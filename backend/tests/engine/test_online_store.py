"""Online stores: templates, the browser state machine, screenshots, shoppers, sessions and their analysis."""

import asyncio
import io
import random

import pytest
from PIL import Image
from pydantic import BaseModel, ValidationError

from store_emulator.domain.online import (
    ActionKind,
    BrowserState,
    CartLine,
    OnlineAction,
    OnlineRunRequest,
    OnlineShopper,
    OnlineSite,
    PageKind,
    PageRef,
)
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.online.analysis import clickstream_csv, paired_deltas, summarize
from store_emulator.engine.online.browser import (
    Page,
    apply,
    build_page,
    cart_totals,
    initial_state,
    numbering,
    outline,
    search_products,
)
from store_emulator.engine.online.catalog import build_site, template_ids, template_summaries
from store_emulator.engine.online.policies import ModelPolicy, RulePolicy
from store_emulator.engine.online.prompt import choice_model
from store_emulator.engine.online.render import render_page
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers


def _site(template: str = "fashion", **options: object) -> OnlineSite:
    site = build_site(template, site_id="s1")
    return site.model_copy(update={"options": site.options.model_copy(update=options)}) if options else site


def _act(site: OnlineSite, state: BrowserState, kind: ActionKind, target: str | None = None, **kw: object) -> BrowserState:
    page = build_page(site, state)
    control = next(c for c in page.active if c.action.kind == kind and (target is None or c.action.target == target))
    return apply(site, state, control.action, **kw)  # type: ignore[arg-type]


def _kinds(page: Page) -> set[ActionKind]:
    return {c.action.kind for c in page.active}


def test_every_template_builds_a_consistent_shop() -> None:
    summaries = template_summaries()
    assert len(summaries) >= 40 and len({t.id for t in summaries}) == len(summaries)
    assert sum(t.products for t in summaries) > 2000 and sum(t.photos for t in summaries) > 1000
    for template in template_ids():
        site = build_site(template, site_id="s")
        ids = [p.id for p in site.products]
        assert len(ids) == len(set(ids)) and site.categories
        assert {p.category_id for p in site.products} <= {c.id for c in site.categories}
        assert all(p.list_price == 0 or p.list_price > p.price for p in site.products)
        assert any("bestseller" in p.badges for p in site.products)


def test_templates_are_deterministic_and_localized() -> None:
    assert build_site("grocery_delivery", site_id="a") == build_site("grocery_delivery", site_id="a")
    usd = build_site("grocery_delivery", site_id="a")
    krw = build_site("grocery_delivery", site_id="a", currency="KRW")
    assert krw.currency == "KRW" and krw.products[0].name != usd.products[0].name
    assert all(p.price % 100 == 0 for p in krw.products)
    assert krw.options.shipping_fee % 100 == 0 and krw.options.shipping_fee > usd.options.shipping_fee
    with pytest.raises(ValueError):
        build_site("nope", site_id="a")


def test_home_page_offers_the_browser_and_shop_controls() -> None:
    site = _site(cookie_banner=False)
    page = build_page(site, BrowserState())
    kinds = _kinds(page)
    assert {ActionKind.SEARCH, ActionKind.OPEN_MENU, ActionKind.OPEN_SETTINGS, ActionKind.OPEN_CART, ActionKind.HOME,
            ActionKind.OPEN_CATEGORY, ActionKind.OPEN_PRODUCT, ActionKind.LEAVE} <= kinds
    assert ActionKind.BACK not in kinds  # nothing to go back to yet
    numbers = numbering(page)
    assert sorted(numbers.values()) == list(range(1, len(page.active) + 1))
    shuffled = numbering(page, 12345)
    assert sorted(shuffled.values()) == sorted(numbers.values()) and shuffled != numbers
    assert numbering(page, 12345) == shuffled


def test_a_welcome_popup_blocks_the_page_until_answered() -> None:
    site = _site("beauty")  # coupon popup, hidden code
    state = initial_state(site)
    page = build_page(site, state)
    assert _kinds(page) == {ActionKind.ACCEPT_POPUP, ActionKind.CLOSE_POPUP, ActionKind.LEAVE}
    accepted = _act(site, state, ActionKind.ACCEPT_POPUP)
    assert accepted.overlay == "none" and accepted.coupon_applied and accepted.coupon_known
    closed = _act(site, state, ActionKind.CLOSE_POPUP)
    assert not closed.coupon_known and ActionKind.SEARCH in _kinds(build_page(site, closed))


def test_menu_lists_categories_and_back_returns() -> None:
    site = _site(cookie_banner=False)
    state = _act(site, BrowserState(), ActionKind.OPEN_MENU)
    page = build_page(site, state)
    assert page.overlay is not None and page.overlay.modal
    assert ActionKind.CLOSE_MENU in _kinds(page) and ActionKind.SEARCH not in _kinds(page)
    category = site.categories[1].id
    state = _act(site, state, ActionKind.OPEN_CATEGORY, category)
    assert state.at.page == PageKind.CATEGORY and state.at.category_id == category and state.overlay == "none"
    back = _act(site, state, ActionKind.BACK)
    assert back.at.page == PageKind.HOME and not back.history


def test_search_modes() -> None:
    site = _site()
    assert any("Sneakers" in p.name for p in search_products(site, "sneakers"))
    assert search_products(site, "zzzz nothing") == []
    exact = site.model_copy(update={"options": site.options.model_copy(update={"search": "exact"})})
    assert search_products(exact, "sneakers canvas") == []  # words out of order find nothing
    off = site.model_copy(update={"options": site.options.model_copy(update={"search": "off"})})
    assert ActionKind.SEARCH not in _kinds(build_page(off, BrowserState()))
    state = apply(site, BrowserState(), OnlineAction(kind=ActionKind.SEARCH), query="  canvas   sneakers ")
    assert state.at.page == PageKind.SEARCH and state.at.query == "canvas sneakers"
    assert apply(site, BrowserState(), OnlineAction(kind=ActionKind.SEARCH), query=" ").notice


def test_listing_sorts_and_pages() -> None:
    site = _site(products_per_page=4, cookie_banner=False)
    state = apply(site, BrowserState(), OnlineAction(kind=ActionKind.OPEN_CATEGORY, target=site.categories[0].id))
    page = build_page(site, state)
    assert len(page.grids[0].cards) == 4 and ActionKind.NEXT_PAGE in _kinds(page)
    cheap = _act(site, state, ActionKind.SORT, "price_asc")
    cards = build_page(site, cheap).grids[0].cards
    assert cards[0].sponsored  # fashion pays for one sponsored slot, which stays on top whatever the order
    prices = [c.product.price for c in cards if not c.sponsored]
    assert prices == sorted(prices)
    second = _act(site, cheap, ActionKind.NEXT_PAGE)
    assert second.at.page_index == 1 and ActionKind.PREVIOUS_PAGE in _kinds(build_page(site, second))


def test_cart_totals_shipping_coupon_fees_and_addon() -> None:
    site = _site(shipping_fee=500, free_shipping_threshold=5000, coupon_code="X10", coupon_percent=10,
                 service_fee=99, preselected_addon_percent=10)
    product = next(p for p in site.products if 1000 <= p.price <= 2000)
    cart = [CartLine(product_id=product.id, quantity=2)]
    state = BrowserState(cart=cart)
    plain = cart_totals(site, cart, state, at_review=False)
    assert plain.subtotal == product.price * 2 and plain.shipping == 500 and plain.service_fee == plain.addon == 0
    review = cart_totals(site, cart, state, at_review=True)
    assert review.service_fee == 99 and review.addon == round(product.price * 2 * 0.1)
    assert review.total == review.subtotal + 500 + 99 + review.addon
    coupon = cart_totals(site, cart, state.model_copy(update={"coupon_applied": True, "addon_removed": True}), at_review=True)
    assert coupon.discount == round(product.price * 0.2) and coupon.addon == 0


def test_checkout_flow_multi_step_with_guest_and_order() -> None:
    site = _site("fashion", welcome_popup="none", cookie_banner=False, payment_methods=["card", "paypal"])
    product = next(p for p in site.products if p.stock != 0)
    state = apply(site, BrowserState(), OnlineAction(kind=ActionKind.OPEN_PRODUCT, target=product.id))
    state = _act(site, state, ActionKind.ADD_TO_CART)
    assert state.cart == [CartLine(product_id=product.id)] and state.notice.startswith("Added")
    state = _act(site, state, ActionKind.OPEN_CART)
    state = _act(site, state, ActionKind.CHECKOUT)
    assert state.at.page == PageKind.SIGN_IN
    no_account = _act(site, state, ActionKind.SIGN_IN)
    assert no_account.at.page == PageKind.SIGN_IN and "No account" in no_account.notice
    state = _act(site, state, ActionKind.GUEST_CHECKOUT)
    assert state.at.checkout_step == "address"
    state = _act(site, state, ActionKind.ADD_ADDRESS)
    assert state.at.checkout_step == "payment"
    assert {c.action.target for c in build_page(site, state).active if c.action.kind == ActionKind.ADD_PAYMENT} == {"card", "paypal"}
    state = _act(site, state, ActionKind.ADD_PAYMENT, "paypal")
    assert state.at.checkout_step == "review" and state.payment_method == "paypal"
    total = cart_totals(site, state.cart, state, at_review=True).total
    state = _act(site, state, ActionKind.PLACE_ORDER)
    assert state.at.page == PageKind.ORDER_COMPLETE and state.order_id.startswith("ORD-")
    assert state.cart == [] and state.order == [CartLine(product_id=product.id)] and state.order_total == total


def test_accounts_one_page_checkout_and_buy_now() -> None:
    site = _site(guest_checkout=False, checkout_flow="one_page", one_click_buy=True, welcome_popup="none",
                 cookie_banner=False)
    product = next(p for p in site.products if p.stock != 0)
    state = apply(site, BrowserState(), OnlineAction(kind=ActionKind.OPEN_PRODUCT, target=product.id))
    state = _act(site, state, ActionKind.BUY_NOW)
    assert state.at.page == PageKind.SIGN_IN and ActionKind.GUEST_CHECKOUT not in _kinds(build_page(site, state))
    signed = _act(site, state, ActionKind.SIGN_IN, has_account=True)
    assert signed.at.page == PageKind.CHECKOUT and signed.address_added and signed.payment_method == "card"
    assert ActionKind.PLACE_ORDER in _kinds(build_page(site, signed))
    created = _act(site, state, ActionKind.CREATE_ACCOUNT)
    page = build_page(site, created)
    assert ActionKind.PLACE_ORDER not in _kinds(page) and ActionKind.ADD_ADDRESS in _kinds(page)


def test_sold_out_products_cannot_be_added() -> None:
    site = _site()
    sold = site.products[0].model_copy(update={"stock": 0})
    site = site.model_copy(update={"products": [sold, *site.products[1:]]})
    state = apply(site, BrowserState(cookies_answered=True), OnlineAction(kind=ActionKind.OPEN_PRODUCT, target=sold.id))
    assert ActionKind.ADD_TO_CART not in _kinds(build_page(site, state))
    assert apply(site, state, OnlineAction(kind=ActionKind.ADD_TO_CART, target=sold.id)).cart == []


def test_screenshot_marks_every_option_and_is_deterministic() -> None:
    site = _site(cookie_banner=True)
    for state in (BrowserState(), BrowserState(device="mobile"), initial_state(site)):
        page = build_page(site, state)
        numbers = numbering(page, 7)
        shot = render_page(page, site, numbers)
        assert set(shot.boxes) == set(numbers)
        assert all(0 <= x0 < x1 <= shot.width and 0 <= y0 < y1 <= shot.height for x0, y0, x1, y1 in shot.boxes.values())
        with Image.open(io.BytesIO(shot.png)) as image:
            assert image.size == (shot.width, shot.height)
        assert render_page(page, site, numbers).png == shot.png
    assert render_page(build_page(site, BrowserState(device="mobile")), site, {}).width < 500
    small = render_page(build_page(site, BrowserState()), site, {}).scaled_data_url(480)
    assert small.startswith("data:image/png;base64,")


def test_outline_reads_the_page_as_text() -> None:
    site = _site("grocery_delivery", cookie_banner=False)
    text = outline(build_page(site, BrowserState()), site)
    assert text[0].startswith("Page: ") and any(line.startswith("Section: ") for line in text)


def _shoppers(site: OnlineSite, n: int = 30, seed: int = 1) -> list[OnlineShopper]:
    request = OnlineRunRequest(site_ids=["s1"])
    return sample_shoppers(site, n, seed=seed, missions=request.missions, mobile_share=request.mobile_share)


def test_shopper_panel_is_reproducible_and_mission_driven() -> None:
    site = _site()
    panel = _shoppers(site, 60)
    assert panel == _shoppers(site, 60) and len({s.id for s in panel}) == 60
    assert {s.mission for s in panel} >= {"purchase", "browse"}
    for s in panel:
        if s.mission == "replenish":
            assert site.product(s.target_product) is not None
        if s.mission in ("purchase", "compare", "gift"):
            assert s.target_category and s.target_terms and s.budget > 0
    only = sample_shoppers(site, 10, seed=3, missions={"deal_hunt": 1.0}, mobile_share=1.0)
    assert {s.mission for s in only} == {"deal_hunt"}


def _run(site: OnlineSite, shoppers: list[OnlineShopper], **kw: object) -> list:  # type: ignore[type-arg]
    async def go() -> list:  # type: ignore[type-arg]
        return [await run_session(site, s, RulePolicy(), seed=5, max_steps=30, render=False, **kw) for s in shoppers]  # type: ignore[arg-type]
    return asyncio.run(go())


def test_rule_sessions_are_reproducible_and_end_properly() -> None:
    site = _site()
    shoppers = _shoppers(site)
    first, again = _run(site, shoppers), _run(site, shoppers)
    assert first == again
    outcomes = {s.outcome for s in first}
    assert "purchased" in outcomes and outcomes & {"left", "bounced", "abandoned_cart"}
    for session in first:
        assert session.reached[0] == "visit"
        if session.outcome == "purchased":
            assert session.steps[-1].page == PageKind.ORDER_COMPLETE and session.order and session.order_total > 0
            assert "purchase" in session.reached and "checkout" in session.reached
        else:
            assert session.order_total == 0


def test_analysis_and_paired_deltas() -> None:
    site = _site()
    shoppers = _shoppers(site, 40)
    sessions = _run(site, shoppers)
    summary = summarize(site, {s.id: s for s in shoppers}, sessions)
    shares = [row.sessions for row in summary.funnel]
    assert shares == sorted(shares, reverse=True) and shares[0] == 40
    assert summary.purchases == sum(s.outcome == "purchased" for s in sessions)
    assert {row.dimension for row in summary.segments} == {"mission", "device", "age_group", "gender"}
    slow = site.model_copy(update={"options": site.options.model_copy(update={"page_load_ms": 6000})})
    slow_sessions = _run(slow, shoppers)
    deltas = {d.metric: d for d in paired_deltas(sessions, slow_sessions)}
    assert deltas["conversion"].n == 40 and deltas["conversion"].diff <= 0 and deltas["steps"].diff < 0
    assert deltas["conversion"].ci_low is not None and deltas["conversion"].ci_low <= deltas["conversion"].diff
    loads = [step.load_seconds for s in slow_sessions for step in s.steps if step.choice]
    assert sum(loads) / len(loads) > 4
    csv_text = clickstream_csv([(site, sessions)], {s.id: s for s in shoppers})
    assert csv_text.splitlines()[0].startswith("variant,site,shopper")


class _FakeModel:
    """Picks the option whose label contains `want` (else the first), typing `query` into search."""

    def __init__(self, want: str = "Search box", query: str = "sneakers", *, fail: bool = False) -> None:
        self.want, self.query, self.fail = want, query, fail
        self.calls: list[dict[str, object]] = []

    def _answer[T: BaseModel](self, response_model: type[T], system: str, prompt: str, image: str | None) -> T:
        self.calls.append({"system": system, "prompt": prompt, "image": image})
        if self.fail:
            raise TimeoutError("model server timed out")
        options = [line for line in prompt.splitlines() if line.startswith("[")]
        hit = next((line for line in options if self.want in line), options[0])
        number = int(hit[1:hit.index("]")])
        return response_model.model_validate({"option": number, "search_text": self.query if "Search box" in hit else "",
                                              "thought": "Looking around."})

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        return self._answer(response_model, system_prompt, user_prompt, None)

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        assert image_url.startswith("data:image/png;base64,")
        return self._answer(response_model, system_prompt, user_prompt, image_url)

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=len(self.calls))


def test_vision_policy_sees_the_screenshot_and_numbered_options() -> None:
    site = _site(welcome_popup="none")
    shopper = _shoppers(site, 1)[0]
    model = _FakeModel()
    session = asyncio.run(run_session(site, shopper, ModelPolicy(model, vision=True), seed=1, max_steps=2, render=True,
                                      image_width=600))
    first = model.calls[0]
    assert isinstance(first["image"], str) and "screenshot" in str(first["system"])
    assert "Options:" in str(first["prompt"]) and shopper.goal in str(first["prompt"])
    step = session.steps[0]
    assert step.source == "model" and step.choice is not None and step.choice.kind == ActionKind.SEARCH
    assert step.search_text == "sneakers" and step.choice.box is not None and step.screen is not None
    assert session.steps[1].state.at.page == PageKind.SEARCH and session.model_requests == 2


def test_text_policy_reads_the_outline_and_failures_fall_back_to_rules() -> None:
    site = _site(welcome_popup="none")
    shopper = _shoppers(site, 1)[0]
    model = _FakeModel(want="Close the tab")
    session = asyncio.run(run_session(site, shopper, ModelPolicy(model, vision=False), seed=1, max_steps=5, render=False))
    assert model.calls[0]["image"] is None and "Page: " in str(model.calls[0]["prompt"])
    assert session.outcome == "bounced" and len(session.steps) == 1
    broken = asyncio.run(run_session(site, shopper, ModelPolicy(_FakeModel(fail=True), vision=False), seed=1,
                                     max_steps=4, render=False))
    assert broken.fallbacks == broken.model_requests > 0
    assert all(s.source == "fallback" and "TimeoutError" in s.error for s in broken.steps if s.choice)


def test_choice_schema_limits_answers_to_the_page() -> None:
    schema = choice_model([2, 5, 9], search_number=5)
    assert schema.model_validate({"option": "[9]"}).option == 9
    assert schema.model_json_schema()["properties"]["option"]["enum"] == [2, 5, 9]
    with pytest.raises(ValidationError):
        schema.model_validate({"option": 4})
    with pytest.raises(ValidationError):
        schema.model_validate({"option": 5, "search_text": ""})
    with pytest.raises(ValidationError):
        schema.model_validate({"option": True})
    long = schema.model_validate({"option": 2, "thought": "x" * 500})
    assert len(long.thought) == 200


def test_slow_pages_cost_patience() -> None:
    site = _site(page_load_ms=12000)
    shoppers = _shoppers(site, 30, seed=4)
    sessions = _run(site, shoppers)
    fast = _run(_site(page_load_ms=300), shoppers)
    assert sum(s.outcome == "purchased" for s in sessions) < sum(s.outcome == "purchased" for s in fast)
    assert random.Random(1).random() == random.Random(1).random()  # sanity: seeded streams only


@pytest.mark.parametrize("template", ["fashion", "electronics", "senior_care", "food_delivery", "beauty", "marketplace"])
def test_random_crawl_every_option_is_drawn(template: str) -> None:
    """Click through a store at random: every option a page offers must be visible in its screenshot."""
    site = build_site(template, site_id="crawl")
    rng = random.Random(template)
    for device in ("desktop", "mobile"):
        state = initial_state(site, device=device)
        for _ in range(22):
            page = build_page(site, state)
            numbers = numbering(page, rng.randint(0, 99))
            shot = render_page(page, site, numbers)
            missing = [c.action.label for c in page.active if c.index not in shot.boxes]
            assert not missing, f"{page.url}: options not drawn: {missing}"
            choices = [c for c in page.active if c.action.kind != ActionKind.LEAVE]
            weights = [6 if c.action.kind in (ActionKind.ADD_TO_CART, ActionKind.CHECKOUT, ActionKind.PLACE_ORDER,
                                              ActionKind.GUEST_CHECKOUT, ActionKind.ADD_ADDRESS, ActionKind.ADD_PAYMENT,
                                              ActionKind.OPEN_CART) else 1 for c in choices]
            control = rng.choices(choices, weights=weights, k=1)[0]
            state = apply(site, state, control.action, query="gift", has_account=rng.random() < 0.5)
