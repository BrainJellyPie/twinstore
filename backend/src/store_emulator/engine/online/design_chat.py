"""Changing a web shop's design by talking to a language model.

The owner says what they want ("make it feel premium", "a green theme and add-to-cart buttons on the cards", "remove
the popup") and the model answers with a short reply and the options to change, nothing else: every proposed value is
one the designer form could set, checked by the same validation, and applied to a draft. Nothing is saved; the owner
keeps the draft, saves it as a variant and tests it against the original on the same shoppers. Written in English like
the other online prompts; the "Language" block keeps the reply in English.
"""

import re
from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

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
- `updates`: a list of {{"option": field_name, "value": new_value}}. Include ONLY requested changes, using the
  listed values. Do not copy unchanged values, emit null values or add unrelated options. Every change you mention
  in the reply must be set here. Use an empty list when nothing should change.
- `reply`: one to three plain sentences saying what you changed and why, or a short question ending in "?" when the
  request is unclear or cannot be done with these options (then change nothing).

Page styles: {styles}.
Money amounts are in major units of {currency} (e.g. 4.99).
Make the changes the owner asked for, plus only what clearly serves them (e.g. "feel premium": a luxury or minimal style,
a dark theme colour, no urgency or popups). Do not undo earlier changes unless asked. Never invent options.
Examples: "Change ONLY the color to #00AA33" => updates=[{{"option":"theme_color","value":"#00AA33"}}].
"Remove the welcome popup" => updates=[{{"option":"welcome_popup","value":"none"}}].
"Free delivery" => updates=[{{"option":"shipping_fee","value":0}}]. Never change unrelated options.
"Free delivery and remove the welcome popup" => updates=[{{"option":"shipping_fee","value":0}},{{"option":"welcome_popup","value":"none"}}].
Cover every requested change when the owner combines several instructions.
"Free shipping from an order total of 20; keep the shipping fee" => updates=[{{"option":"free_shipping_threshold","value":20}}].
"Set the free-delivery threshold to zero; keep the shipping fee" => updates=[{{"option":"free_shipping_threshold","value":0}}].
shipping_fee is the charge below the free_shipping_threshold; the threshold is the order total that qualifies for free delivery.
When asked to change only the threshold, set free_shipping_threshold and leave shipping_fee unchanged, including for a threshold of zero.

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


def _reply_schema(schema: dict[str, JsonValue]) -> None:
    """Bind each sparse update to that option's existing non-null value schema."""
    fields = schema["properties"]
    assert isinstance(fields, dict)
    variants: list[JsonValue] = []
    for key, definition in fields.items():
        if key == "reply":
            continue
        assert isinstance(definition, dict)
        choices = definition["anyOf"]
        assert isinstance(choices, list)
        value = next(choice for choice in choices if isinstance(choice, dict) and choice.get("type") != "null")
        variants.append({"type": "object", "required": ["option", "value"], "additionalProperties": False,
            "properties": {"option": {"type": "string", "const": key}, "value": value}})
    schema["properties"] = {
        "updates": {"type": "array", "maxItems": len(variants), "items": {"anyOf": variants}}, "reply": fields["reply"],
    }
    schema["required"] = ["updates", "reply"]
    schema["additionalProperties"] = False


class DesignReply(DesignChanges):
    """The options to change, then the reply: a model writes what it set before saying what it did."""
    model_config = ConfigDict(extra="forbid", json_schema_extra=_reply_schema)
    reply: str = Field(min_length=1, max_length=600)

    @model_validator(mode="before")
    @classmethod
    def sparse_updates(cls, value: JsonValue) -> JsonValue:
        if not isinstance(value, dict) or "updates" not in value:
            return value  # Canonical flat changes remain readable from cache.
        if set(value) - {"updates", "reply"} or not isinstance(value["updates"], list):
            raise ValueError("Return only updates and reply; updates must be a list.")
        fields: dict[str, JsonValue] = {"reply": value.get("reply")}
        for update in value["updates"]:
            if not isinstance(update, dict) or set(update) != {"option", "value"}:
                raise ValueError("Each update must contain only option and value.")
            key = update["option"]
            if not isinstance(key, str) or key not in DesignChanges.model_fields or key in fields:
                raise ValueError("Each design option may be updated once, using a known option name.")
            if update["value"] is None:
                raise ValueError("Omit unchanged options; an update must have a non-null value.")
            fields[key] = update["value"]
        return fields

    @property
    def changes(self) -> DesignChanges:
        return DesignChanges.model_validate(self.model_dump(exclude={"reply"}))


_MONEY = ("shipping_fee", "free_shipping_threshold")
_HISTORY_BYTES = 4000  # Reserve room for the current design, system instructions and reply on small local contexts.


def _minor(currency: str) -> int:
    return 1 if currency.upper() in ZERO_DECIMAL else 100


def apply_design(options: SiteOptions, changes: DesignChanges, currency: str) -> tuple[SiteOptions, list[str]]:
    """`options` with the proposed changes, validated like the designer form, and the names of options that changed."""
    update: dict[str, object] = {}
    for key, value in changes.model_dump(exclude_none=True).items():
        update[key] = (int((Decimal(str(value)) * _minor(currency)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                       if key in _MONEY and isinstance(value, float) else value)
    edited = SiteOptions.model_validate({**options.model_dump(), **update})
    changed = [key for key in update if getattr(edited, key) != getattr(options, key)]
    return edited, changed


# What a reply calls each group of options, to catch a reply that describes a change it did not set (small models
# often narrate more than their updates hold). A mention counts as set when any option of its group was set.
_MENTION_PATTERNS: list[tuple[str, str, tuple[str, ...]]] = [
    ("page style", r"\b(luxury|minimal|brutalist|playful|marketplace|editorial|neon|retro|organic|page style)\b", ("page_style",)),
    ("colour", r"\bcolou?rs?\b|#[0-9a-f]{6}\b", ("theme_color",)),
    ("product grid", r"\bcolumns?\b|\bper page\b", ("grid_columns", "products_per_page")),
    ("banner", r"(?<!cookie )\bbanner\b|\bheadline\b|\bhero\b", ("hero_banner", "hero_text")),
    ("home page sections", r"\bsections?\b", ("home_sections",)),
    ("text size", r"\b(large|larger|bigger) text\b|\b(text|font) size\b", ("large_text",)),
    ("ratings", r"\bratings?\b", ("show_ratings",)),
    ("sort order", r"\bsort(ed|ing)?\b", ("default_sort",)),
    ("add-to-cart buttons", r"\badd[- ]to[- ]cart\b|\bquick[- ]add\b", ("quick_add",)),
    ("wishlist", r"\bwish ?list\b", ("wishlist",)),
    ("urgency and popularity notes", r"\burgency\b|\bscarcity\b|\bsocial proof\b|\bbought this week\b", ("urgency", "social_proof")),
    ("welcome popup", r"\bpop-?ups?\b|\bnewsletter\b", ("welcome_popup",)),
    ("cookie banner", r"\bcookies?\b", ("cookie_banner",)),
    ("chat widget", r"\bchat\b", ("chat_widget",)),
    ("trust badges", r"\btrust\b", ("trust_badges",)),
    ("free-delivery threshold", r"\bfree[- ](?:shipping|delivery)[- ]threshold\b", ("free_shipping_threshold",)),
    ("delivery fees", r"\b(?:shipping|delivery)\b(?![- ]threshold\b)", ("shipping_fee", "free_shipping_threshold")),
    ("coupon", r"\bcoupons?\b|\b(discount|promo) code\b", ("coupon_code", "coupon_percent", "welcome_popup")),
    ("guest checkout", r"\bguest\b", ("guest_checkout",)),
    ("checkout steps", r"\bone[- ]page checkout\b|\bmulti[- ]step\b|\bcheckout (steps|flow)\b", ("checkout_flow",)),
    ("one-click buying", r"\bone[- ]click\b|\bbuy now\b", ("one_click_buy",)),
    ("page speed", r"\bload(ing)? time\b|\bpage (speed|load)\b|\b\d+ ?ms\b|\b(faster|slower) pages?\b", ("page_load_ms",)),
]
_MENTIONS = [(name, re.compile(pattern, re.IGNORECASE), options) for name, pattern, options in _MENTION_PATTERNS]


def unapplied_mentions(reply: str, set_options: Sequence[str]) -> list[str]:
    """The kinds of change `reply` talks about although none of their options was set, each as its first option's
    name, in a fixed order. A question (the designer asking what the owner wants) changes nothing and claims nothing.
    Option names written as such (`shipping_fee`) read as their words."""
    if reply.rstrip().endswith("?"):
        return []
    done, text = set(set_options), reply.replace("_", " ")
    return [options[0] for _name, pattern, options in _MENTIONS if pattern.search(text) and not done.intersection(options)]


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
    lines = [f"{'Owner' if m.role == 'owner' else 'Designer'}: {m.text}" for m in messages]
    start, used = len(lines), 0
    for line in reversed(lines):
        size = len(line.encode("utf-8")) + 1
        if start < len(lines) and used + size > _HISTORY_BYTES:
            break
        start -= 1
        used += size  # Always retain the complete latest request, even when it alone exceeds the history budget.
    while start < len(lines) - 1 and messages[start].role == "designer":
        start += 1  # A reply without its owner's request is misleading context.
    talk = "\n".join(lines[start:])
    if start:
        talk = "[Earlier messages omitted; the current design above is authoritative.]\n" + talk
    system = DESIGN_PROMPT.format(styles=", ".join(PAGE_STYLES), currency=site.currency.upper())
    user = (f"{_describe(site, options)}\n\nConversation:\n{talk}\n\n"
            'Return the edit result: {"updates":[{"option":"the_option_to_change","value":"its new value"}],"reply":"your answer"}. '
            "Use the option's actual value type and an empty updates list when nothing should change. "
            "Return actual changes, not a JSON schema; do not copy $defs, properties, required or type definitions.")
    reply = await llm.generate_structured_async(DesignReply, system, user, max_retries=2, seed=0)
    if reply.changes.model_dump(exclude_none=True) or reply.reply.rstrip().endswith("?"):
        return reply
    # Small models often describe a change without setting it: ask once more, saying so.
    return await llm.generate_structured_async(
        DesignReply, system, f"{user}\n\nYour previous answer set no option. Set every option you change, or ask a question.",
        max_retries=2, seed=1)
