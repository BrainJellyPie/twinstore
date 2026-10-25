"""Changing a web shop's design by talking to a language model.

The owner says what they want ("make it feel premium", "a green theme and add-to-cart buttons on the cards", "remove
the popup") and the model answers with a short reply and the options to change, nothing else: every proposed value is
one the designer form could set, checked by the same validation, and applied to a draft. Nothing is saved; the owner
keeps the draft, saves it as a variant and tests it against the original on the same shoppers. Written in English like
the other online prompts; the "Language" block keeps the reply in English.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.online import (
    PAGE_STYLES,
    CheckoutFlow,
    DesignMessage,
    HomeSection,
    OnlineSite,
    PageStyle,
    SiteOptions,
    SortKey,
    WelcomePopup,
)
from store_emulator.engine.layout_edit import ZERO_DECIMAL
from store_emulator.engine.prompting import display_price


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


DESIGN_PROMPT = """You are a web designer changing an online shop's design for its owner, in a conversation. Each turn,
read the owner's latest message (and the conversation before it) and return:
- the options to change, each set to its new value; leave every other option null. Use only the values listed for each
  option. Every change you mention in the reply must be set here.
- `reply`: one to three plain sentences saying what you changed and why, or a short question ending in "?" when the
  request is unclear or cannot be done with these options (then change nothing).

Page styles: {styles}.
Money amounts are in major units of {currency} (e.g. 4.99).
Make the changes the owner asked for, plus only what clearly serves them (e.g. "feel premium": a luxury or minimal style,
a dark theme colour, no urgency or popups). Do not undo earlier changes unless asked. Never invent options.

## Language
Write reply in English."""


class DesignChanges(BaseModel):
    """The options to change; null leaves an option as it is."""
    model_config = ConfigDict(str_strip_whitespace=True)

    page_style: PageStyle | None = None
    theme_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$", description="hex colour, e.g. #1d4ed8")
    grid_columns: int | None = Field(default=None, ge=2, le=5, description="product columns on desktop")
    products_per_page: int | None = Field(default=None, ge=4, le=24)
    hero_banner: bool | None = None
    hero_text: str | None = Field(default=None, max_length=80, description="the home banner's headline")
    home_sections: list[HomeSection] | None = Field(default=None, max_length=5)
    large_text: bool | None = None
    show_ratings: bool | None = None
    default_sort: SortKey | None = None
    quick_add: bool | None = Field(default=None, description="'Add to cart' buttons on product cards")
    wishlist: bool | None = None
    urgency: bool | None = Field(default=None, description="'Only 3 left' notes")
    social_proof: bool | None = Field(default=None, description="'128 bought this week' notes")
    welcome_popup: WelcomePopup | None = None
    cookie_banner: bool | None = None
    chat_widget: bool | None = None
    trust_badges: bool | None = None
    shipping_fee: float | None = Field(default=None, ge=0, le=1_000_000, description="delivery fee, major units")
    free_shipping_threshold: float | None = Field(default=None, ge=0, le=10_000_000,
                                                  description="order total for free delivery, major units; 0 = always free")
    coupon_code: str | None = Field(default=None, max_length=20)
    coupon_percent: int | None = Field(default=None, ge=0, le=90)
    guest_checkout: bool | None = None
    checkout_flow: CheckoutFlow | None = None
    one_click_buy: bool | None = None
    page_load_ms: int | None = Field(default=None, ge=50, le=15000)


class DesignReply(DesignChanges):
    """The options to change, then the reply: a model writes what it set before saying what it did."""
    reply: str = Field(min_length=1, max_length=600)

    @property
    def changes(self) -> DesignChanges:
        return DesignChanges.model_validate(self.model_dump(exclude={"reply"}))


_MONEY = ("shipping_fee", "free_shipping_threshold")


def _minor(currency: str) -> int:
    return 1 if currency.upper() in ZERO_DECIMAL else 100


def apply_design(options: SiteOptions, changes: DesignChanges, currency: str) -> tuple[SiteOptions, list[str]]:
    """`options` with the proposed changes, validated like the designer form, and the names of options that changed."""
    update: dict[str, object] = {}
    for key, value in changes.model_dump(exclude_none=True).items():
        update[key] = round(value * _minor(currency)) if key in _MONEY and isinstance(value, float) else value
    edited = SiteOptions.model_validate({**options.model_dump(), **update})
    changed = [key for key in update if getattr(edited, key) != getattr(options, key)]
    return edited, changed


def _describe(site: OnlineSite, options: SiteOptions) -> str:
    o = options
    categories = ", ".join(c.name for c in site.categories[:12])
    return "\n".join([
        f"Shop: {site.name} ({site.tagline or 'web shop'}), selling: {categories}.",
        "Current design:",
        f"- page_style: {o.page_style}; theme_color: {o.theme_color}; grid_columns: {o.grid_columns}; "
        f"products_per_page: {o.products_per_page}",
        f"- hero_banner: {o.hero_banner}; hero_text: {o.hero_text!r}; home_sections: {', '.join(o.home_sections)} "
        "(choose from categories, bestsellers, deals, new, recommended)",
        f"- large_text: {o.large_text}; show_ratings: {o.show_ratings}; default_sort: {o.default_sort} "
        "(featured, price_asc, price_desc, rating, newest)",
        f"- quick_add: {o.quick_add}; wishlist: {o.wishlist}; urgency: {o.urgency}; social_proof: {o.social_proof}",
        f"- welcome_popup: {o.welcome_popup} (none, newsletter, coupon); cookie_banner: {o.cookie_banner}; "
        f"chat_widget: {o.chat_widget}; trust_badges: {o.trust_badges}",
        f"- shipping_fee: {display_price(o.shipping_fee, site.currency)}; "
        f"free_shipping_threshold: {display_price(o.free_shipping_threshold, site.currency)}; "
        f"coupon_code: {o.coupon_code!r}; coupon_percent: {o.coupon_percent}",
        f"- guest_checkout: {o.guest_checkout}; checkout_flow: {o.checkout_flow} (one_page, multi_step); "
        f"one_click_buy: {o.one_click_buy}; page_load_ms: {o.page_load_ms}",
    ])


async def chat_design(llm: StructuredLLM, site: OnlineSite, options: SiteOptions,
                      messages: Sequence[DesignMessage]) -> DesignReply:
    """The designer's reply to the owner's latest message, with the option changes it proposes."""
    talk = "\n".join(f"{'Owner' if m.role == 'owner' else 'Designer'}: {m.text}" for m in messages)
    system = DESIGN_PROMPT.format(styles=", ".join(PAGE_STYLES), currency=site.currency.upper())
    user = f"{_describe(site, options)}\n\nConversation:\n{talk}"
    reply = await llm.generate_structured_async(DesignReply, system, user, max_retries=2, seed=0)
    if reply.changes.model_dump(exclude_none=True) or reply.reply.rstrip().endswith("?"):
        return reply
    # Small models often describe a change without setting it: ask once more, saying so.
    return await llm.generate_structured_async(
        DesignReply, system, f"{user}\n\nYour previous answer set no option. Set every option you change, or ask a question.",
        max_retries=2, seed=1)
