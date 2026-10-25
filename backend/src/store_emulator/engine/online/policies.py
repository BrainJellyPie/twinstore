"""Who clicks: rules (instant and free) or a language/vision model.

The rule shopper follows its mission with seeded probabilities: it searches or browses to what it came for, weighs
relevance, price against budget, rating and discounts, and reacts to friction the way shoppers commonly do — some
leave at a forced sign-up, a fee revealed at the last step or a slow page, some accept a welcome coupon. Its numbers
are illustrative priors, not calibrated measurements. The model shopper sees the page (screenshot or text outline)
and the numbered options and picks one; when a call fails, the rule shopper decides that step.
"""

import random
from dataclasses import dataclass, field
from typing import Protocol

from store_emulator.domain.online import (
    PAYMENT_METHODS,
    ActionKind,
    BrowserState,
    OnlineProduct,
    OnlineShopper,
    OnlineSite,
    PageKind,
    PaymentMethod,
    StepSource,
)

from store_emulator.engine.llm_router import SimLLM
from store_emulator.engine.prompting import display_price

from .browser import Control, Page, cart_totals, query_terms
from .prompt import choice_model, system_prompt, user_prompt
from .shoppers import product_terms


@dataclass
class Memory:
    """What the shopper remembers of this visit."""
    steps: list[str] = field(default_factory=list[str])  # "Home page: closed the popup", one per step
    searched: list[str] = field(default_factory=list[str])
    rejected: set[str] = field(default_factory=set[str])
    views: int = 0
    pages_turned: int = 0
    satisfied: bool = False  # what they came for is in the cart
    elapsed: float = 0.0
    last_load: float = 0.0
    want_views: int = 0  # products a browser or comparer looks at before deciding
    looked: bool = False  # the landing page made its first impression


@dataclass(frozen=True)
class Choice:
    control: Control
    query: str = ""
    thought: str = ""
    source: StepSource = "rule"
    error: str = ""


@dataclass(frozen=True)
class StepView:
    """One page as the policy gets it: the laid-out page, the browser state behind it, badge numbers, and (for
    vision) the screenshot."""
    page: Page
    state: BrowserState
    numbers: dict[int, int]
    outline: list[str]
    cart_count: int = 0
    cart_subtotal: int = 0
    cart_names: tuple[str, ...] = ()
    image_url: str = ""
    seed: int = 0


class ShopperPolicy(Protocol):
    async def choose(self, site: OnlineSite, shopper: OnlineShopper, view: StepView, memory: Memory,
                     rng: random.Random) -> Choice: ...


def _find(page: Page, kind: ActionKind, target: str | None = None) -> Control | None:
    return next((c for c in page.active if c.action.kind == kind and (target is None or c.action.target == target)), None)


def _all(page: Page, kind: ActionKind) -> list[Control]:
    return [c for c in page.active if c.action.kind == kind]


def relevance(shopper: OnlineShopper, product: OnlineProduct, site: OnlineSite) -> float:
    """0–1: how well a product fits what the shopper came for."""
    if shopper.target_product:
        same = shopper.target_category and product.category_id == shopper.target_category
        return 1.0 if product.id == shopper.target_product else 0.3 if same else 0.05
    in_category = bool(shopper.target_category) and product.category_id == shopper.target_category
    if shopper.mission == "deal_hunt":
        return min(1.0, 0.15 + product.discount_percent / 35)
    if shopper.mission in ("browse", "compare", "gift"):
        # The category is the goal: anything in it fits, other things a little.
        return 1.0 if in_category else 0.45 if shopper.mission == "browse" else 0.1
    category = site.category(product.category_id)
    text = set(query_terms(f"{product.name} {category.name if category else ''} {' '.join(product.tags)}"))
    score = 0.35 if in_category else 0.0
    for phrase in shopper.target_terms:
        words = query_terms(phrase)
        hits = [any(t.startswith(w) or (len(t) >= 3 and w.startswith(t)) for t in text) for w in words]
        if words and all(hits):
            score += 0.65
            break
        if any(hits):
            score += 0.25
    return min(1.0, score)


def _rating_factor(rating: float) -> float:
    return min(1.0, max(0.4, 0.85 + 0.15 * (rating - 4)))


def _budget_left(site: OnlineSite, shopper: OnlineShopper, view: StepView) -> int | None:
    if shopper.budget <= 0:
        return None
    return shopper.budget - view.cart_subtotal


def _appeal(site: OnlineSite, shopper: OnlineShopper, product: OnlineProduct, view: StepView, rng: random.Random) -> float:
    left = _budget_left(site, shopper, view)
    score = relevance(shopper, product, site)
    if product.stock == 0:
        score *= 0.3
    if left is not None and product.price > left:
        score *= 0.25
    score *= _rating_factor(product.rating)
    score *= 1 + shopper.price_sensitivity * product.discount_percent / 60
    if "bestseller" in product.badges:
        score *= 1.08
    return score * rng.uniform(0.85, 1.15)


def _goal_link(page: Page, shopper: OnlineShopper) -> Control | None:
    if shopper.mission == "deal_hunt":
        return _find(page, ActionKind.OPEN_DEALS)
    if shopper.target_category:
        return _find(page, ActionKind.OPEN_CATEGORY, shopper.target_category)
    return None


_OLDER_PAYMENTS: tuple[PaymentMethod, ...] = ("card", "bank_transfer", "cash_on_delivery")


def _payment(site: OnlineSite, shopper: OnlineShopper, page: Page, rng: random.Random) -> Control | None:
    preferred: list[PaymentMethod] = []
    young = shopper.age_group in ("10s", "20s", "30s")
    if shopper.device == "mobile" and young:
        preferred.append("apple_pay")
    if young and shopper.price_sensitivity > 0.6 and rng.random() < 0.4:
        preferred.insert(0, "bnpl")
    if shopper.age_group in ("50s", "60s+"):
        preferred.extend(_OLDER_PAYMENTS)
    preferred.extend(PAYMENT_METHODS)
    options = _all(page, ActionKind.ADD_PAYMENT)
    for method in preferred[:3]:
        hit = next((c for c in options if c.action.target == method), None)
        if hit is not None:
            return hit
    # Their usual ways to pay are missing: most use another, some leave.
    if options and rng.random() < 0.85:
        for method in preferred:
            hit = next((c for c in options if c.action.target == method), None)
            if hit is not None:
                return hit
    return None


class RulePolicy:
    """The rule shopper. Deterministic for a given random stream."""

    async def choose(self, site: OnlineSite, shopper: OnlineShopper, view: StepView, memory: Memory,
                     rng: random.Random) -> Choice:
        return decide(site, shopper, view, memory, rng)


def decide(site: OnlineSite, shopper: OnlineShopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
    page = view.page
    leave = page.leave

    def pick(control: Control | None, thought: str, query: str = "") -> Choice | None:
        return Choice(control, query=query, thought=thought) if control is not None else None

    # Overlays first: they cover the page.
    if page.overlay is not None and page.overlay.kind == "welcome":
        if rng.random() < 0.03 + 0.05 * (1 - shopper.tech_savvy):
            return Choice(leave, thought="A popup before I even see anything? I'm out.")
        accept = 0.15 + 0.55 * shopper.price_sensitivity + (0.2 if shopper.mission == "deal_hunt" else 0)
        if rng.random() < accept:
            return pick(_find(page, ActionKind.ACCEPT_POPUP), "A discount? Sure, I'll take it.") or Choice(leave)
        return pick(_find(page, ActionKind.CLOSE_POPUP), "No thanks, just let me shop.") or Choice(leave)
    if page.overlay is not None and page.overlay.kind == "menu":
        target = _goal_link(page, shopper)
        if target is None and shopper.mission == "browse":
            categories = _all(page, ActionKind.OPEN_CATEGORY)
            target = rng.choice(categories) if categories else None
        return (pick(target, f"{target.action.label.removeprefix('Menu: ')} is what I want." if target else "")
                or pick(_find(page, ActionKind.CLOSE_MENU), "Nothing useful in here.") or Choice(leave))

    # A slow page tests patience.
    if memory.last_load > 2.5 and page.kind != PageKind.ORDER_COMPLETE:
        p_leave = min(0.45, 0.07 * (memory.last_load - 2)) * (1.3 - shopper.tech_savvy * 0.5) * (0.6 if memory.satisfied else 1)
        if rng.random() < p_leave:
            return Choice(leave, thought="This site is so slow. Never mind.")

    # First impression: some visitors leave the landing page at once, low-intent ones most.
    if not memory.looked and page.overlay is None:
        memory.looked = True
        bounce = {"browse": 0.22, "deal_hunt": 0.14, "gift": 0.07, "compare": 0.05, "purchase": 0.05,
                  "replenish": 0.02}[shopper.mission]
        if rng.random() < bounce:
            return Choice(leave, thought="Not what I expected. Moving on.")

    # Cookie banner: most answer it on the first page they see.
    if page.cookie is not None and not memory.steps and rng.random() < 0.7:
        accept, reject = page.cookie
        return Choice(accept if rng.random() < 0.72 else reject, thought="Get this banner out of the way.")

    if page.kind == PageKind.PRODUCT and page.detail is not None:
        return _on_product(site, shopper, view, memory, rng)
    if page.kind == PageKind.CART:
        return _on_cart(site, shopper, view, memory, rng)
    if page.kind == PageKind.SIGN_IN:
        return _on_sign_in(shopper, page, rng)
    if page.kind == PageKind.CHECKOUT:
        return _on_checkout(site, shopper, view, rng)
    return _on_listing(site, shopper, view, memory, rng)


def _on_listing(site: OnlineSite, shopper: OnlineShopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
    page = view.page
    leave = page.leave
    if memory.satisfied:
        cart = page.header.cart
        if view.cart_count:
            return Choice(cart, thought="Got what I came for. Let's check out.")
    browsing = shopper.mission in ("browse", "deal_hunt")
    if shopper.mission in ("compare", "gift") and memory.views >= memory.want_views + 2:
        return Choice(leave, thought="None of them convinced me. I'll look elsewhere.")
    if browsing and memory.want_views and memory.views >= memory.want_views:
        if view.cart_count and rng.random() < 0.8:
            return Choice(page.header.cart, thought="Let me look at what I picked.")
        return Choice(leave, thought="That's enough browsing for today.")
    cards = [card for grid in page.grids for card in grid.cards
             if card.open.index in view.numbers and card.product.id not in memory.rejected]
    unseen = [c for c in cards if not browsing or c.product.id not in view.state.viewed]
    scored = sorted(((_appeal(site, shopper, c.product, view, rng), i, c) for i, c in enumerate(unseen)),
                    key=lambda s: (-s[0], s[1]))
    threshold = 0.25 if browsing else 0.5
    if page.kind == PageKind.HOME and browsing and rng.random() < 0.5:
        link = _goal_link(page, shopper) or (rng.choice(_all(page, ActionKind.OPEN_CATEGORY)) if _all(page, ActionKind.OPEN_CATEGORY) else None)
        if link is not None:
            return Choice(link, thought="Let me see what they have in here.")
    if scored and scored[0][0] >= threshold:
        best = scored[0][2]
        return Choice(best.open, thought=f"{best.product.name} looks right." if not browsing
                      else f"Ooh, {best.product.name}.")
    if page.kind == PageKind.SEARCH and not cards:
        if len(memory.searched) < 2 and shopper.target_terms:
            words = query_terms(memory.searched[-1] if memory.searched else shopper.target_terms[0])
            shorter = words[-1] if len(words) > 1 else ""
            search = page.header.search
            if shorter and search is not None and shorter not in memory.searched:
                return Choice(search, query=shorter, thought="Nothing? Let me try fewer words.")
        link = _goal_link(page, shopper)
        if link is not None:
            return Choice(link, thought="Search is useless. I'll look in the category.")
        if rng.random() < 0.45:
            return Choice(leave, thought="They don't seem to have it.")
    next_page = _find(page, ActionKind.NEXT_PAGE)
    if next_page is not None and memory.pages_turned < 2 and rng.random() < 0.55:
        return Choice(next_page, thought="Maybe on the next page.")
    if shopper.price_sensitivity > 0.65 and page.kind in (PageKind.CATEGORY, PageKind.SEARCH):
        cheap = _find(page, ActionKind.SORT, "price_asc")
        if cheap is not None and rng.random() < 0.5:
            return Choice(cheap, thought="Show me the cheapest first.")
    search = page.header.search
    terms = shopper.target_terms[0] if shopper.target_terms else ""
    if (search is not None and terms and terms not in memory.searched and search.index in view.numbers
            and rng.random() < 0.35 + 0.6 * shopper.tech_savvy):
        query = terms if shopper.mission == "replenish" or rng.random() < 0.7 else product_terms(terms)
        return Choice(search, query=query, thought=f"I'll just search for {query}.")
    link = _goal_link(page, shopper)
    if link is not None and page.kind != PageKind.CATEGORY:
        return Choice(link, thought="This section should have it.")
    menu = page.header.menu
    if menu.index in view.numbers and page.kind == PageKind.HOME and rng.random() < 0.6:
        return Choice(menu, thought="Where are the categories?")
    if scored and scored[0][0] > 0.05 and rng.random() < 0.5:
        best = scored[0][2]
        return Choice(best.open, thought=f"Maybe {best.product.name}?")
    if page.back is not None and rng.random() < 0.4:
        return Choice(page.back, thought="Not here. Back.")
    return Choice(leave, thought="I can't find what I want here.")


def _on_product(site: OnlineSite, shopper: OnlineShopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
    page = view.page
    assert page.detail is not None
    product = page.detail.product
    o = site.options
    add = _find(page, ActionKind.ADD_TO_CART)
    buy = _find(page, ActionKind.BUY_NOW)
    if any(view.cart_names) and product.name in view.cart_names and memory.satisfied:
        return Choice(page.header.cart, thought="It's in my cart. To checkout.")
    reviews = _find(page, ActionKind.READ_REVIEWS)
    if reviews is not None and shopper.mission in ("compare", "gift") and rng.random() < 0.6:
        return Choice(reviews, thought="What do other people say about it?")
    fit = relevance(shopper, product, site)
    left = _budget_left(site, shopper, view)
    affordable = left is None or product.price <= left
    base = {"purchase": 0.7, "replenish": 0.97, "gift": 0.25, "compare": 0.25, "browse": 0.015, "deal_hunt": 0.03}[shopper.mission]
    if shopper.mission in ("compare", "gift") and memory.views < memory.want_views:
        base = 0.0  # still looking around before deciding
    if shopper.mission == "deal_hunt":
        base += 0.3 if product.discount_percent >= 25 else 0.12 if product.discount_percent >= 15 else 0
    if shopper.mission == "browse" and product.discount_percent >= 20:
        base += 0.02
    pressure = 0.0
    if o.urgency and (product.stock is not None and 0 < product.stock <= 5 or product.discount_percent):
        pressure += 0.25 * (1.1 - shopper.tech_savvy)
    if o.social_proof and product.weekly_sales > 50:
        pressure += 0.1
    p_buy = min(0.97, base * fit ** 2 * (1.0 if shopper.mission == "replenish" else _rating_factor(product.rating))
                * (1 + pressure) * (1 + shopper.price_sensitivity * product.discount_percent / 80))
    if not affordable:
        p_buy *= 0.05
    if add is not None and rng.random() < p_buy:
        memory.satisfied = shopper.mission not in ("browse", "deal_hunt") or rng.random() < 0.6
        if buy is not None and (shopper.mission == "replenish" or rng.random() < 0.45):
            return Choice(buy, thought="That's the one. Buy it now.")
        return Choice(add, thought="Good price, good reviews. Into the cart.")
    memory.rejected.add(product.id)
    wish = _find(page, ActionKind.ADD_TO_WISHLIST)
    if wish is not None and shopper.mission in ("browse", "gift") and rng.random() < 0.2:
        return Choice(wish, thought="Maybe later. Saving it.")
    if not affordable:
        thought = "Too expensive for me."
    elif add is None:
        thought = "Sold out. Typical."
    elif shopper.mission in ("compare", "gift") and memory.views < memory.want_views:
        thought = "Let me see a few more before I decide."
    elif fit >= 0.9 and product.rating < 3.8:
        thought = "The reviews put me off."
    elif fit >= 0.9:
        thought = "Close, but I'm not convinced yet."
    else:
        thought = "Not quite what I'm looking for."
    similar = [c for grid in page.grids for c in grid.cards if c.product.id not in memory.rejected]
    if similar and shopper.mission in ("browse", "compare", "gift") and rng.random() < 0.35:
        choice = max(similar, key=lambda c: _appeal(site, shopper, c.product, view, rng))
        return Choice(choice.open, thought=f"{thought} What about {choice.product.name}?")
    if page.back is not None:
        return Choice(page.back, thought=thought)
    return Choice(page.header.home, thought=thought)


def _on_cart(site: OnlineSite, shopper: OnlineShopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
    page = view.page
    checkout = _find(page, ActionKind.CHECKOUT)
    if checkout is None:
        return Choice(page.leave if memory.steps and rng.random() < 0.5 else page.header.home, thought="My cart is empty.")
    coupon = _find(page, ActionKind.APPLY_COUPON)
    rejected = page.notice == "That code is not valid"
    if coupon is not None and not rejected and rng.random() < 0.35 + 0.5 * shopper.price_sensitivity:
        if view.state.coupon_known or site.options.coupon_public or rng.random() < 0.3:
            return Choice(coupon, thought="Let me try a coupon code first.")
    if rejected and rng.random() < 0.25 * shopper.price_sensitivity:
        return Choice(page.leave, thought="I'll go find a coupon code somewhere else.")
    # Extra costs seen in the cart are the most common reason to abandon it; impulse picks get second thoughts.
    totals = cart_totals(site, view.state.cart, view.state, at_review=False)
    hesitate = 0.04 + (0.05 + 0.2 * shopper.price_sensitivity if totals.shipping else 0.0)
    if shopper.mission in ("browse", "deal_hunt"):
        hesitate += 0.2
    elif shopper.mission == "replenish":
        hesitate *= 0.3  # a habit: they know what delivery costs
    if rng.random() < hesitate:
        thought = (f"{display_price(totals.shipping, site.currency)} just for delivery? No." if totals.shipping
                   else "I'll think about it and come back later.")
        return Choice(page.leave, thought=thought)
    if shopper.budget and view.cart_subtotal > shopper.budget * 1.3 and rng.random() < 0.5:
        return Choice(page.leave, thought="That adds up to more than I wanted to spend.")
    return Choice(checkout, thought="Checking out.")


def _on_sign_in(shopper: OnlineShopper, page: Page, rng: random.Random) -> Choice:
    sign_in = _find(page, ActionKind.SIGN_IN)
    if shopper.has_account and sign_in is not None and "No account" not in page.notice:
        return Choice(sign_in, thought="I have an account here.")
    guest = _find(page, ActionKind.GUEST_CHECKOUT)
    if guest is not None and rng.random() < 0.88:
        return Choice(guest, thought="Guest checkout. No need for another account.")
    create = _find(page, ActionKind.CREATE_ACCOUNT)
    if create is not None and rng.random() < (0.3 + 0.4 * shopper.tech_savvy) * (0.5 if guest is None else 1.0) + 0.15:
        return Choice(create, thought="Fine, I'll make an account.")
    return Choice(page.leave, thought="I'm not creating an account just to buy this.")


def _on_checkout(site: OnlineSite, shopper: OnlineShopper, view: StepView, rng: random.Random) -> Choice:
    page = view.page
    address = _find(page, ActionKind.ADD_ADDRESS)
    if address is not None:
        return Choice(address, thought="Typing in my address.")
    payments = _all(page, ActionKind.ADD_PAYMENT)
    if payments:
        method = _payment(site, shopper, page, rng)
        if method is None:
            return Choice(page.leave, thought="They don't take how I usually pay.")
        return Choice(method, thought=f"I'll pay with {method.action.label.removeprefix('Add payment: ')}.")
    addon = _find(page, ActionKind.REMOVE_ADDON)
    if addon is not None and rng.random() < 0.3 + 0.5 * shopper.price_sensitivity:
        return Choice(addon, thought="Wait, I never asked for a protection plan.")
    coupon = _find(page, ActionKind.APPLY_COUPON)
    if coupon is not None and site.options.coupon_public and rng.random() < 0.3 * shopper.price_sensitivity:
        return Choice(coupon, thought="Don't forget the coupon.")
    place = _find(page, ActionKind.PLACE_ORDER)
    if place is None:
        return Choice(page.back or page.leave, thought="Something is missing here.")
    # A fee first shown on the review (drip pricing) drives some away; a pre-ticked add-on nobody noticed is just paid.
    if site.options.service_fee > 0:
        p_leave = (0.05 + 0.25 * shopper.price_sensitivity) * (0.4 if shopper.mission == "replenish" else 1.0)
        if rng.random() < p_leave:
            return Choice(page.leave, thought="A service fee at the very end? Forget it.")
    if shopper.budget and view.cart_subtotal > shopper.budget * 1.25 and rng.random() < 0.5:
        return Choice(page.leave, thought="The total is more than I can spend.")
    return Choice(place, thought="Placing the order.")


class ModelPolicy:
    """A language or vision model picks the option. `vision`: it gets the screenshot (otherwise the page as text).
    A failed call (no valid answer after the retries) is decided by the rule shopper and recorded as a fallback."""

    def __init__(self, llm: SimLLM, *, vision: bool, max_tokens: int = 240, max_retries: int = 1) -> None:
        self.llm = llm
        self.vision = vision
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    async def choose(self, site: OnlineSite, shopper: OnlineShopper, view: StepView, memory: Memory,
                     rng: random.Random) -> Choice:
        by_number = {view.numbers[c.index]: c for c in view.page.active if c.index in view.numbers}
        search = view.page.header.search
        search_number = view.numbers.get(search.index) if search is not None else None
        schema = choice_model(sorted(by_number), search_number)
        prompt = user_prompt(
            site, shopper, page_title=view.page.title,
            options=[(n, by_number[n].action.label) for n in sorted(by_number)], history=memory.steps,
            elapsed=memory.elapsed, load_seconds=memory.last_load,
            cart=(view.cart_count, view.cart_subtotal, view.cart_names),
            outline=None if self.vision else view.outline,
        )
        try:
            if self.vision:
                answer = await self.llm.generate_structured_with_image_async(
                    schema, system_prompt(vision=True), prompt, view.image_url, max_retries=self.max_retries,
                    seed=view.seed, route=shopper.id, max_tokens=self.max_tokens)
            else:
                answer = await self.llm.generate_structured_async(
                    schema, system_prompt(vision=False), prompt, max_retries=self.max_retries, seed=view.seed,
                    route=shopper.id, max_tokens=self.max_tokens)
        except Exception as e:  # noqa: BLE001 — one failed call must not end the session; the rules decide this step
            fallback = decide(site, shopper, view, memory, rng)
            return Choice(fallback.control, fallback.query, fallback.thought, source="fallback",
                          error=f"{type(e).__name__}: {e}"[:300])
        control = by_number[answer.option]
        query = answer.search_text.strip() if control.action.kind == ActionKind.SEARCH else ""
        return Choice(control, query=query, thought=answer.thought.strip(), source="model")
