"""Prompt and answer schema of the model shopper.

Written in English, like the vision shopper's shelf prompts: small local VLMs follow English instructions far more
reliably. The "Language" block keeps the narrative fields (search text, thoughts) in English.
"""

from typing import Self

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from store_emulator.domain.online import Arrival, ExitSurvey, OnlineShopper, OnlineSite, Vision
from store_emulator.engine.prompting import display_price

SYSTEM_PROMPT = """You role-play one online shopper using a web browser.
{view}
Every element the shopper can click carries a red number badge, and the list of options says what each number does.

Choose what THIS shopper does next, in character: their goal, budget, patience, device and comfort with websites.
Real shoppers search, browse, compare, get tempted by deals, abandon carts when costs surprise them, and leave sites
that are slow, confusing or pushy. Do not be more diligent, patient or wealthy than this person is.
Closing the tab is a real choice, just as buying is.

Reply in JSON:
- option: the number of the ONE option the shopper picks
- search_text: if that option is the search box, the few words the shopper types; otherwise ""
- thought: what the shopper thinks right now, in the first person, at most 20 words

## Language
Write search_text and thought in English."""

_VIEW_IMAGE = "The image is a screenshot of the browser window: the page the shopper sees right now."
_VIEW_TEXT = "You get the page the shopper sees right now as text, top to bottom, the way a screen reader reads it."
_HISTORY = 8


def system_prompt(*, vision: bool) -> str:
    return SYSTEM_PROMPT.replace("{view}", _VIEW_IMAGE if vision else _VIEW_TEXT)


def _level(value: float) -> str:
    return "low" if value < 0.4 else "high" if value > 0.7 else "medium"


def age_words(age: str) -> str:
    return "in their 60s or older" if age == "60s+" else f"in their {age}" if age != "10s" else "a teenager"


def user_prompt(
    site: OnlineSite, shopper: OnlineShopper, *, page_title: str, options: list[tuple[int, str]], history: list[str],
    elapsed: float, load_seconds: float, cart: tuple[int, int, tuple[str, ...]], outline: list[str] | None,
) -> str:
    """`options`: (number, what it does), in number order. `cart`: (items, subtotal, product names). `outline`: the
    page as text (text policy) or None (the screenshot shows it)."""
    money = display_price
    count, subtotal, names = cart
    lines = [
        f"Shopper: {shopper.identity}, {age_words(shopper.age_group)}, {shopper.gender.lower()}, on a {shopper.device}.",
    ]
    if shopper.description and shopper.persona_id:
        lines.append(shopper.description)
    if shopper.vision != "typical":
        lines.append(EYESIGHT[shopper.vision] + ("" if outline is not None else " " + _EYESIGHT_IMAGE))
    lines += [
        f"Why they are on {site.name}: {shopper.goal}.",
        f"Budget: {money(shopper.budget, site.currency)}." if shopper.budget else "Budget: no fixed limit.",
        f"Price sensitivity: {_level(shopper.price_sensitivity)}. Comfort with websites: {_level(shopper.tech_savvy)}. "
        f"Has an account on this site: {'yes' if shopper.has_account else 'no'}.",
        f"Time on the site so far: {int(elapsed) // 60}:{int(elapsed) % 60:02d}; they give it about "
        f"{max(1, round(shopper.patience_sec / 60))} minutes in all.",
        f"This page took {load_seconds:.1f} seconds to load.",
        (f"Cart: {count} item{'s' if count != 1 else ''}, {money(subtotal, site.currency)} ({', '.join(names[:4])})."
         if count else "Cart: empty."),
    ]
    if history:
        lines.append("What they did so far:")
        start = max(0, len(history) - _HISTORY)
        lines += [f"{start + i + 1}. {text}" for i, text in enumerate(history[start:])]
    else:
        lines.append("This is the first page they see on this site." + ARRIVED[shopper.arrival])
    lines += ["", f"Current page: {page_title}"]
    if outline is not None:
        lines += outline
    lines.append("Options:")
    lines += [f"[{number}] {label}" for number, label in options]
    lines.append("Which option does the shopper pick next?")
    return "\n".join(lines)


EYESIGHT: dict[Vision, str] = {
    "low_vision": "The shopper has low vision: small text and thin lines are hard for them to make out. The site's "
                  "settings may offer large text.",
    "color_blind": "The shopper is red-green colour-blind: red sale tags and green stock notes do not stand out for them.",
    "aging_eyes": "The shopper's eyes are older: small print is tiring to read without reading glasses.",
    "typical": "",
}
_EYESIGHT_IMAGE = "The screenshot shows the page the way they see it."
ARRIVED: dict[Arrival, str] = {
    "direct": "", "search_engine": " They came from a search engine result.",
    "social": " They came from a social media post.", "email": " They came from the shop's email newsletter.",
}

_TEXT_LIMITS = {"search_text": 60, "thought": 200, "frustration": 200, "improvement": 200}


class BrowserChoice(BaseModel):
    option: int = Field(ge=0, le=10_000)
    search_text: str = Field(default="", max_length=60)
    thought: str = Field(default="", max_length=200)

    @field_validator("option", mode="before")
    @classmethod
    def _numeric(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("option must be a number, not true or false")
        if isinstance(value, str) and value.strip().lstrip("[#").rstrip("]").isdigit():
            return int(value.strip().lstrip("[#").rstrip("]"))
        return value

    @field_validator("search_text", "thought", mode="before")
    @classmethod
    def _clip(cls, value: object, info: ValidationInfo) -> object:
        """A wordy answer is cut rather than discarded: the choice in it is still valid."""
        if value is None:
            return ""
        limit = _TEXT_LIMITS[info.field_name or "thought"]
        return value[:limit] if isinstance(value, str) else value


def choice_model(numbers: list[int], search_number: int | None) -> type[BrowserChoice]:
    """The answer schema of one page: `option` limited to the page's numbers (a grammar for servers that compile
    the schema, a validation error with the valid numbers for the rest)."""
    allowed = set(numbers)

    class PageChoice(BrowserChoice):
        option: int = Field(json_schema_extra={"enum": list(numbers)})

        @model_validator(mode="after")
        def _on_page(self) -> Self:
            if self.option not in allowed:
                raise ValueError(f"option must be one of the numbered options on this page: {sorted(allowed)}")
            if search_number is not None and self.option == search_number and not self.search_text.strip():
                raise ValueError("The shopper picked the search box: put the words they type in search_text.")
            return self

    return PageChoice


SURVEY_PROMPT = """You role-play one online shopper who has just left a web shop. Answer a short survey about the
visit, in character and honestly: a shopper who was annoyed or could not find what they wanted gives low scores.

Reply in JSON:
- satisfaction: 1 (very dissatisfied) to 7 (very satisfied) with the visit
- ease: 1 (very difficult) to 7 (very easy): how easy it was to do what they came for
- recommend: 0 to 10: how likely they are to recommend this shop to a friend
- would_return: true or false: would they shop here again
- frustration: the biggest annoyance of the visit in at most 20 words, or "" if there was none
- improvement: one change that would have helped them, at most 20 words, or ""

## Language
Write frustration and improvement in English."""


def survey_prompt(site: OnlineSite, shopper: OnlineShopper, *, history: list[str], outcome: str, seconds: float,
                  paid: int) -> str:
    lines = [
        f"Shopper: {shopper.identity}, {age_words(shopper.age_group)}, {shopper.gender.lower()}, on a {shopper.device}.",
        f"Why they went to {site.name}: {shopper.goal}.",
    ]
    if shopper.vision != "typical":
        lines.append(EYESIGHT[shopper.vision])
    lines.append("What they did on the site:")
    lines += [f"{i + 1}. {text}" for i, text in enumerate(history[-20:])]
    lines.append(f"How the visit ended: {outcome}. Time on the site: {int(seconds) // 60} min {int(seconds) % 60} s.")
    if paid:
        lines.append(f"They paid {display_price(paid, site.currency)}.")
    lines.append("How do they answer the survey?")
    return "\n".join(lines)


class SurveyAnswer(BaseModel):
    satisfaction: int = Field(ge=1, le=7)
    ease: int = Field(ge=1, le=7)
    recommend: int = Field(ge=0, le=10)
    would_return: bool
    frustration: str = Field(default="", max_length=200)
    improvement: str = Field(default="", max_length=200)

    @field_validator("satisfaction", "ease", "recommend", mode="before")
    @classmethod
    def _score(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("scores are numbers, not true or false")
        return value

    @field_validator("frustration", "improvement", mode="before")
    @classmethod
    def _clip(cls, value: object, info: ValidationInfo) -> object:
        if value is None:
            return ""
        limit = _TEXT_LIMITS[info.field_name or "frustration"]
        return value[:limit] if isinstance(value, str) else value

    def survey(self) -> ExitSurvey:
        return ExitSurvey.model_validate(self.model_dump())
