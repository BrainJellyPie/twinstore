"""Online stores: web shops built from templates, the page a shopper's browser shows and the numbered
options on it, online shoppers, their browsing sessions and the results of a run.

A shopper sees one page at a time (a rendered screenshot, or its text outline) and picks one of the page's
options: search, go back, open product 3, open the menu, add a payment method … The browser state is plain
data, so every page a shopper saw can be rendered again exactly as it was.

Prices, budgets and totals are integers in the currency's minor unit (USD → cents, KRW → won), as for
physical stores.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .persona import AgeGroup, Gender
from .providers import EnsembleConfig
from .types import ResourceId


class PageKind(StrEnum):
    HOME = "home"
    CATEGORY = "category"
    SEARCH = "search"
    DEALS = "deals"
    PRODUCT = "product"
    CART = "cart"
    SIGN_IN = "sign_in"
    CHECKOUT = "checkout"
    ORDER_COMPLETE = "order_complete"
    WISHLIST = "wishlist"
    HELP = "help"
    SETTINGS = "settings"


class ActionKind(StrEnum):
    SEARCH = "search"
    BACK = "back"
    HOME = "home"
    OPEN_CATEGORY = "open_category"
    OPEN_PRODUCT = "open_product"
    OPEN_DEALS = "open_deals"
    OPEN_MENU = "open_menu"
    CLOSE_MENU = "close_menu"
    OPEN_SETTINGS = "open_settings"
    TOGGLE_LARGE_TEXT = "toggle_large_text"
    OPEN_HELP = "open_help"
    OPEN_CART = "open_cart"
    OPEN_WISHLIST = "open_wishlist"
    ADD_TO_CART = "add_to_cart"
    BUY_NOW = "buy_now"
    ADD_TO_WISHLIST = "add_to_wishlist"
    READ_REVIEWS = "read_reviews"
    INCREASE_QUANTITY = "increase_quantity"
    REMOVE_FROM_CART = "remove_from_cart"
    APPLY_COUPON = "apply_coupon"
    CHECKOUT = "checkout"
    SIGN_IN = "sign_in"
    CREATE_ACCOUNT = "create_account"
    GUEST_CHECKOUT = "guest_checkout"
    ADD_ADDRESS = "add_address"
    ADD_PAYMENT = "add_payment"
    REMOVE_ADDON = "remove_addon"
    PLACE_ORDER = "place_order"
    SORT = "sort"
    NEXT_PAGE = "next_page"
    PREVIOUS_PAGE = "previous_page"
    CLOSE_POPUP = "close_popup"
    ACCEPT_POPUP = "accept_popup"
    ACCEPT_COOKIES = "accept_cookies"
    REJECT_COOKIES = "reject_cookies"
    LEAVE = "leave"


type SortKey = Literal["featured", "price_asc", "price_desc", "rating", "newest"]
type SearchMode = Literal["smart", "exact", "off"]
type Recommendations = Literal["none", "popular", "similar"]
type WelcomePopup = Literal["none", "newsletter", "coupon"]
type CheckoutFlow = Literal["one_page", "multi_step"]
type CheckoutStep = Literal["address", "payment", "review"]
type PaymentMethod = Literal["card", "paypal", "apple_pay", "bnpl", "bank_transfer", "cash_on_delivery"]
type ReturnPolicy = Literal["free_30", "paid", "hidden"]
type Device = Literal["desktop", "mobile"]
type Overlay = Literal["none", "menu", "welcome", "promo"]
# Where an ad campaign shows: the home banner, the top of the lists that hold its product, a sponsored row on the
# home page, other products' pages, the cart ("add this to your order"), or a popup over the landing page.
type AdPlacement = Literal["hero_banner", "sponsored_listing", "home_tile", "product_page", "cart_upsell", "popup"]
type AdPricing = Literal["cpc", "cpm"]
type ProductBadge = Literal["bestseller", "new", "limited", "eco", "sponsored"]
type HomeSection = Literal["categories", "bestsellers", "deals", "new", "recommended"]
# How the shop's pages look: colours, corners, type, header and banner. Vision-model shoppers see it; rule and
# text shoppers decide the same way whatever the look.
type PageStyle = Literal[
    "classic", "minimal", "luxury", "brutalist", "playful", "marketplace", "editorial", "neon", "retro", "organic", "tech",
]
type TemplateHighlight = Literal[
    "mobile", "quick_add", "one_click", "coupon_popup", "newsletter_popup", "urgency", "social_proof", "sponsored",
    "addon", "service_fee", "account_required", "one_page_checkout", "bnpl", "cash_on_delivery", "paid_returns",
    "large_text", "free_delivery",
]
# Why a shopper opened the site: buy something specific, look around (window shopping), compare options before
# buying, hunt for discounts, find a gift, or reorder something they buy regularly.
type ShopperMission = Literal["purchase", "browse", "compare", "deal_hunt", "gift", "replenish"]
# Who picks the options: rules (instant, free), a vision model looking at the screenshot, or a text model reading
# the page outline (no image), e.g. to see what the picture adds.
type ShopperPolicyKind = Literal["rule", "vlm", "text"]
type ShopperSource = Literal["panel", "project"]
# Where a visit comes from, which decides the page it starts on: typing the address (home), a search engine result (the
# product page that fits), a social media post (a popular product) or the shop's email (its deals).
type Arrival = Literal["direct", "search_engine", "social", "email"]
# What the shopper's eyes make of a screen. The screenshot a vision model gets is filtered to match.
type Vision = Literal["typical", "low_vision", "color_blind", "aging_eyes"]
# Eyesight of a run's shoppers: all typical, a realistic mix by age and gender, or everyone with one condition
# (a stress test of the design).
type Accessibility = Literal["typical", "realistic", "low_vision", "color_blind", "aging_eyes"]
type FrictionCode = Literal[
    "popup_shown", "popup_left", "popup_accepted", "signin_reached", "signin_left", "account_created",
    "fee_seen", "fee_left", "addon_seen", "addon_removed", "addon_paid", "coupon_failed", "zero_results",
    "sold_out_seen", "slow_exit", "cookies_rejected",
]
type StepSource = Literal["rule", "model", "fallback"]
type SessionOutcome = Literal["purchased", "abandoned_cart", "left", "bounced", "timed_out", "step_limit"]
type FunnelStage = Literal["visit", "product_view", "add_to_cart", "checkout", "payment", "purchase"]

SHOPPER_MISSIONS: list[ShopperMission] = ["purchase", "browse", "compare", "deal_hunt", "gift", "replenish"]
ARRIVALS: list[Arrival] = ["direct", "search_engine", "social", "email"]
FUNNEL_STAGES: list[FunnelStage] = ["visit", "product_view", "add_to_cart", "checkout", "payment", "purchase"]
PAYMENT_METHODS: list[PaymentMethod] = ["card", "paypal", "apple_pay", "bnpl", "bank_transfer", "cash_on_delivery"]
SORT_KEYS: list[SortKey] = ["featured", "price_asc", "price_desc", "rating", "newest"]
PAGE_STYLES: list[PageStyle] = [
    "classic", "minimal", "luxury", "brutalist", "playful", "marketplace", "editorial", "neon", "retro", "organic", "tech",
]


class OnlineCategory(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=80)
    glyph: str = ""  # picture drawn for products without a photo (see engine/online/render.py)


class OnlineProduct(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    category_id: str
    price: int = Field(ge=0)
    list_price: int = Field(default=0, ge=0)  # above `price`: shown struck through as a discount
    rating: float = Field(default=4.2, ge=0, le=5)
    reviews: int = Field(default=0, ge=0)
    badges: list[ProductBadge] = []
    stock: int | None = Field(default=None, ge=0)  # None = plenty; 0 = sold out; a few = "only N left"
    description: str = Field(default="", max_length=400)
    tags: list[str] = []  # extra words search finds the product by
    image_url: str = ""  # bundled catalog picture or the project's product photo
    sku: str = ""  # the physical store's SKU, for sites made from a layout
    weekly_sales: int = Field(default=0, ge=0)  # "N bought this week" when the site shows social proof

    @property
    def discount_percent(self) -> int:
        if self.list_price <= self.price or self.list_price <= 0:
            return 0
        return round((self.list_price - self.price) * 100 / self.list_price)


class SiteOptions(BaseModel):
    """The design choices of one site variant. Each is something a store owner can change, so two variants that differ
    in one option, shopped by the same virtual customers, measure what that option does."""
    model_config = ConfigDict(allow_inf_nan=False)

    # Look
    theme_color: str = Field(default="#2563eb", pattern=r"^#[0-9a-fA-F]{6}$")
    page_style: PageStyle = "classic"
    device: Device | None = None  # None = each shopper's own device; otherwise every page is laid out for this one
    grid_columns: int = Field(default=4, ge=2, le=5)  # product columns on desktop (mobile shows two)
    products_per_page: int = Field(default=8, ge=4, le=24)
    hero_banner: bool = True
    hero_text: str = Field(default="", max_length=80)
    home_sections: list[HomeSection] = ["categories", "bestsellers", "deals"]
    large_text: bool = False  # bigger type everywhere (shoppers can also switch it on in settings)
    # Catalog
    show_ratings: bool = True
    show_review_counts: bool = True
    default_sort: SortKey = "featured"
    search: SearchMode = "smart"
    sponsored_slots: int = Field(default=0, ge=0, le=4)  # sponsored products placed first in lists
    recommendations: Recommendations = "similar"
    quick_add: bool = False  # "Add to cart" right on product cards
    reviews_on_product: bool = True
    wishlist: bool = True
    # Persuasion (several of these are common dark patterns; measure them, do not assume they help)
    urgency: bool = False  # "Only 3 left", "Sale ends in 02:14:09"
    social_proof: bool = False  # "128 bought this week"
    welcome_popup: WelcomePopup = "none"
    cookie_banner: bool = True
    chat_widget: bool = False
    # Price and checkout
    shipping_fee: int = Field(default=499, ge=0)
    free_shipping_threshold: int = Field(default=3500, ge=0)  # 0 = free shipping on every order
    coupon_code: str = Field(default="", max_length=20)
    coupon_percent: int = Field(default=0, ge=0, le=90)
    coupon_public: bool = True  # code printed on the home banner; otherwise only the welcome popup gives it
    cart_reminder: bool = False  # an email reminds shoppers who leave items in the cart; some come back to it
    cart_reminder_percent: int = Field(default=0, ge=0, le=50)  # discount on the cart the reminder offers
    guest_checkout: bool = True  # False = shoppers must sign in or create an account
    checkout_flow: CheckoutFlow = "multi_step"
    payment_methods: list[PaymentMethod] = ["card", "paypal", "apple_pay"]
    one_click_buy: bool = False  # "Buy now" on product pages jumps straight to checkout
    service_fee: int = Field(default=0, ge=0)  # added only on the order review (drip pricing)
    preselected_addon_percent: int = Field(default=0, ge=0, le=50)  # protection plan pre-ticked at checkout
    return_policy: ReturnPolicy = "free_30"
    trust_badges: bool = True
    page_load_ms: int = Field(default=600, ge=50, le=15000)  # how long every page takes to load


class AdCampaign(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=60)
    product_id: str
    placement: AdPlacement
    headline: str = Field(default="", max_length=70)
    pricing: AdPricing = "cpc"
    cost: int = Field(default=50, ge=0)  # per click (CPC) or per thousand impressions (CPM), minor units
    active: bool = True


class OnlineSite(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: ResourceId
    name: str = Field(min_length=1, max_length=60)
    template_id: str
    currency: str = "USD"
    tagline: str = Field(default="", max_length=120)
    categories: list[OnlineCategory] = Field(min_length=1)
    products: list[OnlineProduct] = Field(min_length=1)
    options: SiteOptions = SiteOptions()
    ads: list[AdCampaign] = Field(default_factory=list[AdCampaign], max_length=12)
    variant_of: str = ""  # site this one was copied from
    note: str = Field(default="", max_length=400)  # what this variant changes
    created_at: str = ""
    updated_at: str = ""

    def product(self, product_id: str) -> OnlineProduct | None:
        return next((p for p in self.products if p.id == product_id), None)

    def category(self, category_id: str) -> OnlineCategory | None:
        return next((c for c in self.categories if c.id == category_id), None)


class OnlineTemplate(BaseModel):
    """A ready-made web shop: catalog categories, its look and the defaults of its kind of store."""
    id: str
    name: str
    vertical: str  # store kind, e.g. "grocery", "beauty", "electronics"
    tagline: str
    description: str
    categories: int
    products: int
    photos: int  # products with a bundled picture
    theme_color: str
    highlights: list[TemplateHighlight] = []  # options this template starts with that differ from a plain shop


class CartLine(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=99)


class PageRef(BaseModel):
    page: PageKind = PageKind.HOME
    category_id: str = ""
    query: str = ""
    product_id: str = ""
    sort: SortKey | None = None  # None = the site's default order
    page_index: int = Field(default=0, ge=0)
    checkout_step: CheckoutStep = "address"


class BrowserState(BaseModel):
    """Everything a page depends on besides the site itself."""
    at: PageRef = PageRef()
    history: list[PageRef] = []  # pages "Back" returns to, most recent last
    overlay: Overlay = "none"
    cart: list[CartLine] = []
    wishlist: list[str] = []
    viewed: list[str] = []  # product pages opened, most recent last
    reviews_open: bool = False
    welcome_seen: bool = False
    cookies_answered: bool = False
    coupon_known: bool = False
    coupon_applied: bool = False
    signed_in: bool = False
    guest: bool = False
    address_added: bool = False
    payment_method: PaymentMethod | None = None
    addon_removed: bool = False
    large_text: bool = False
    text_size_changed: bool = False  # distinguish an explicit normal-size choice from the site's default
    device: Device = "desktop"
    reminder_percent: int = 0  # discount from a cart reminder email (the better of it and a coupon applies)
    notice: str = ""  # one-line message on this page ("Added to cart")
    order_id: str = ""
    order: list[CartLine] = []  # what was bought, once the order is placed
    order_total: int = 0


class OnlineAction(BaseModel):
    kind: ActionKind
    target: str = ""  # product, category, sort key or payment method the action is about
    label: str = ""
    ad_id: str = ""  # the ad campaign this element belongs to ("" = not an ad)


class PageOption(OnlineAction):
    number: int = Field(ge=1)
    box: tuple[int, int, int, int] | None = None  # (left, top, right, bottom) in screenshot pixels


class PageView(BaseModel):
    """One page as a shopper's browser shows it: what is on it and what can be clicked."""
    url: str
    title: str
    page: PageKind
    options: list[PageOption]
    outline: list[str]  # the page's text, top to bottom (what the text policy reads)
    state: BrowserState
    image: str = ""  # PNG data URL when rendered
    width: int = 0
    height: int = 0


class OnlineShopper(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: str
    identity: str
    age_group: AgeGroup
    gender: Gender
    device: Device
    mission: ShopperMission
    goal: str  # in the shopper's words, e.g. "Find running shoes for a half-marathon"
    target_category: str = ""  # category id the mission is about ("" = none)
    target_terms: list[str] = []  # words they would type into a search box
    target_product: str = ""  # product id a replenishing shopper reorders
    budget: int = Field(default=0, ge=0)  # 0 = no limit
    price_sensitivity: float = Field(default=0.5, ge=0, le=1)
    patience_sec: int = Field(default=600, ge=30)  # time they give the site before giving up
    tech_savvy: float = Field(default=0.6, ge=0, le=1)
    has_account: bool = False
    description: str = ""
    persona_id: str = ""  # project customer this shopper was made from ("" = panel)
    vision: Vision = "typical"
    arrival: Arrival = "direct"


class SearchRecord(BaseModel):
    query: str
    results: int
    step: int


class OrderLine(BaseModel):
    product_id: str
    name: str
    category_id: str
    quantity: int
    price: int


class SessionStep(BaseModel):
    index: int
    url: str
    page: PageKind
    state: BrowserState  # before the shopper acted (renders the page they saw)
    options: int  # options the page offered
    choice: PageOption | None = None
    search_text: str = ""
    thought: str = ""
    seconds: float = 0.0  # on this page, loading included
    load_seconds: float = 0.0
    source: StepSource = "rule"
    error: str = ""
    mark_seed: int = 0  # badge numbering of the screenshot (0 = in reading order)
    screen: tuple[int, int] | None = None  # (width, height) of the screenshot, when one was drawn
    ads: list[str] = []  # ad campaigns shown on this page


class ExitSurvey(BaseModel):
    """What the shopper says right after the visit (model runs). Scales: satisfaction and ease 1–7 (ease is the
    single ease question, SEQ), recommend 0–10 (net promoter question)."""
    satisfaction: int = Field(ge=1, le=7)
    ease: int = Field(ge=1, le=7)
    recommend: int = Field(ge=0, le=10)
    would_return: bool
    frustration: str = Field(default="", max_length=200)
    improvement: str = Field(default="", max_length=200)


class RivalVisit(BaseModel):
    """The shopper's visit to the rival shop after leaving without buying (the same visit whichever variant they left;
    its replay is the run's last store)."""
    outcome: SessionOutcome
    order_total: int = 0
    steps: int = 0
    exit_thought: str = ""


class SessionResult(BaseModel):
    shopper_id: str
    site_id: str
    outcome: SessionOutcome
    steps: list[SessionStep]
    order: list[OrderLine] = []
    subtotal: int = 0
    order_total: int = 0  # what the shopper paid: items, shipping, fees, add-ons, less the coupon
    seconds: float = 0.0
    reached: list[FunnelStage] = ["visit"]
    viewed_products: list[str] = []
    searches: list[SearchRecord] = []
    exit_page: PageKind = PageKind.HOME
    exit_thought: str = ""
    model_requests: int = 0
    fallbacks: int = 0
    survey: ExitSurvey | None = None
    addon_paid: int = 0  # what a pre-ticked add-on the shopper left ticked cost them
    discount: int = 0  # coupon or reminder discount on the order
    reminded: bool = False  # left a cart and got the reminder email
    returned_at: int | None = None  # first step of the visit the reminder brought them back for
    rival: RivalVisit | None = None  # left without buying and tried the rival shop


class OnlineRunRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    site_ids: list[ResourceId] = Field(min_length=1, max_length=4)  # the first is the control
    rival_site_id: ResourceId | None = None  # a rival shop that shoppers who leave without buying may try next
    name: str = Field(default="", max_length=80)
    shoppers: int = Field(default=30, ge=1, le=500)
    policy: ShopperPolicyKind = "rule"
    model: str | None = Field(default=None, description='Model reference, e.g. "llamacpp:local" (None = default)')
    ensemble: EnsembleConfig | None = None  # several models as one population: each shopper gets one of them
    seed: int = 0
    max_steps: int = Field(default=24, ge=3, le=80,
                           description="Maximum decisions per visit; a cart reminder can add one return visit")
    missions: dict[ShopperMission, Annotated[float, Field(ge=0, le=1000)]] = Field(default_factory=lambda: {
        "purchase": 0.25, "browse": 0.35, "compare": 0.15, "deal_hunt": 0.1, "gift": 0.07, "replenish": 0.08,
    })
    arrivals: dict[Arrival, Annotated[float, Field(ge=0, le=1000)]] = Field(default_factory=lambda: {"direct": 1.0})
    mobile_share: float = Field(default=0.55, ge=0, le=1)
    source: ShopperSource = "panel"
    image_width: int = Field(default=896, ge=480, le=1600)
    shuffle_marks: bool = True  # number badges drawn at random, so a model's liking for low numbers is noise
    accessibility: Accessibility = "typical"
    exit_survey: bool = True  # model runs: each shopper answers a short survey after the visit (one more call)


class FunnelRow(BaseModel):
    stage: FunnelStage
    sessions: int
    share: float  # of all sessions


type SegmentDimension = Literal["mission", "device", "age_group", "gender", "vision", "arrival"]


class SegmentRow(BaseModel):
    dimension: SegmentDimension
    value: str
    sessions: int
    conversion: float
    revenue_per_session: float
    avg_steps: float
    bounce_rate: float | None = None  # None in reports saved before it was measured


class ProductRow(BaseModel):
    product_id: str
    name: str
    views: int
    adds: int
    purchases: int
    units: int
    revenue: int


class SearchTermRow(BaseModel):
    query: str
    count: int
    zero_results: int
    purchases: int  # sessions with this search that ended in an order


class ExitRow(BaseModel):
    page: PageKind
    sessions: int


class ClickPoint(BaseModel):
    page: PageKind
    kind: ActionKind
    device: Device
    x: float  # centre of the clicked element, as a share of the screenshot's width and height
    y: float


class AdRow(BaseModel):
    """What one ad campaign was credited with in one store variant."""
    ad_id: str
    name: str
    placement: AdPlacement
    product_id: str
    product_name: str
    impressions: int  # page views it was on
    reach: int  # visits that saw it
    clicks: int
    ctr: float
    click_conversions: int  # visits that clicked it and ordered the product
    view_conversions: int  # visits that saw it, did not click and ordered the product
    attributed_revenue: int  # the product's revenue in post-click conversions
    units_sold: int  # the product's units in every order
    cost: int
    roas: float | None  # attributed revenue / cost


class AdLift(BaseModel):
    """What an ad running in only one of two compared stores added, on the same shoppers: the store with it minus
    the store without it."""
    ad_id: str
    name: str
    site_id: str  # the store that runs the ad
    product_id: str
    units_without: int
    units_with: int
    units_diff: int
    revenue_diff: int  # total revenue, with the ad minus without
    other_revenue_diff: int  # other product line revenue, before order discounts/fees (negative: cannibalization)
    cost: int
    iroas: float | None  # revenue_diff / cost


class RecoveryRow(BaseModel):
    """What the cart reminder email did in one store variant."""
    emails: int  # visits that left items in the cart and got the reminder
    returned: int
    recovered: int  # returns that ended in an order
    revenue: int  # what the recovered orders paid
    discount: int  # discount given on the recovered orders


class RivalRow(BaseModel):
    """Where this store's lost shoppers went: the rival shop's take."""
    left: int  # visits that ended without an order
    went: int  # of those, shoppers who tried the rival
    bought: int  # and ordered there
    revenue: int  # what the rival took from them


class FrictionRow(BaseModel):
    """How often one known friction point (or dark pattern) came up, and how many sessions ended right there."""
    code: FrictionCode
    sessions: int  # sessions where it happened
    share: float  # of all sessions
    amount: int = 0  # money involved, e.g. add-on revenue from shoppers who never unticked it


class SurveySummary(BaseModel):
    responses: int
    satisfaction: float  # mean, 1–7
    ease: float  # mean, 1–7
    nps: float  # % promoters (9–10) minus % detractors (0–6), −100…100
    would_return: float  # share
    frustrations: list[str]  # a sample, most common first
    improvements: list[str]


class FlowLink(BaseModel):
    """Visits that went from one page to the next at one step, or ended after it: a link of the page-flow chart."""
    depth: int  # the source page's step in the visit, from 0
    source: PageKind
    target: PageKind | None = None  # the next page; None when the chart stops following the visit here
    outcome: SessionOutcome | None = None  # set when target is None: how the visit ended, maybe after more pages
    sessions: int


class VariantSummary(BaseModel):
    site_id: str
    site_name: str
    sessions: int
    purchases: int
    conversion: float
    revenue: int
    aov: float
    revenue_per_session: float
    bounce_rate: float
    cart_abandonment: float  # sessions that added to the cart but did not order, of those that added
    add_to_cart_rate: float
    avg_steps: float
    avg_seconds: float
    search_share: float
    zero_result_searches: int
    outcomes: dict[str, int]
    actions: dict[str, int]
    funnel: list[FunnelRow]
    exits: list[ExitRow]
    segments: list[SegmentRow]
    products: list[ProductRow]
    searches: list[SearchTermRow]
    clicks: list[ClickPoint]
    frictions: list[FrictionRow] = []
    survey: SurveySummary | None = None
    ads: list[AdRow] = []
    recovery: RecoveryRow | None = None  # stores that send the cart reminder
    rival: RivalRow | None = None  # runs with a rival shop
    flow: list[FlowLink] = []  # the first pages of each visit ([] in older runs)
    flow_route: list[PageKind | SessionOutcome] = []  # most common observed page prefix and its final outcome


class PairedDelta(BaseModel):
    metric: Literal["conversion", "revenue_per_session", "add_to_cart_rate", "steps", "seconds", "satisfaction", "recommend",
                    "rival_revenue_per_session"]
    control: float
    variant: float
    diff: float
    ci_low: float | None = None
    ci_high: float | None = None
    n: int


class SegmentDelta(BaseModel):
    """Conversion and revenue per visit, variant minus control, for the same shoppers within one segment."""
    dimension: SegmentDimension
    value: str
    n: int
    control_conversion: float
    variant_conversion: float
    conversion_diff: float
    ci_low: float | None = None
    ci_high: float | None = None
    revenue_diff: float  # per visit


class SwitchRow(BaseModel):
    """A shopper whose visit ended differently in the two stores, and why each visit ended."""
    shopper_id: str
    control_outcome: SessionOutcome
    variant_outcome: SessionOutcome
    control_total: int
    variant_total: int
    control_exit: PageKind
    variant_exit: PageKind
    control_thought: str = ""
    variant_thought: str = ""


class VariantComparison(BaseModel):
    site_id: str
    site_name: str
    deltas: list[PairedDelta]
    ad_lifts: list[AdLift] = []
    segments: list[SegmentDelta] = []
    won: int = 0  # shoppers who ordered only in the variant
    lost: int = 0  # shoppers who ordered only in the control
    changed: int = 0  # shoppers whose visit ended differently
    switches: list[SwitchRow] = []  # some of them: orders won or lost first, the largest amounts first


class VisitBrief(BaseModel):
    """How one shopper's visit to one store of a run ended, for picking whom to watch without loading every visit."""
    outcome: SessionOutcome
    order_total: int = 0
    clicks: int = 0
    rival: SessionOutcome | None = None  # where a visit that ended without an order went on at the rival shop
    furthest: FunnelStage = "visit"  # the last funnel stage the visit reached


class OnlineRunResult(BaseModel):
    run_id: str
    name: str = ""
    policy: ShopperPolicyKind
    model: str = ""
    currency: str
    variants: list[VariantSummary]
    comparisons: list[VariantComparison] = []
    shoppers: list[OnlineShopper]
    model_requests: int = 0
    fallbacks: int = 0
    seconds: float = 0.0
    notes: list[str] = []
    rival_name: str = ""  # the rival shop of the run, if any; its sessions are the store after the variants
    visits: dict[str, list[VisitBrief]] = {}  # shopper id → their visit to each store, in store order ({} in older runs)


class OnlineRunStatus(BaseModel):
    run_id: str
    name: str = ""
    site_ids: list[str]
    site_names: list[str] = []
    status: str  # pending | running | completed | failed
    phase: str = ""
    done: int = 0  # sessions finished, all variants
    total: int = 0
    error: str = ""
    request: OnlineRunRequest
    created_at: str = ""
    finished_at: str = ""
    image_snapshot: bool = False  # older runs did not retain their product artwork
