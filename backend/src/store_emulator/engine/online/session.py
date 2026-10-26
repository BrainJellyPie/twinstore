"""One shopper's visit: page after page until they order, close the tab, run out of patience or steps.

Time on the site is simulated: every page takes the site's load time (with jitter) plus reading time, which grows
with what is on the page, and typing an address, a card or a new account takes longer. When it passes the shopper's
patience, they give up. Random streams are seeded per (run seed, shopper, decision point), not per site, so two
variants of a site are shopped with common random numbers. A decision point is the page and what covers it, counted
by how often the shopper has been there: a variant that adds a popup or a banner to answer first does not reshuffle
every decision after it.
"""

import math
import random
from collections import Counter

from store_emulator.domain.online import (
    FUNNEL_STAGES,
    ActionKind,
    BrowserState,
    FunnelStage,
    OnlineShopper,
    OnlineSite,
    OrderLine,
    PageKind,
    PageOption,
    SearchRecord,
    SessionOutcome,
    SessionResult,
    SessionStep,
)
from store_emulator.domain.types import stable_seed

from .browser import Page, apply, build_page, cart_totals, initial_state, numbering, outline, returning, search_products
from .policies import Choice, Memory, ShopperPolicy, StepView, Surveyor, comes_back
from .render import ProductPicture, render_page, see_as
from .shoppers import landing

_EXTRA_SECONDS: dict[ActionKind, float] = {
    ActionKind.SEARCH: 3.0, ActionKind.ADD_ADDRESS: 38.0, ActionKind.ADD_PAYMENT: 32.0, ActionKind.CREATE_ACCOUNT: 45.0,
    ActionKind.SIGN_IN: 12.0, ActionKind.GUEST_CHECKOUT: 5.0, ActionKind.PLACE_ORDER: 3.0, ActionKind.APPLY_COUPON: 8.0,
}
_SEED_MOD = 2**31 - 1
# Reading time per page, scaled to the pace of real visits (about half a minute a page on average). Real time between
# page views varies widely, between pages and between people, so the spread is wide and the pace sets the mean.
_READING_PACE = 1.75
_READING_SPREAD = 0.8
# Real visitors sometimes pause between pages (another tab, a call). A pause runs the visit's clock but not the
# shopper's patience, and the shopper is not told about it, so it changes nothing they decide.
_PAUSE_CHANCE = 0.3
_PAUSE_MEDIAN = 40.0
_PAUSE_SPREAD = 1.2


def pause_seconds(rng: random.Random) -> float:
    if rng.random() >= _PAUSE_CHANCE:
        return 0.0
    return rng.lognormvariate(math.log(_PAUSE_MEDIAN), _PAUSE_SPREAD)


def load_seconds(site: OnlineSite, rng: random.Random) -> float:
    return site.options.page_load_ms / 1000 * rng.lognormvariate(0, 0.25)


def read_seconds(page: Page, shopper: OnlineShopper, choice: Choice, rng: random.Random) -> float:
    base = 2.0 + 0.5 * min(page.products_shown(), 16)
    if page.detail is not None:
        base += 6 + 3 * len(page.detail.reviews)
    if page.kind in (PageKind.CART, PageKind.CHECKOUT, PageKind.SIGN_IN):
        base += 4
    if page.overlay is not None:
        base += 2
    if shopper.device == "mobile":
        base *= 1.15
    if shopper.vision == "low_vision":
        base *= 1.25 if page.large_text else 1.8
    elif shopper.vision == "aging_eyes":
        base *= 1.1 if page.large_text else 1.3
    base *= (1.35 - 0.5 * shopper.tech_savvy) * _READING_PACE
    base += _EXTRA_SECONDS.get(choice.control.action.kind, 0.0) + 0.25 * len(choice.query)
    return base * rng.lognormvariate(0, _READING_SPREAD)


def _want_views(shopper: OnlineShopper, rng: random.Random) -> int:
    if shopper.mission == "browse":
        return rng.randint(3, 9)
    if shopper.mission == "deal_hunt":
        return rng.randint(3, 8)
    if shopper.mission in ("compare", "gift"):
        return rng.randint(2, 4)
    return 0


def _history_line(page: Page, choice: Choice) -> str:
    action = choice.control.action
    what = f'searched for "{choice.query}"' if action.kind == ActionKind.SEARCH else action.label
    return f"{page.title.split(' | ')[0]}: {what}"


def _cart_view(site: OnlineSite, state: BrowserState) -> tuple[int, int, tuple[str, ...]]:
    names: list[str] = []
    for line in state.cart:
        product = site.product(line.product_id)
        if product is not None:
            names.append(product.name)
    return (sum(line.quantity for line in state.cart), cart_totals(site, state.cart, state, at_review=False).subtotal,
            tuple(names))


async def run_session(
    site: OnlineSite, shopper: OnlineShopper, policy: ShopperPolicy, *, seed: int, max_steps: int, render: bool,
    shuffle_marks: bool = True, image_width: int = 896, picture: ProductPicture | None = None,
    surveyor: Surveyor | None = None,
) -> SessionResult:
    """`render`: draw a screenshot of every page (vision models need it; rules and text models do not). The
    screenshot is filtered to the shopper's eyesight. `surveyor`: asks the exit survey when the visit is over."""
    state = initial_state(site, device=shopper.device, at=landing(site, shopper))
    rng = random.Random(stable_seed(seed, "online-session", shopper.id))
    memory = Memory(want_views=_want_views(shopper, rng), views=len(state.viewed))
    steps: list[SessionStep] = []
    reached: set[FunnelStage] = {"visit", "product_view"} if state.at.page == PageKind.PRODUCT else {"visit"}
    searches: list[SearchRecord] = []
    pages_seen: set[str] = set()
    viewed: list[str] = list(state.viewed)  # a visit can start on a product page
    outcome: SessionOutcome = "step_limit"
    exit_thought = ""
    requests = fallbacks = addon_paid = discount = 0
    spent = 0.0  # seconds of the visits before the current one
    paused = 0.0  # pauses between pages, on the clock but not on the shopper's patience
    reminded = False
    returned_at: int | None = None
    visits: Counter[str] = Counter()
    ad_products = {ad.id: ad.product_id for ad in site.ads}
    while True:  # a visit, and the one a cart reminder email may bring about
        outcome, exit_thought = "step_limit", ""
        for _ in range(max_steps):
            index = len(steps)
            page = build_page(site, state)
            pages_seen.add(page.url)
            point = f"{state.at.model_dump_json()}|{state.overlay}|{page.cookie is not None}"
            point_seed = stable_seed(seed, "online-step", shopper.id, point, visits[point])
            visits[point] += 1
            step_rng = random.Random(point_seed)
            shown = page.ads_shown
            memory.ad_products.update(ad_products[ad] for ad in shown)
            load = load_seconds(site, step_rng)
            memory.last_load = load
            mark_seed = stable_seed(seed, "online-marks", shopper.id, index) % _SEED_MOD + 1 if shuffle_marks else 0
            numbers = numbering(page, mark_seed)
            image_url, boxes, screen = "", dict[int, tuple[int, int, int, int]](), None
            if render:
                shot = see_as(render_page(page, site, numbers, picture), shopper.vision, large_text=page.large_text)
                image_url, boxes, screen = shot.scaled_data_url(image_width), shot.boxes, (shot.width, shot.height)
            count, subtotal, names = _cart_view(site, state)
            view = StepView(page, state, numbers, outline(page, site), count, subtotal, names, image_url,
                            seed=stable_seed(seed, "online-call", shopper.id, index) % _SEED_MOD, point=point_seed)
            choice = await policy.choose(site, shopper, view, memory, step_rng)
            if choice.control.index not in numbers:  # a policy may only use what is on the page
                choice = Choice(page.leave, thought=choice.thought, source=choice.source,
                                error=choice.error or f"picked a control that is not on the page: {choice.control.action.label}")
            if choice.source != "rule":
                requests += 1
            if choice.source == "fallback":
                fallbacks += 1
            seconds = load + read_seconds(page, shopper, choice, step_rng)
            memory.elapsed += seconds
            pause = pause_seconds(random.Random(stable_seed(seed, "online-pause", shopper.id, index)))
            paused += pause
            action = choice.control.action
            steps.append(SessionStep(
                index=index, url=page.url, page=page.kind, state=state, options=len(numbers),
                choice=PageOption(kind=action.kind, target=action.target, label=action.label, ad_id=action.ad_id,
                                  number=numbers[choice.control.index], box=boxes.get(choice.control.index)),
                search_text=choice.query, thought=choice.thought[:240], seconds=round(seconds + pause, 2), load_seconds=round(load, 2),
                source=choice.source, error=choice.error, mark_seed=mark_seed, screen=screen, ads=shown,
            ))
            memory.steps.append(_history_line(page, choice))
            if action.kind == ActionKind.LEAVE:
                exit_thought = choice.thought
                outcome = "abandoned_cart" if state.cart else "bounced" if len(pages_seen) <= 1 else "left"
                break
            new_state = apply(site, state, action, query=choice.query, has_account=shopper.has_account)
            if action.kind == ActionKind.PLACE_ORDER and new_state.order_id:
                totals = cart_totals(site, state.cart, state, at_review=True)
                addon_paid, discount = totals.addon, totals.discount
            if action.kind == ActionKind.SEARCH and new_state.at.page == PageKind.SEARCH:
                query = new_state.at.query
                searches.append(SearchRecord(query=query, results=len(search_products(site, query)), step=index))
                memory.searched.append(choice.query.strip().lower())
            if action.kind == ActionKind.OPEN_PRODUCT and new_state.at.page == PageKind.PRODUCT:
                memory.views += 1
                viewed.append(action.target)
                reached.add("product_view")
            if action.kind == ActionKind.NEXT_PAGE:
                memory.pages_turned += 1
            if sum(line.quantity for line in new_state.cart) > sum(line.quantity for line in state.cart):
                reached.add("add_to_cart")
            if new_state.at.page in (PageKind.SIGN_IN, PageKind.CHECKOUT):
                reached.add("checkout")
            if new_state.payment_method is not None and (new_state.at.page == PageKind.CHECKOUT or new_state.order_id):
                reached.add("payment")
            state = new_state
            if state.order_id:
                reached.add("purchase")
                outcome = "purchased"
                final = build_page(site, state)
                steps.append(SessionStep(index=index + 1, url=final.url, page=final.kind, state=state,
                                         options=len(final.active), seconds=0.0))
                break
            if memory.elapsed >= shopper.patience_sec:
                outcome = "abandoned_cart" if state.cart else "timed_out"
                exit_thought = "Out of patience: this is taking too long."
                break
        if outcome == "step_limit" and state.cart:
            outcome = "abandoned_cart"
        if outcome != "abandoned_cart" or not site.options.cart_reminder or returned_at is not None:
            break
        reminded = True
        percent = site.options.cart_reminder_percent
        if random.Random(stable_seed(seed, "online-reminder", shopper.id)).random() >= comes_back(shopper, percent):
            break
        returned_at = len(steps)
        state = returning(state, percent)
        spent += memory.elapsed
        memory.elapsed = 0.0  # a new visit, with patience to match
        memory.steps.append("Next day: a reminder email about my cart brought me back"
                            + (f" with {percent}% off" if percent else ""))
    order: list[OrderLine] = []
    for line in state.order:
        product = site.product(line.product_id)
        if product is not None:
            order.append(OrderLine(product_id=product.id, name=product.name, category_id=product.category_id,
                                   quantity=line.quantity, price=product.price))
    survey = None
    if surveyor is not None:
        requests += 1
        survey = await surveyor(site, shopper, history=memory.steps, outcome=outcome, seconds=spent + memory.elapsed,
                                paid=state.order_total, seed=stable_seed(seed, "online-survey", shopper.id) % _SEED_MOD)
    return SessionResult(
        shopper_id=shopper.id, site_id=site.id, outcome=outcome, steps=steps, order=order,
        subtotal=sum(line.price * line.quantity for line in order), order_total=state.order_total,
        seconds=round(spent + memory.elapsed + paused, 1), reached=[s for s in FUNNEL_STAGES if s in reached], viewed_products=viewed,
        searches=searches, exit_page=steps[-1].page if steps else PageKind.HOME, exit_thought=exit_thought[:240],
        model_requests=requests, fallbacks=fallbacks, survey=survey, addon_paid=addon_paid, discount=discount,
        reminded=reminded, returned_at=returned_at,
    )
