"""Prompt and response schema for the vision-language shopper.

Written in English: the target models are small local VLMs (≤2B parameters on CPU),
which follow English instructions far more reliably than Korean ones. The Korean cue
words of the behavior presets are glossed into English here (LLM-internal site, see
AGENTS.md i18n policy).
"""

import re

from pydantic import BaseModel, Field

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.persona import Persona
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
