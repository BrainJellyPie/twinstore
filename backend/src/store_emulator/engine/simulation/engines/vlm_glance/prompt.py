"""Prompt and response schema for the vision-language shopper.

Written in English: the target models are small local VLMs (≤2B parameters on CPU),
which follow English instructions far more reliably than Korean ones. The Korean cue
words of the behavior presets are glossed into English here (LLM-internal site, see
AGENTS.md i18n policy).
"""

import re
from collections.abc import Callable
from functools import cache
from statistics import median
from typing import ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Weekday
from store_emulator.engine.perception import MarkedItem, ShelfView
from store_emulator.engine.prompting import display_price

SYSTEM_PROMPT = """You role-play one shopper walking through a convenience store.
The image is the shelf this shopper is passing right now. Each product shows its name on the package and a yellow price tag "#N price" below it.

Look at the whole shelf, top to bottom. Pick the ONE product that would most likely catch THIS shopper's eye, then rate how tempted they are to take it right now:
0 = would walk past, 3 = a passing glance, 6 = would pick it up and look, 9-10 = would definitely grab it.
Be realistic: a shopper who came for something else is rarely tempted, and price matters when money is tight.

Reply in JSON:
- product: the product name exactly as printed, or "" if nothing at all fits
- number: its N from the price tag, or 0
- interest: 0 to 10
- reason: a few words"""


class ShelfGlance(BaseModel):
    """The model names the most eye-catching product and how tempting it is. Whether the
    shopper actually buys is a seeded draw from that interest (see VLMGlanceConfig), so
    small models' habit of always answering "yes" cannot set the purchase rate."""
    product: str = Field(default="", max_length=60)
    number: int = Field(default=0, ge=0, le=99)
    interest: int = Field(default=0, ge=0, le=10)
    reason: str = Field(default="", max_length=80)

    @field_validator("product", "reason", mode="before")
    @classmethod
    def _clip_long_text(cls, value: object, info: ValidationInfo) -> object:
        """A wordy answer is cut rather than discarded: the decision in it is still valid
        (models without a JSON grammar, e.g. cloud APIs, sometimes exceed the limit)."""
        limit = 60 if info.field_name == "product" else 80
        return value[:limit] if isinstance(value, str) else value


_CUE_GLOSS: dict[str, str] = {
    # state
    "피곤함": "tired", "좀지침": "a bit worn out", "배고픔": "hungry", "출출함": "peckish",
    "목마름": "thirsty", "나른함": "sluggish", "졸림": "sleepy", "기력충만": "full of energy",
    "상쾌함": "refreshed", "발걸음가벼움": "light on their feet", "몸이무거움": "feeling heavy",
    "에너지넘침": "bursting with energy",
    # purse
    "가성비추구": "looking for value", "절약모드": "saving money", "예산빠듯": "on a tight budget",
    "카드값걱정": "worried about the card bill", "아끼는중": "cutting back", "월급직후": "just got paid",
    "자기보상": "in a treat-yourself mood", "여유있음": "comfortable with money",
    "프리미엄기분": "in the mood for something premium", "충동경계중": "trying not to impulse-buy",
    "플렉스모드": "in a splurge mood", "무계획소비": "spending without a plan",
    "포인트소진": "using up reward points", "이왕이면좋은걸": "prefers the better option",
    # emotion
    "무덤덤": "indifferent", "기분좋음": "in a good mood", "콧노래흥얼": "humming happily",
    "느긋함": "relaxed", "심드렁": "unenthusiastic", "짜증남": "annoyed", "신경날카로움": "on edge",
    "스트레스만땅": "very stressed", "설렘": "excited", "들뜸": "giddy", "울적함": "a bit down",
    "심심함": "bored", "초조함": "anxious", "후련함": "relieved", "허전함": "feeling empty",
    # company
    "혼자": "alone", "친구랑": "with a friend", "연인과 같이 옴": "with their partner",
    "가족이랑": "with family", "아이데리고": "with a child", "동료랑": "with a coworker",
    "부모님이랑": "with their parents", "후배랑": "with a junior colleague",
    "윗사람이랑": "with a senior colleague", "이웃이랑": "with a neighbor",
}

_PATTERN_GLOSS: dict[str, str] = {
    "purposeful": "came for specific items and leaves once found",
    "habitual": "regular who buys the same things",
    "routine_refill": "restocking usual items",
    "urgent": "in a hurry",
    "quick_snack": "wants one quick snack",
    "exploratory": "likes to look around",
    "hungry_wandering": "hungry and browsing for food",
    "leisurely": "strolling without hurry",
    "social_browsing": "browsing together and chatting",
    "impulse_heavy": "easily tempted",
    "window_shopping": "just looking",
    "deal_hunting": "hunting for deals and promotions",
}

_AGE: dict[str, str] = {"10s": "teenage", "20s": "twenty-something", "30s": "thirty-something",
                        "40s": "forty-something", "50s": "fifty-something", "60s+": "senior"}


def _gloss(word: str | None) -> str | None:
    if not word:
        return None
    return _CUE_GLOSS.get(word, word)


def user_prompt(
    persona: Persona,
    cue: BehaviorCue,
    pattern: BehaviorPattern,
    view: ShelfView,
    *,
    basket: list[str],
    money_left: int | None,
    currency: str,
    situation: str = "",
) -> str:
    mood = ", ".join(g for g in (_gloss(cue.state), _gloss(cue.emotion), _gloss(cue.purse), _gloss(cue.company)) if g)
    who = f"A {_AGE.get(persona.age_group, persona.age_group)} {persona.gender.lower()}, {persona.identity}."
    lines = [
        f"Shopper: {who} {persona.description}".strip(),
        f"Came for: {persona.intent or persona.purpose}",
    ]
    if persona.behavior_tendency:
        lines.append(f"Habits: {persona.behavior_tendency}")
    lines.append(f"Shopping style today: {_PATTERN_GLOSS.get(pattern.id, pattern.id.replace('_', ' '))}.")
    if mood:
        lines.append(f"Right now: {mood}.")
    if situation:
        lines.append(f"Today: {situation}.")
    lines.append(f"Already in basket: {', '.join(basket) if basket else 'nothing yet'}.")
    if money_left is not None:
        lines.append(f"Still willing to spend: about {display_price(max(0, money_left), currency)}.")
    kind = "fridge" if view.rack.type.value == "fridge" else "shelf"
    lines.append(f"Passing: the {view.rack.rack_name or kind} {kind}. Does anything here catch this shopper's eye?")
    return "\n".join(lines)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 1 or w.isdigit()}


def resolve(view: ShelfView, glance: ShelfGlance) -> tuple[MarkedItem | None, str]:
    """Map the model's answer to a product on the shelf.

    Small VLMs read printed names more reliably than they tie a badge number to the
    right product, so the name decides when it clearly matches one product; the number
    is the fallback. Returns (item, how) with how ∈ {"none", "name", "number", "invalid"}.
    """
    name = glance.product.strip()
    if not name and glance.number == 0:
        return None, "none"
    if name:
        said = _words(name)
        best: MarkedItem | None = None
        best_score = 0.0
        for marked in view.items:
            target = _words(marked.item.name)
            if not target:
                continue
            score = len(said & target) / len(said | target)
            if score > best_score:
                best, best_score = marked, score
        if best is not None and best_score >= 0.5:
            return best, "name"
    by_number = view.by_mark(glance.number) if glance.number else None
    if by_number is not None:
        return by_number, "number"
    return None, "invalid"


def combine_votes(view: ShelfView, answers: list[tuple[str, ShelfGlance]]) -> tuple[ShelfGlance, float]:
    """Ensemble vote: the product named by most members wins (ties → higher summed interest).

    The combined interest is the mean over all members, counting 0 for members that named
    something else, so a lone enthusiast cannot drive a purchase. Returns (glance, agreement)
    where agreement is the share of members that named the winner.
    """
    tally: dict[str, list[ShelfGlance]] = {}
    for _, glance in answers:
        hit, _ = resolve(view, glance)
        tally.setdefault(hit.item.sku if hit else "", []).append(glance)
    named = {sku: gs for sku, gs in tally.items() if sku}
    if not named:
        return ShelfGlance(), len(tally.get("", [])) / max(1, len(answers))
    winner = max(named, key=lambda sku: (len(named[sku]), sum(g.interest for g in named[sku]), sku))
    marked = next(m for m in view.items if m.item.sku == winner)
    supporters = named[winner]
    interest = round(sum(g.interest for g in supporters) / len(answers))
    reason = next((g.reason for g in supporters if g.reason), "")
    combined = ShelfGlance(product=marked.item.name, number=marked.mark, interest=interest, reason=reason)
    return combined, len(supporters) / len(answers)


# ── planning at the entrance ──────────────────────────────────────────────

PLAN_ITEMS_LIMIT = 4  # upper bound of VLMGlanceConfig.max_plan_items

PLAN_SYSTEM_PROMPT = """You role-play one shopper standing at the door of a convenience store.
{image_line}Decide what THIS shopper came for, given who they are, the time, today's situation and their money.

Reply in JSON:
- mission: what they came for, at most 12 words
- enter: true if they go in; false only if they would turn around (the store has nothing they need, or today's situation puts them off)
- items: {items_rule}
- reason: a few words"""

_PLAN_IMAGE_LINE = ("The image is the store directory map by the door: racks labeled by category, "
                    "red SALE ribbons mark promotions.\n")


_TEXT_LIMITS: dict[str, int] = {"category": 30, "product": 48, "mission": 72, "reason": 48}


def _clip(value: object, info: ValidationInfo) -> object:
    """Over-long text is cut instead of failing the call (grammar-constrained servers never send it)."""
    limit = _TEXT_LIMITS.get(info.field_name or "", 0)
    return value[:limit] if isinstance(value, str) and limit else value


class PlannedItem(BaseModel):
    category: str = Field(default="", max_length=_TEXT_LIMITS["category"])
    product: str = Field(default="", max_length=_TEXT_LIMITS["product"])
    qty: int = Field(default=1, ge=1, le=3)

    _clip_text = field_validator("category", "product", mode="before")(_clip)

    @field_validator("qty", mode="before")
    @classmethod
    def _clamp_qty(cls, value: object) -> object:
        return min(3, max(1, value)) if isinstance(value, int) and not isinstance(value, bool) else value


class EntryDecision(BaseModel):
    """What the shopper came for. Small and flat with short string bounds: on grammar-constrained
    local servers the bounds cap the output tokens, which dominate the latency of tiny CPU models."""
    items_limit: ClassVar[int] = PLAN_ITEMS_LIMIT

    # Mission first: small models decide `enter` better once they have written down their purpose.
    mission: str = Field(default="", max_length=_TEXT_LIMITS["mission"])
    enter: bool = True
    items: list[PlannedItem] = Field(default_factory=list[PlannedItem], max_length=PLAN_ITEMS_LIMIT)
    reason: str = Field(default="", max_length=_TEXT_LIMITS["reason"])

    _clip_text = field_validator("mission", "reason", mode="before")(_clip)

    @field_validator("items", mode="before")
    @classmethod
    def _trim_items(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        items = cast(list[object], value)
        return items[:cls.items_limit]


@cache
def entry_decision_model(max_items: int) -> type[EntryDecision]:
    """EntryDecision whose JSON schema allows at most `max_items` items (grammar-enforced on local
    servers; small models otherwise fill every slot the schema allows). Longer lists are trimmed."""
    if max_items >= PLAN_ITEMS_LIMIT:
        return EntryDecision

    class BoundedEntryDecision(EntryDecision):
        model_config = ConfigDict(title=f"EntryDecision{max_items}")
        items_limit: ClassVar[int] = max_items
        items: list[PlannedItem] = Field(default_factory=list[PlannedItem], max_length=max_items)

    return BoundedEntryDecision


_WEEKDAY_NAMES: dict[Weekday, str] = {
    Weekday.MON: "Monday", Weekday.TUE: "Tuesday", Weekday.WED: "Wednesday", Weekday.THU: "Thursday",
    Weekday.FRI: "Friday", Weekday.SAT: "Saturday", Weekday.SUN: "Sunday",
}


def plan_system_prompt(*, max_items: int, image: bool) -> str:
    items_rule = (
        f"at most {max_items} things they plan to buy. category: one category from the store directory. "
        "product: a product name from the directory, or a short description. qty: 1 to 3"
        if max_items > 0 else "leave empty: today they only browse inside, no planned purchase"
    )
    return PLAN_SYSTEM_PROMPT.format(image_line=_PLAN_IMAGE_LINE if image else "", items_rule=items_rule)


def plan_user_prompt(
    persona: Persona,
    cue: BehaviorCue,
    pattern: BehaviorPattern,
    *,
    day: Weekday,
    hour: int,
    situation: str,
    budget: int | None,
    currency: str,
    directory: str,
) -> str:
    mood = ", ".join(g for g in (_gloss(cue.state), _gloss(cue.emotion), _gloss(cue.purse), _gloss(cue.company)) if g)
    who = f"A {_AGE.get(persona.age_group, persona.age_group)} {persona.gender.lower()}, {persona.identity}."
    lines = [f"Shopper: {who} {persona.description}".strip()]
    if persona.intent or persona.purpose:
        lines.append(f"Usually comes for: {persona.intent or persona.purpose}")
    if persona.preferred_categories:
        lines.append(f"Usually buys: {', '.join(persona.preferred_categories[:5])}")
    if persona.behavior_tendency:
        lines.append(f"Habits: {persona.behavior_tendency}")
    lines.append(f"Shopping style today: {_PATTERN_GLOSS.get(pattern.id, pattern.id.replace('_', ' '))}.")
    if mood:
        lines.append(f"Right now: {mood}.")
    lines.append(f"Time: {_WEEKDAY_NAMES.get(day, 'a weekday')} {hour:02d}:00.")
    lines.append(f"Today: {situation}." if situation else "Today: an ordinary day.")
    if budget is not None:
        lines.append(f"Money they are willing to spend: about {display_price(max(0, budget), currency)}.")
    lines.append("Store directory:")
    lines.append(directory)
    lines.append("Does this shopper go in, and what do they plan to buy?")
    return "\n".join(lines)


def combine_plan_votes(
    answers: list[tuple[str, EntryDecision]], item_key: Callable[[PlannedItem], str],
) -> tuple[EntryDecision, float]:
    """Ensemble vote on an entry plan: `enter` by majority (a tie enters), items named by at least
    half of the members (identity = `item_key`, e.g. the resolved product or category; quantity =
    median of the supporters'). Returns (plan, agreement = share of members on the majority side)."""
    n = len(answers)
    if n == 0:
        return EntryDecision(), 0.0
    entering = [d for _, d in answers if d.enter]
    enter = 2 * len(entering) >= n
    side = entering if enter else [d for _, d in answers if not d.enter]
    agreement = len(side) / n
    if not enter:
        first = side[0]
        return EntryDecision(enter=False, mission=first.mission, reason=first.reason), agreement
    support: dict[str, list[PlannedItem]] = {}
    for _, decision in answers:
        seen: set[str] = set()
        for item in decision.items:
            key = item_key(item)
            if key in seen:
                continue
            seen.add(key)
            support.setdefault(key, []).append(item)
    order = list(support)
    kept = sorted((k for k in order if 2 * len(support[k]) >= n), key=lambda k: (-len(support[k]), order.index(k)))
    items = [
        support[k][0].model_copy(update={"qty": round(median(i.qty for i in support[k]))})
        for k in kept[:PLAN_ITEMS_LIMIT]
    ]
    keyset = set(kept)
    lead = max(side, key=lambda d: sum(1 for i in d.items if item_key(i) in keyset))
    return EntryDecision(enter=True, mission=lead.mission, items=items, reason=lead.reason), agreement
