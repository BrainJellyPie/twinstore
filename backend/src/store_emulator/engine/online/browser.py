"""The browser: what a page of an online site shows, what can be clicked on it, and what a click does.

`build_page(site, state)` lays a page out as blocks (header, banner, product grids, panels, popups); every
clickable element is a `Control` holding the action it performs. `apply(site, state, action)` returns the browser
state after that action. Both are pure, so a recorded state always renders the page the shopper saw, and rules can
shop without drawing a single pixel.
"""

import hashlib
import math
import random
import re
from dataclasses import dataclass, field
from typing import Literal

from store_emulator.domain.online import (
    ActionKind,
    AdPlacement,
    BrowserState,
    CartLine,
    OnlineAction,
    OnlineProduct,
    OnlineSite,
    PageKind,
    PageRef,
    PaymentMethod,
    SortKey,
)
from store_emulator.engine.prompting import display_price

from .ads import active_ads

_HISTORY = 30
_RECENT = 12
_HOME_ROW = 4
_SORT_CHOICES: tuple[SortKey, ...] = ("price_asc", "rating", "newest", "price_desc")

PAYMENT_LABELS: dict[PaymentMethod, str] = {
    "card": "Credit or debit card", "paypal": "PayPal", "apple_pay": "Apple Pay",
    "bnpl": "Buy now, pay later (4 instalments)", "bank_transfer": "Bank transfer", "cash_on_delivery": "Cash on delivery",
}
SORT_LABELS: dict[SortKey, str] = {
    "featured": "Featured", "price_asc": "Price: low to high", "price_desc": "Price: high to low",
    "rating": "Top rated", "newest": "Newest",
}
_STOP_WORDS = frozenset({"a", "an", "the", "for", "of", "and", "or", "to", "in", "with", "on", "my", "some", "me",
                         "buy", "find", "need", "want", "new", "cheap", "best", "good"})

type LineStyle = Literal["title", "text", "muted", "price", "total", "alert", "good", "strong"]


@dataclass(frozen=True)
class Control:
    """One clickable element. `index` is its place in the page's reading order."""
    index: int
    action: OnlineAction


@dataclass(frozen=True)
class Card:
    product: OnlineProduct
    open: Control
    quick_add: Control | None = None
    sponsored: bool = False


@dataclass(frozen=True)
class Banner:
    headline: str
    small: str
    control: Control | None
    product: OnlineProduct | None = None  # an ad banner shows its product
    sponsored: bool = False


@dataclass(frozen=True)
class Grid:
    title: str
    cards: tuple[Card, ...]
    controls: tuple[Control, ...] = ()  # sorting and paging
    note: str = ""


@dataclass(frozen=True)
class Line:
    text: str
    style: LineStyle = "text"
    control: Control | None = None


@dataclass(frozen=True)
class Panel:
    title: str
    lines: tuple[Line, ...]
    chips: bool = False  # clickable lines drawn as a row of tiles (home page categories)


@dataclass(frozen=True)
class Detail:
    product: OnlineProduct
    breadcrumb: Control | None
    facts: tuple[Line, ...]
    buttons: tuple[Control, ...]
    reviews: tuple[Line, ...] = ()


@dataclass(frozen=True)
class Overlay:
    kind: Literal["menu", "welcome", "promo"]
    title: str
    lines: tuple[Line, ...]
    modal: bool
    product: OnlineProduct | None = None  # what a promo popup advertises


@dataclass(frozen=True)
class Header:
    home: Control
    search: Control | None
    menu: Control
    settings: Control
    cart: Control
    wishlist: Control | None
    cart_count: int
    account: str


@dataclass(frozen=True)
class Page:
    kind: PageKind
    url: str
    title: str
    device: Literal["desktop", "mobile"]
    large_text: bool
    theme: str
    site_name: str
    back: Control | None
    leave: Control
    header: Header
    nav: tuple[Control, ...] = ()
    notice: str = ""
    banner: Banner | None = None
    detail: Detail | None = None
    grids: tuple[Grid, ...] = ()
    panels: tuple[Panel, ...] = ()
    footer: tuple[Control, ...] = ()
    cookie: tuple[Control, Control] | None = None
    chat: bool = False
    overlay: Overlay | None = None
    trust: bool = False
    controls: tuple[Control, ...] = field(default=())

    @property
    def active(self) -> list[Control]:
        """Controls that can be used: all of them, or only the popup's (and closing the tab) while a modal is open."""
        if self.overlay is not None and self.overlay.modal:
            inside = {line.control.index for line in self.overlay.lines if line.control is not None}
            return [c for c in self.controls if c.index in inside or c.index == self.leave.index]
        return list(self.controls)

    @property
    def ads_shown(self) -> list[str]:
        """Ad campaigns on this page (their elements are visible, so each is one impression)."""
        visible = self.active if self.overlay is not None and self.overlay.modal else self.controls
        return sorted({c.action.ad_id for c in visible if c.action.ad_id})

    def products_shown(self) -> int:
        return sum(len(g.cards) for g in self.grids) + (1 if self.detail else 0)


class _Builder:
    def __init__(self) -> None:
        self.controls: list[Control] = []

    def __call__(self, kind: ActionKind, label: str, target: str = "", ad_id: str = "") -> Control:
        control = Control(len(self.controls), OnlineAction(kind=kind, target=target, label=label, ad_id=ad_id))
        self.controls.append(control)
        return control


# ── money ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Totals:
    subtotal: int
    discount: int
    shipping: int
    service_fee: int
    addon: int
    total: int


def cart_totals(site: OnlineSite, lines: list[CartLine], state: BrowserState, *, at_review: bool) -> Totals:
    """What the cart costs. The service fee and a pre-ticked add-on appear only on the order review, as on sites
    that reveal them last."""
    o = site.options
    subtotal = 0
    for line in lines:
        product = site.product(line.product_id)
        if product is not None:
            subtotal += product.price * line.quantity
    discount = round(subtotal * o.coupon_percent / 100) if state.coupon_applied and o.coupon_percent else 0
    goods = subtotal - discount
    free = o.free_shipping_threshold == 0 or goods >= o.free_shipping_threshold
    shipping = 0 if not lines or free else o.shipping_fee
    service = o.service_fee if at_review and lines else 0
    addon = (round(subtotal * o.preselected_addon_percent / 100)
             if at_review and lines and o.preselected_addon_percent and not state.addon_removed else 0)
    return Totals(subtotal, discount, shipping, service, addon, goods + shipping + service + addon)


def money(amount: int, site: OnlineSite) -> str:
    return display_price(amount, site.currency)


# ── catalog queries ────────────────────────────────────────────────────────────


def _words(text: str) -> list[str]:
    out: list[str] = []
    for raw in re.findall(r"[\w\-']+", text.lower()):
        word = raw.strip("-'")
        if len(word) > 3 and word.endswith("es") and not word.endswith("ses"):
            word = word[:-2]
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        if word:
            out.append(word)
    return out


def query_terms(query: str) -> list[str]:
    return [w for w in _words(query) if w not in _STOP_WORDS]


def search_products(site: OnlineSite, query: str) -> list[OnlineProduct]:
    """Products a search finds, best match first. "smart" matches words and word beginnings anywhere in the name,
    category and tags; "exact" only finds names containing the whole query, as a basic shop search does."""
    mode = site.options.search
    text = query.strip().lower()
    if mode == "off" or not text:
        return []
    if mode == "exact":
        return [p for p in site.products if text in p.name.lower()]
    terms = query_terms(query) or _words(query)
    if not terms:
        return []
    scored: list[tuple[float, int, OnlineProduct]] = []
    for order, product in enumerate(site.products):
        category = site.category(product.category_id)
        name_words = set(_words(product.name))
        other_words = set(_words(" ".join([category.name if category else "", *product.tags])))
        score = 0.0
        matched = 0
        for term in terms:
            if term in name_words or any(len(term) >= 3 and w.startswith(term) for w in name_words):
                score += 1.0
                matched += 1
            elif term in other_words or any(len(term) >= 3 and w.startswith(term) for w in other_words):
                score += 0.6
                matched += 1
        if matched >= max(1, len(terms) / 2):
            scored.append((score, order, product))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [p for _, _, p in scored]


def sort_products(products: list[OnlineProduct], sort: SortKey) -> list[OnlineProduct]:
    if sort == "price_asc":
        return sorted(products, key=lambda p: (p.price, p.id))
    if sort == "price_desc":
        return sorted(products, key=lambda p: (-p.price, p.id))
    if sort == "rating":
        return sorted(products, key=lambda p: (-p.rating, -p.reviews, p.id))
    if sort == "newest":
        return sorted(products, key=lambda p: ("new" not in p.badges, -int(p.id[1:]) if p.id[1:].isdigit() else 0))
    return list(products)


def _with_sponsored(site: OnlineSite, products: list[OnlineProduct]) -> tuple[list[OnlineProduct], set[str]]:
    """Up to `sponsored_slots` sponsored products of the list moved to the top, labelled as ads."""
    slots = site.options.sponsored_slots
    if slots <= 0:
        return products, set()
    ads = [p for p in products if "sponsored" in p.badges][:slots]
    ids = {p.id for p in ads}
    return ads + [p for p in products if p.id not in ids], ids


def listing(site: OnlineSite, ref: PageRef) -> list[OnlineProduct]:
    """All products of a category, search or deals page, in display order (before paging)."""
    sort = ref.sort or site.options.default_sort
    if ref.page == PageKind.SEARCH:
        found = search_products(site, ref.query)
        return found if sort == "featured" else sort_products(found, sort)
    if ref.page == PageKind.DEALS:
        deals = sorted((p for p in site.products if p.discount_percent > 0), key=lambda p: (-p.discount_percent, p.id))
        return deals if sort == "featured" else sort_products(deals, sort)
    products = [p for p in site.products if p.category_id == ref.category_id]
    return sort_products(products, sort)


def page_count(site: OnlineSite, total: int) -> int:
    return max(1, math.ceil(total / site.options.products_per_page))


# ── labels ─────────────────────────────────────────────────────────────────────


def product_label(site: OnlineSite, p: OnlineProduct, *, sponsored: bool = False) -> str:
    bits = [money(p.price, site)]
    if p.discount_percent:
        bits.append(f"was {money(p.list_price, site)}, -{p.discount_percent}%")
    if site.options.show_ratings:
        bits.append(f"{p.rating:.1f} stars" + (f", {p.reviews:,} reviews" if site.options.show_review_counts else ""))
    if p.stock == 0:
        bits.append("sold out")
    if sponsored:
        bits.append("sponsored")
    return f"Open product: {p.name} ({'; '.join(bits)})"


def _shipping_line(site: OnlineSite) -> str:
    o = site.options
    if o.free_shipping_threshold == 0 or o.shipping_fee == 0:
        return "Free delivery on every order"
    return f"Delivery {money(o.shipping_fee, site)}, free over {money(o.free_shipping_threshold, site)}"


def _returns_line(site: OnlineSite) -> str:
    return {"free_30": "Free returns within 30 days", "paid": f"Returns cost {money(site.options.shipping_fee, site)}",
            "hidden": ""}[site.options.return_policy]


def _urgency(p: OnlineProduct, seed: str) -> str:
    if p.stock is not None and 0 < p.stock <= 5:
        return f"Only {p.stock} left - order soon"
    rng = random.Random(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16))
    if p.discount_percent:
        return f"Sale ends in {rng.randint(1, 9):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
    return f"{rng.randint(3, 40)} people are looking at this right now"


def slug(site: OnlineSite) -> str:
    text = re.sub(r"[^a-z0-9]+", "", site.name.lower())
    return text or site.id.lower().replace("_", "")


def page_url(site: OnlineSite, ref: PageRef) -> str:
    base = f"https://www.{slug(site)}.shop"
    query = f"?sort={ref.sort}" if ref.sort else ""
    if ref.page_index:
        query += ("&" if query else "?") + f"page={ref.page_index + 1}"
    paths: dict[PageKind, str] = {
        PageKind.HOME: "/", PageKind.CATEGORY: f"/c/{ref.category_id}", PageKind.DEALS: "/deals",
        PageKind.SEARCH: "/search", PageKind.PRODUCT: f"/p/{ref.product_id}", PageKind.CART: "/cart",
        PageKind.SIGN_IN: "/account/sign-in", PageKind.CHECKOUT: f"/checkout/{ref.checkout_step}",
        PageKind.ORDER_COMPLETE: "/checkout/thank-you", PageKind.WISHLIST: "/wishlist", PageKind.HELP: "/help",
        PageKind.SETTINGS: "/settings",
    }
    if ref.page == PageKind.SEARCH:
        q = re.sub(r"\s+", "+", ref.query.strip())
        query = f"?q={q}" + (query.replace("?", "&", 1) if query else "")
    return base + paths[ref.page] + query


# ── page layout ────────────────────────────────────────────────────────────────


def _can_add(state: BrowserState, product: OnlineProduct) -> bool:
    limit = min(99, product.stock) if product.stock is not None else 99
    return sum(line.quantity for line in state.cart if line.product_id == product.id) < limit


def _cards(site: OnlineSite, state: BrowserState, products: list[OnlineProduct], ctl: _Builder,
           sponsored: set[str] | None = None, ad_id: str = "") -> tuple[Card, ...]:
    """Product tiles, optionally belonging to one campaign with attributed clicks."""
    cards: list[Card] = []
    for p in products:
        is_ad = bool(ad_id) or (sponsored is not None and p.id in sponsored)
        label = product_label(site, p, sponsored=is_ad)
        open_control = ctl(ActionKind.OPEN_PRODUCT, f"Ad · {label}" if ad_id else label, p.id, ad_id)
        quick = (ctl(ActionKind.ADD_TO_CART, f"Add to cart: {p.name} ({money(p.price, site)})", p.id, ad_id)
                 if site.options.quick_add and _can_add(state, p) else None)
        cards.append(Card(p, open_control, quick, is_ad))
    return tuple(cards)


def _popular(site: OnlineSite, exclude: set[str] | None = None, limit: int = _HOME_ROW) -> list[OnlineProduct]:
    skip = exclude or set()
    ranked = sorted((p for p in site.products if p.id not in skip), key=lambda p: (-p.weekly_sales, p.id))
    return ranked[:limit]


def _ad_grid(site: OnlineSite, state: BrowserState, ctl: _Builder, placement: AdPlacement, title: str,
             keep: set[str] | None = None, exclude: str = "") -> Grid | None:
    """A sponsored row of one placement's ads (only products in `keep`, when given)."""
    ads = [ad for ad in active_ads(site, placement)
           if ad.product_id != exclude and (keep is None or ad.product_id in keep)][:_HOME_ROW]
    cards = tuple(card for ad in ads if (product := site.product(ad.product_id)) is not None
                  for card in _cards(site, state, [product], ctl, ad_id=ad.id))
    if not cards:
        return None
    return Grid(title, cards)


def _listing_grid(site: OnlineSite, state: BrowserState, ctl: _Builder, title: str,
                  products: list[OnlineProduct] | None = None) -> Grid:
    ref = state.at
    if products is None:
        products, ads = _with_sponsored(site, listing(site, ref))
    else:
        products = sort_products(products, ref.sort or site.options.default_sort)
        ads = set[str]()
    per = site.options.products_per_page
    pages = page_count(site, len(products))
    index = min(ref.page_index, pages - 1)
    shown = products[index * per:(index + 1) * per]
    current = ref.sort or site.options.default_sort
    controls: list[Control] = []
    if len(products) > 1:
        for sort_key in _SORT_CHOICES:
            if sort_key != current:
                controls.append(ctl(ActionKind.SORT, f"Sort by {SORT_LABELS[sort_key].lower()}", sort_key))
    if index > 0:
        controls.append(ctl(ActionKind.PREVIOUS_PAGE, f"Previous page (page {index} of {pages})"))
    if index + 1 < pages:
        controls.append(ctl(ActionKind.NEXT_PAGE, f"Next page (page {index + 2} of {pages})"))
    note = (f"{len(products)} results · page {index + 1} of {pages} · sorted by {SORT_LABELS[current].lower()}"
            if products else "")
    return Grid(title, _cards(site, state, shown, ctl, ads), tuple(controls), note)


def _home(site: OnlineSite, state: BrowserState, ctl: _Builder) -> tuple[Banner | None, list[Grid], list[Panel]]:
    o = site.options
    banner: Banner | None = None
    hero = active_ads(site, "hero_banner")
    advertised = site.product(hero[0].product_id) if hero else None
    if hero and advertised is not None:
        ad = hero[0]
        cta = ctl(ActionKind.OPEN_PRODUCT, f"Ad · banner: {ad.headline or advertised.name} ({money(advertised.price, site)})",
                  advertised.id, ad.id)
        banner = Banner(ad.headline or advertised.name, f"{advertised.name} · {money(advertised.price, site)}", cta,
                        advertised, sponsored=True)
    elif o.hero_banner:
        has_deals = any(p.discount_percent for p in site.products)
        cta = (ctl(ActionKind.OPEN_DEALS, "Banner: shop today's deals") if has_deals
               else ctl(ActionKind.OPEN_CATEGORY, f"Banner: shop {site.categories[0].name}", site.categories[0].id))
        small = (f"Use code {o.coupon_code} for {o.coupon_percent}% off" if o.coupon_code and o.coupon_percent
                 and o.coupon_public else _shipping_line(site))
        banner = Banner(o.hero_text or site.tagline or site.name, small, cta)
    grids: list[Grid] = []
    panels: list[Panel] = []
    used: set[str] = set()
    tiles = _ad_grid(site, state, ctl, "home_tile", "Sponsored")
    if tiles is not None:
        grids.append(tiles)
    for section in o.home_sections:
        if section == "categories":
            panels.append(Panel("Shop by category", tuple(
                Line(c.name, "strong", ctl(ActionKind.OPEN_CATEGORY, f"Category: {c.name}", c.id)) for c in site.categories),
                chips=True))
            continue
        if section == "bestsellers":
            products, title = _popular(site, used), "Best sellers"
        elif section == "deals":
            products = sorted((p for p in site.products if p.discount_percent and p.id not in used),
                              key=lambda p: (-p.discount_percent, p.id))[:_HOME_ROW]
            title = "Today's deals"
        elif section == "new":
            products = [p for p in site.products if "new" in p.badges and p.id not in used][:_HOME_ROW]
            title = "New arrivals"
        else:
            seen = [site.product(pid) for pid in state.viewed]
            liked = {p.category_id for p in seen if p is not None}
            pool = [p for p in site.products if p.category_id in liked and p.id not in used and p.id not in state.viewed]
            products = sorted(pool, key=lambda p: (-p.rating, p.id))[:_HOME_ROW] or _popular(site, used | set(state.viewed))
            title = "Recommended for you"
        if products:
            used |= {p.id for p in products}
            grids.append(Grid(title, _cards(site, state, products, ctl)))
    return banner, grids, panels


def _detail(site: OnlineSite, state: BrowserState, ctl: _Builder) -> tuple[Detail | None, list[Grid]]:
    p = site.product(state.at.product_id)
    if p is None:
        return None, []
    o = site.options
    category = site.category(p.category_id)
    crumb = ctl(ActionKind.OPEN_CATEGORY, f"Category: {category.name}", category.id) if category else None
    facts: list[Line] = []
    if o.show_ratings:
        facts.append(Line(f"{p.rating:.1f} out of 5 stars" + (f" · {p.reviews:,} reviews" if o.show_review_counts else "")))
    price = money(p.price, site)
    if p.discount_percent:
        facts.append(Line(f"{price}   was {money(p.list_price, site)}   -{p.discount_percent}%", "price"))
    else:
        facts.append(Line(price, "price"))
    if p.stock == 0:
        facts.append(Line("Sold out", "alert"))
    elif p.stock is not None and p.stock <= 5:
        facts.append(Line(f"In stock: {p.stock} left", "alert" if o.urgency else "muted"))
    else:
        facts.append(Line("In stock", "good"))
    if o.urgency and p.stock != 0:
        facts.append(Line(_urgency(p, site.id + p.id), "alert"))
    if o.social_proof and p.weekly_sales:
        facts.append(Line(f"{p.weekly_sales:,} bought this week", "strong"))
    facts.append(Line(_shipping_line(site), "muted"))
    returns = _returns_line(site)
    if returns:
        facts.append(Line(returns, "muted"))
    if p.description:
        facts.append(Line(p.description))
    buttons: list[Control] = []
    if p.stock != 0:
        if _can_add(state, p):
            buttons.append(ctl(ActionKind.ADD_TO_CART, f"Add to cart: {p.name} ({price})", p.id))
        if o.one_click_buy:
            buttons.append(ctl(ActionKind.BUY_NOW, f"Buy now: {p.name} ({price})", p.id))
    if o.wishlist and p.id not in state.wishlist:
        buttons.append(ctl(ActionKind.ADD_TO_WISHLIST, "Save to wishlist", p.id))
    reviews: list[Line] = []
    if o.reviews_on_product and p.reviews:
        if state.reviews_open:
            reviews = [Line(t, "muted") for t in review_snippets(p)]
        else:
            buttons.append(ctl(ActionKind.READ_REVIEWS, f"Read reviews ({p.reviews:,})", p.id))
    grids: list[Grid] = []
    cross = _ad_grid(site, state, ctl, "product_page", "Sponsored products", exclude=p.id)
    if cross is not None:
        grids.append(cross)
    if o.recommendations != "none":
        if o.recommendations == "similar":
            pool = [x for x in site.products if x.category_id == p.category_id and x.id != p.id]
            similar = sorted(pool, key=lambda x: (-x.rating, x.id))[:_HOME_ROW]
            title = "Similar items"
        else:
            similar, title = _popular(site, {p.id}), "Customers also bought"
        if similar:
            grids.append(Grid(title, _cards(site, state, similar, ctl)))
    return Detail(p, crumb, tuple(facts), tuple(buttons), tuple(reviews)), grids


def review_snippets(p: OnlineProduct) -> list[str]:
    rng = random.Random(int(hashlib.md5(p.id.encode() + p.name.encode()).hexdigest()[:8], 16))
    good = ("Exactly as described, would buy again.", "Great quality for the price.", "Arrived fast and well packed.",
            "My family loves it.", "Better than I expected.")
    mixed = ("Decent, but smaller than I thought.", "Works fine, packaging could be better.", "Good, not great.")
    bad = ("Stopped working after a week.", "Not worth the money.", "Arrived damaged, returned it.")
    out: list[str] = []
    for _ in range(3):
        stars = min(5, max(1, round(rng.gauss(p.rating, 0.9))))
        pool = good if stars >= 4 else mixed if stars == 3 else bad
        out.append(f"{'★' * stars}{'☆' * (5 - stars)}  {rng.choice(pool)}")
    return out


def _cart(site: OnlineSite, state: BrowserState, ctl: _Builder) -> list[Panel]:
    o = site.options
    if not state.cart:
        return [Panel("Your cart is empty", (Line("Find something you like and add it here.", "muted"),
                                            Line("Continue shopping", "strong", ctl(ActionKind.HOME, "Continue shopping"))))]
    items = [(item, p) for item in state.cart if (p := site.product(item.product_id)) is not None]
    per = o.products_per_page
    pages = page_count(site, len(items))
    index = min(state.at.page_index, pages - 1)
    lines: list[Line] = []
    if pages > 1:
        lines.append(Line(f"{len(items)} products · page {index + 1} of {pages}", "muted"))
    if index > 0:
        label = f"Previous page (page {index} of {pages})"
        lines.append(Line(label, "text", ctl(ActionKind.PREVIOUS_PAGE, label)))
    if index + 1 < pages:
        label = f"Next page (page {index + 2} of {pages})"
        lines.append(Line(label, "text", ctl(ActionKind.NEXT_PAGE, label)))
    for item, p in items[index * per:(index + 1) * per]:
        lines.append(Line(f"{p.name}  ×{item.quantity}   {money(p.price * item.quantity, site)}", "strong"))
        if _can_add(state, p):
            lines.append(Line("+ one more", "muted", ctl(ActionKind.INCREASE_QUANTITY, f"Add one more: {p.name}", p.id)))
        lines.append(Line("Remove", "muted", ctl(ActionKind.REMOVE_FROM_CART, f"Remove from cart: {p.name}", p.id)))
    t = cart_totals(site, state.cart, state, at_review=False)
    summary = [Line(f"Subtotal: {money(t.subtotal, site)}")]
    if t.discount:
        summary.append(Line(f"Coupon {o.coupon_code}: -{money(t.discount, site)}", "good"))
    elif o.coupon_code and o.coupon_percent:
        summary.append(Line("Have a coupon code?", "muted", ctl(ActionKind.APPLY_COUPON, "Apply a coupon code")))
    summary.append(Line("Delivery: free" if t.shipping == 0 else f"Delivery: {money(t.shipping, site)}"))
    if t.shipping and o.free_shipping_threshold:
        gap = o.free_shipping_threshold - (t.subtotal - t.discount)
        summary.append(Line(f"Add {money(gap, site)} more for free delivery", "muted"))
    in_cart = {line.product_id for line in state.cart}
    for ad in active_ads(site, "cart_upsell"):
        extra = site.product(ad.product_id)
        if extra is not None and extra.id not in in_cart and _can_add(state, extra):
            price = money(extra.price, site)
            summary.append(Line(f"Sponsored: {extra.name} · {price}", "muted"))
            summary.append(Line("Add to order", "text", ctl(ActionKind.ADD_TO_CART,
                                                            f"Ad · add {extra.name} ({price}) to the order", extra.id, ad.id)))
            break
    summary.append(Line(f"Total: {money(t.total, site)}", "total"))
    summary.append(Line("Proceed to checkout", "strong", ctl(ActionKind.CHECKOUT, f"Proceed to checkout ({money(t.total, site)})")))
    summary.append(Line("Continue shopping", "muted", ctl(ActionKind.HOME, "Continue shopping")))
    return [Panel("Your cart", tuple(lines)), Panel("Order summary", tuple(summary))]


def _sign_in(site: OnlineSite, ctl: _Builder) -> list[Panel]:
    lines = [Line("Sign in to your account", "strong", ctl(ActionKind.SIGN_IN, "Sign in to an existing account")),
             Line("New here? Create an account (name, email, password)", "text",
                  ctl(ActionKind.CREATE_ACCOUNT, "Create a new account"))]
    if site.options.guest_checkout:
        lines.append(Line("Continue as a guest", "text", ctl(ActionKind.GUEST_CHECKOUT, "Check out as a guest")))
    else:
        lines.append(Line("An account is required to check out.", "alert"))
    return [Panel("Sign in or check out", tuple(lines))]


def _review_lines(site: OnlineSite, state: BrowserState, ctl: _Builder) -> list[Line]:
    o = site.options
    t = cart_totals(site, state.cart, state, at_review=True)
    lines = [Line(f"Items: {money(t.subtotal, site)}")]
    if t.discount:
        lines.append(Line(f"Coupon: -{money(t.discount, site)}", "good"))
    elif o.coupon_code and o.coupon_percent:
        lines.append(Line("Have a coupon code?", "muted", ctl(ActionKind.APPLY_COUPON, "Apply a coupon code")))
    lines.append(Line("Delivery: free" if t.shipping == 0 else f"Delivery: {money(t.shipping, site)}"))
    if t.service_fee:
        lines.append(Line(f"Service fee: {money(t.service_fee, site)}"))
    if t.addon:
        lines.append(Line(f"[x] Protection plan: {money(t.addon, site)}", "text",
                          ctl(ActionKind.REMOVE_ADDON, f"Untick the protection plan (-{money(t.addon, site)})")))
    lines.append(Line(f"Order total: {money(t.total, site)}", "total"))
    return lines


def _checkout(site: OnlineSite, state: BrowserState, ctl: _Builder) -> list[Panel]:
    """Controls are made only for what the step shows: every control is an option the shopper can see."""
    o = site.options
    if not state.cart:
        return [Panel("Your cart is empty", (Line("Continue shopping", "strong", ctl(ActionKind.HOME, "Continue shopping")),))]

    def address() -> Line:
        return (Line("Delivery address saved", "good") if state.address_added
                else Line("Add a delivery address", "strong", ctl(ActionKind.ADD_ADDRESS, "Add a delivery address")))

    def payment() -> list[Line]:
        if state.payment_method:
            return [Line(f"Paying with {PAYMENT_LABELS[state.payment_method]}", "good")]
        return [Line(f"Pay with {PAYMENT_LABELS[m]}", "text", ctl(ActionKind.ADD_PAYMENT, f"Add payment: {PAYMENT_LABELS[m]}", m))
                for m in o.payment_methods]

    def place() -> Line:
        total = cart_totals(site, state.cart, state, at_review=True).total
        return Line("Place order", "strong", ctl(ActionKind.PLACE_ORDER, f"Place order ({money(total, site)})"))

    if o.checkout_flow == "one_page":
        lines = [address(), *payment(), *_review_lines(site, state, ctl)]
        if state.address_added and state.payment_method:
            lines.append(place())
        else:
            lines.append(Line("Add an address and a payment method to place the order", "muted"))
        return [Panel("Checkout", tuple(lines))]
    progress = Line("1 Address  ›  2 Payment  ›  3 Review", "muted")
    step = state.at.checkout_step
    if step == "address":
        return [Panel("Checkout: delivery address", (progress, address()))]
    if step == "payment":
        return [Panel("Checkout: payment", (progress, *payment()))]
    return [Panel("Checkout: review your order", (progress, *_review_lines(site, state, ctl), place()))]


def _info(site: OnlineSite, state: BrowserState, ctl: _Builder) -> list[Panel]:
    kind = state.at.page
    if kind == PageKind.ORDER_COMPLETE:
        return [Panel("Thank you for your order!", (
            Line(f"Order {state.order_id} is confirmed.", "strong"),
            Line(f"Total paid: {money(state.order_total, site)}", "total"),
            Line("It arrives in 2–4 days. A receipt is on its way to your inbox.", "muted"),
            Line("Continue shopping", "strong", ctl(ActionKind.HOME, "Continue shopping")),
        ))]
    if kind == PageKind.HELP:
        lines = [Line(_shipping_line(site)), Line(_returns_line(site) or "See our terms for returns.", "muted"),
                 Line("Secure checkout, we never store your card number.", "muted"),
                 Line("Back to the shop", "strong", ctl(ActionKind.HOME, "Back to the home page"))]
        return [Panel("Delivery and returns", tuple(lines))]
    large = state.large_text if state.text_size_changed else state.large_text or site.options.large_text
    return [Panel("Settings", (
        Line(f"Text size: {'large' if large else 'normal'}", "strong",
             ctl(ActionKind.TOGGLE_LARGE_TEXT, "Use normal text" if large else "Use large text")),
        Line(f"Currency: {site.currency}", "muted"),
        Line("Email offers: off", "muted"),
        Line("Back to the shop", "strong", ctl(ActionKind.HOME, "Back to the home page")),
    ))]


def _menu(site: OnlineSite, ctl: _Builder) -> Overlay:
    lines = [Line(c.name, "strong", ctl(ActionKind.OPEN_CATEGORY, f"Menu: {c.name}", c.id)) for c in site.categories]
    if any(p.discount_percent for p in site.products):
        lines.append(Line("Deals", "strong", ctl(ActionKind.OPEN_DEALS, "Menu: deals")))
    if site.options.wishlist:
        lines.append(Line("Wishlist", "text", ctl(ActionKind.OPEN_WISHLIST, "Menu: my wishlist")))
    lines.append(Line("Delivery and returns", "text", ctl(ActionKind.OPEN_HELP, "Menu: delivery and returns")))
    lines.append(Line("Settings", "text", ctl(ActionKind.OPEN_SETTINGS, "Menu: settings")))
    lines.append(Line("Close menu", "muted", ctl(ActionKind.CLOSE_MENU, "Close the menu")))
    return Overlay("menu", "Menu", tuple(lines), modal=True)


def _welcome(site: OnlineSite, ctl: _Builder) -> Overlay:
    o = site.options
    percent = o.coupon_percent or 10
    if o.welcome_popup == "newsletter":
        title, body, accept = (f"Get {percent}% off your first order", "Join our newsletter for offers and new arrivals.",
                               "Sign up for the newsletter")
    else:
        title, body, accept = (f"A gift for you: {percent}% off", f"Use code {o.coupon_code or 'WELCOME'} at checkout today.",
                               "Claim the offer")
    return Overlay("welcome", title, (
        Line(body),
        Line(accept, "strong", ctl(ActionKind.ACCEPT_POPUP, f"Popup: {accept.lower()}")),
        Line("No thanks", "muted", ctl(ActionKind.CLOSE_POPUP, "Popup: no thanks, close it")),
    ), modal=True)


def _promo(site: OnlineSite, ctl: _Builder) -> Overlay | None:
    ads = active_ads(site, "popup")
    product = site.product(ads[0].product_id) if ads else None
    if not ads or product is None:
        return None
    ad = ads[0]
    return Overlay("promo", ad.headline or f"Today only: {product.name}", (
        Line(f"{product.name} · {money(product.price, site)}", "strong"),
        Line("View the offer", "strong", ctl(ActionKind.OPEN_PRODUCT, f"Ad · popup: view {product.name}", product.id, ad.id)),
        Line("No thanks", "muted", ctl(ActionKind.CLOSE_POPUP, "Popup: no thanks, close it")),
    ), modal=True, product=product)


def build_page(site: OnlineSite, state: BrowserState) -> Page:
    o = site.options
    ref = state.at
    ctl = _Builder()
    device = o.device or state.device
    back = ctl(ActionKind.BACK, "Browser back button") if state.history else None
    leave = ctl(ActionKind.LEAVE, "Close the tab and leave the site")
    count = sum(line.quantity for line in state.cart)
    header = Header(
        home=ctl(ActionKind.HOME, f"Logo: {site.name} home page"),
        search=ctl(ActionKind.SEARCH, "Search box: type words to search the shop") if o.search != "off" else None,
        menu=ctl(ActionKind.OPEN_MENU, "Menu button (all categories)"),
        settings=ctl(ActionKind.OPEN_SETTINGS, "Settings button"),
        cart=ctl(ActionKind.OPEN_CART, f"Cart button ({count} item{'s' if count != 1 else ''})"),
        wishlist=ctl(ActionKind.OPEN_WISHLIST, f"Wishlist ({len(state.wishlist)})") if o.wishlist and device == "desktop" else None,
        cart_count=count,
        account="Signed in" if state.signed_in else "Guest" if state.guest else "Sign in",
    )
    nav: tuple[Control, ...] = ()
    if device == "desktop" and ref.page not in (PageKind.CHECKOUT, PageKind.SIGN_IN):
        links = [ctl(ActionKind.OPEN_CATEGORY, f"Top menu: {c.name}", c.id) for c in site.categories[:8]]
        if any(p.discount_percent for p in site.products):
            links.append(ctl(ActionKind.OPEN_DEALS, "Top menu: deals"))
        nav = tuple(links)
    banner = None
    detail = None
    grids: list[Grid] = []
    panels: list[Panel] = []
    title = site.name
    if ref.page == PageKind.HOME:
        banner, grids, panels = _home(site, state, ctl)
    elif ref.page == PageKind.CATEGORY:
        category = site.category(ref.category_id)
        title = category.name if category else "Category"
        keep = {p.id for p in site.products if p.category_id == ref.category_id}
        strip = _ad_grid(site, state, ctl, "sponsored_listing", "Sponsored", keep=keep) if ref.page_index == 0 else None
        grids = [g for g in (strip, _listing_grid(site, state, ctl, title)) if g is not None]
    elif ref.page == PageKind.DEALS:
        title = "Deals"
        keep = {p.id for p in site.products if p.discount_percent}
        strip = _ad_grid(site, state, ctl, "sponsored_listing", "Sponsored", keep=keep) if ref.page_index == 0 else None
        grids = [g for g in (strip, _listing_grid(site, state, ctl, "Today's deals")) if g is not None]
    elif ref.page == PageKind.SEARCH:
        title = f'Results for "{ref.query}"'
        found = {p.id for p in search_products(site, ref.query)}
        strip = _ad_grid(site, state, ctl, "sponsored_listing", "Sponsored", keep=found) if ref.page_index == 0 else None
        grid = _listing_grid(site, state, ctl, title)
        if not grid.cards:
            grid = Grid(title, (), (), f'No products match "{ref.query}". Check the spelling or try other words.')
        grids = [strip, grid] if strip is not None else [grid]
    elif ref.page == PageKind.PRODUCT:
        detail, grids = _detail(site, state, ctl)
        title = detail.product.name if detail else "Product not found"
    elif ref.page == PageKind.CART:
        title, panels = "Cart", _cart(site, state, ctl)
    elif ref.page == PageKind.SIGN_IN:
        title, panels = "Sign in", _sign_in(site, ctl)
    elif ref.page == PageKind.CHECKOUT:
        title, panels = "Checkout", _checkout(site, state, ctl)
    elif ref.page == PageKind.WISHLIST:
        title = "Wishlist"
        saved = [p for p in (site.product(pid) for pid in state.wishlist) if p is not None]
        grids = ([_listing_grid(site, state, ctl, "Your wishlist", saved)] if saved else
                 [Grid("Your wishlist", (), (), "Nothing saved yet.")])
    else:
        title = {PageKind.ORDER_COMPLETE: "Order confirmed", PageKind.HELP: "Delivery and returns"}.get(ref.page, "Settings")
        panels = _info(site, state, ctl)
    footer = (ctl(ActionKind.OPEN_HELP, "Footer: delivery and returns"),) if ref.page != PageKind.HELP else ()
    cookie = ((ctl(ActionKind.ACCEPT_COOKIES, "Cookie banner: accept all"),
               ctl(ActionKind.REJECT_COOKIES, "Cookie banner: reject non-essential"))
              if o.cookie_banner and not state.cookies_answered else None)
    overlay = (_menu(site, ctl) if state.overlay == "menu" else _welcome(site, ctl) if state.overlay == "welcome"
               else _promo(site, ctl) if state.overlay == "promo" else None)
    return Page(
        kind=ref.page, url=page_url(site, ref), title=f"{title} | {site.name}" if title != site.name else site.name,
        device=device, large_text=state.large_text if state.text_size_changed else state.large_text or o.large_text,
        theme=o.theme_color, site_name=site.name,
        back=back, leave=leave, header=header, nav=nav, notice=state.notice, banner=banner, detail=detail,
        grids=tuple(grids), panels=tuple(panels), footer=footer, cookie=cookie, chat=o.chat_widget, overlay=overlay,
        trust=o.trust_badges and ref.page in (PageKind.CART, PageKind.CHECKOUT, PageKind.PRODUCT),
        controls=tuple(ctl.controls),
    )


def numbering(page: Page, mark_seed: int = 0) -> dict[int, int]:
    """Badge number of every usable control (by control index): reading order, or a seeded shuffle so that a model's
    liking for low numbers does not look like a liking for what happens to come first."""
    active = page.active
    numbers = list(range(1, len(active) + 1))
    if mark_seed:
        random.Random(mark_seed).shuffle(numbers)
    return {control.index: number for control, number in zip(active, numbers, strict=True)}


def outline(page: Page, site: OnlineSite) -> list[str]:
    """The page as text, top to bottom: what a screen reader (or the text policy) gets instead of the picture."""
    out = [f"Page: {page.title}", f"Address: {page.url}"]
    if page.notice:
        out.append(f"Message: {page.notice}")
    if page.overlay is not None:
        out.append(f"{'Sponsored popup' if page.overlay.kind == 'promo' else 'Popup' if page.overlay.modal else 'Open drawer'}: "
                   f"{page.overlay.title}")
        out.extend(f"  {line.text}" for line in page.overlay.lines if line.control is None)
    if page.banner is not None:
        out.append(f"{'Sponsored banner' if page.banner.sponsored else 'Banner'}: {page.banner.headline} — {page.banner.small}")
    if page.detail is not None:
        d = page.detail
        out.append(f"Product: {d.product.name}")
        out.extend(f"  {line.text}" for line in d.facts)
        out.extend(f"  Review: {line.text}" for line in d.reviews)
    for grid in page.grids:
        out.append(f"Section: {grid.title}" + (f" ({grid.note})" if grid.note else ""))
        for card in grid.cards:
            p = card.product
            extras = [b for b in p.badges if b != "sponsored"]
            if site.options.urgency and p.stock is not None and 0 < p.stock <= 5:
                extras.append(f"only {p.stock} left")
            if site.options.social_proof and p.weekly_sales:
                extras.append(f"{p.weekly_sales} bought this week")
            out.append(f"  - {card.open.action.label.removeprefix('Open product: ')}" + (f" [{', '.join(extras)}]" if extras else ""))
    for panel in page.panels:
        out.append(f"Section: {panel.title}")
        out.extend(f"  {line.text}" for line in panel.lines if line.control is None)
    if page.cookie is not None:
        out.append("Cookie banner at the bottom of the page")
    return out


# ── actions ────────────────────────────────────────────────────────────────────


def initial_state(site: OnlineSite, *, device: Literal["desktop", "mobile"] = "desktop", signed_in: bool = False) -> BrowserState:
    """The landing page; a welcome popup (or else an ad popup) opens over it when the site has one."""
    popup = site.options.welcome_popup != "none"
    promo = bool(active_ads(site, "popup"))
    return BrowserState(device=device, overlay="welcome" if popup else "promo" if promo else "none", welcome_seen=popup,
                        signed_in=signed_in)


def _go(state: BrowserState, ref: PageRef) -> BrowserState:
    history = [*state.history, state.at][-_HISTORY:]
    return state.model_copy(update={"at": ref, "history": history, "overlay": "none", "reviews_open": False})


def _add(state: BrowserState, product: OnlineProduct) -> list[CartLine]:
    cart = [line.model_copy() for line in state.cart]
    if not _can_add(state, product):
        return cart
    for line in cart:
        if line.product_id == product.id:
            line.quantity += 1
            return cart
    return [*cart, CartLine(product_id=product.id)]


def _to_checkout(site: OnlineSite, state: BrowserState) -> BrowserState:
    if not (state.signed_in or state.guest):
        return _go(state, PageRef(page=PageKind.SIGN_IN))
    step = "review" if state.address_added and state.payment_method else "payment" if state.address_added else "address"
    return _go(state, PageRef(page=PageKind.CHECKOUT, checkout_step=step))


def order_id(site: OnlineSite, state: BrowserState) -> str:
    text = site.id + "|" + "|".join(f"{line.product_id}x{line.quantity}" for line in state.cart) + f"|{len(state.history)}"
    return "ORD-" + hashlib.sha1(text.encode()).hexdigest()[:8].upper()


def apply(
    site: OnlineSite, state: BrowserState, action: OnlineAction, *, query: str = "", has_account: bool = False,
) -> BrowserState:
    """The browser state after `action`. `query` is what was typed for a search; `has_account` says whether signing
    in can succeed."""
    state = state.model_copy(update={"notice": ""})
    kind, target = action.kind, action.target
    o = site.options
    if kind == ActionKind.LEAVE:
        return state
    if kind == ActionKind.BACK:
        if not state.history:
            return state
        return state.model_copy(update={"at": state.history[-1], "history": state.history[:-1], "overlay": "none",
                                        "reviews_open": False})
    if kind == ActionKind.HOME:
        return _go(state, PageRef(page=PageKind.HOME))
    if kind == ActionKind.SEARCH:
        text = " ".join(query.split())[:60]
        if not text or o.search == "off":
            return state.model_copy(update={"notice": "Type something to search for"})
        return _go(state, PageRef(page=PageKind.SEARCH, query=text))
    if kind == ActionKind.OPEN_CATEGORY:
        return _go(state, PageRef(page=PageKind.CATEGORY, category_id=target)) if site.category(target) else state
    if kind == ActionKind.OPEN_DEALS:
        return _go(state, PageRef(page=PageKind.DEALS))
    if kind == ActionKind.OPEN_PRODUCT:
        if site.product(target) is None:
            return state
        moved = _go(state, PageRef(page=PageKind.PRODUCT, product_id=target))
        viewed = [pid for pid in moved.viewed if pid != target][-(_RECENT - 1):] + [target]
        return moved.model_copy(update={"viewed": viewed})
    if kind == ActionKind.OPEN_MENU:
        return state.model_copy(update={"overlay": "menu"})
    if kind == ActionKind.CLOSE_MENU:
        return state.model_copy(update={"overlay": "none"})
    if kind == ActionKind.OPEN_SETTINGS:
        return _go(state, PageRef(page=PageKind.SETTINGS))
    if kind == ActionKind.TOGGLE_LARGE_TEXT:
        large = state.large_text if state.text_size_changed else state.large_text or o.large_text
        return state.model_copy(update={"large_text": not large, "text_size_changed": True})
    if kind == ActionKind.OPEN_HELP:
        return _go(state, PageRef(page=PageKind.HELP))
    if kind == ActionKind.OPEN_CART:
        return _go(state, PageRef(page=PageKind.CART))
    if kind == ActionKind.OPEN_WISHLIST:
        return _go(state, PageRef(page=PageKind.WISHLIST))
    if kind in (ActionKind.ADD_TO_CART, ActionKind.BUY_NOW, ActionKind.INCREASE_QUANTITY):
        product = site.product(target)
        if product is None or product.stock == 0:
            return state.model_copy(update={"notice": "Sorry, this product is sold out"})
        if kind == ActionKind.BUY_NOW and any(line.product_id == target for line in state.cart):
            return _to_checkout(site, state.model_copy(update={"overlay": "none"}))
        if not _can_add(state, product):
            return state.model_copy(update={"notice": "Your cart already contains the available quantity of this product"})
        added = state.model_copy(update={"cart": _add(state, product), "overlay": "none",
                                         "notice": f"Added to cart: {product.name}"})
        if kind == ActionKind.BUY_NOW:
            return _to_checkout(site, added)
        return added
    if kind == ActionKind.ADD_TO_WISHLIST:
        if target in state.wishlist or site.product(target) is None:
            return state
        return state.model_copy(update={"wishlist": [*state.wishlist, target], "notice": "Saved to your wishlist"})
    if kind == ActionKind.READ_REVIEWS:
        return state.model_copy(update={"reviews_open": True})
    if kind == ActionKind.REMOVE_FROM_CART:
        cart = [line for line in state.cart if line.product_id != target]
        at = state.at
        if at.page == PageKind.CART:
            pages = page_count(site, sum(site.product(line.product_id) is not None for line in cart))
            at = at.model_copy(update={"page_index": min(at.page_index, pages - 1)})
        return state.model_copy(update={"cart": cart, "at": at, "notice": "Removed from your cart"})
    if kind == ActionKind.APPLY_COUPON:
        if state.coupon_known and o.coupon_percent:
            return state.model_copy(update={"coupon_applied": True, "notice": f"Coupon {o.coupon_code} applied"})
        if o.coupon_public and o.coupon_percent:
            return state.model_copy(update={"coupon_applied": True, "coupon_known": True,
                                            "notice": f"Coupon {o.coupon_code} applied"})
        return state.model_copy(update={"notice": "That code is not valid"})
    if kind == ActionKind.CHECKOUT:
        return _to_checkout(site, state) if state.cart else state
    if kind == ActionKind.SIGN_IN:
        if not has_account:
            return state.model_copy(update={"notice": "No account found for that email address"})
        signed = state.model_copy(update={"signed_in": True, "address_added": True,
                                          "payment_method": state.payment_method or (o.payment_methods[0] if o.payment_methods else None)})
        return _to_checkout(site, signed)
    if kind == ActionKind.CREATE_ACCOUNT:
        return _to_checkout(site, state.model_copy(update={"signed_in": True, "notice": "Your account is ready"}))
    if kind == ActionKind.GUEST_CHECKOUT:
        return _to_checkout(site, state.model_copy(update={"guest": True})) if o.guest_checkout else state
    if kind == ActionKind.ADD_ADDRESS:
        added = state.model_copy(update={"address_added": True, "notice": "Address saved"})
        if o.checkout_flow == "one_page":
            return added
        return _go(added, PageRef(page=PageKind.CHECKOUT, checkout_step="review" if state.payment_method else "payment"))
    if kind == ActionKind.ADD_PAYMENT:
        method = next((m for m in o.payment_methods if m == target), None)
        if method is None:
            return state
        paid = state.model_copy(update={"payment_method": method, "notice": "Payment method added"})
        if o.checkout_flow == "one_page":
            return paid
        return _go(paid, PageRef(page=PageKind.CHECKOUT, checkout_step="review" if state.address_added else "address"))
    if kind == ActionKind.REMOVE_ADDON:
        return state.model_copy(update={"addon_removed": True})
    if kind == ActionKind.PLACE_ORDER:
        if not (state.cart and state.address_added and state.payment_method):
            return state
        products = [site.product(line.product_id) for line in state.cart]
        if len({line.product_id for line in state.cart}) != len(state.cart) or any(
            product is None or product.stock is not None and line.quantity > product.stock
            for line, product in zip(state.cart, products, strict=True)
        ):
            return state.model_copy(update={"notice": "Some cart quantities are unavailable. Adjust your cart before ordering."})
        total = cart_totals(site, state.cart, state, at_review=True).total
        placed = state.model_copy(update={"order_id": order_id(site, state), "order": state.cart, "order_total": total})
        return _go(placed, PageRef(page=PageKind.ORDER_COMPLETE)).model_copy(update={"cart": []})
    if kind == ActionKind.SORT:
        sort = next((k for k in SORT_LABELS if k == target), None)
        if sort is None:
            return state
        return state.model_copy(update={"at": state.at.model_copy(update={"sort": sort, "page_index": 0})})
    if kind in (ActionKind.NEXT_PAGE, ActionKind.PREVIOUS_PAGE):
        step = 1 if kind == ActionKind.NEXT_PAGE else -1
        return _go(state, state.at.model_copy(update={"page_index": max(0, state.at.page_index + step)}))
    if kind in (ActionKind.CLOSE_POPUP, ActionKind.ACCEPT_POPUP):
        # An ad popup waits for the welcome popup to be answered, then opens at once.
        after: Literal["promo", "none"] = "promo" if state.overlay == "welcome" and active_ads(site, "popup") else "none"
        if kind == ActionKind.ACCEPT_POPUP and o.coupon_percent:
            return state.model_copy(update={"overlay": after, "coupon_known": True, "coupon_applied": True,
                                            "notice": f"{o.coupon_percent}% off will be applied at checkout"})
        return state.model_copy(update={"overlay": after})
    if kind in (ActionKind.ACCEPT_COOKIES, ActionKind.REJECT_COOKIES):
        return state.model_copy(update={"cookies_answered": True})
    return state
