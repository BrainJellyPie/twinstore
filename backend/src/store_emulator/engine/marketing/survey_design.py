"""A concept test drafted from the question the user wants answered.

"Which of our two new labels looks more premium to people in their twenties?" becomes the product images to show (from
the project's library, by name), the questions to ask, the brief respondents read, an optional shelf price and the
panel's age and gender quotas. Images that are not in the library are dropped and reported; nothing runs.
"""

from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
import re
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from store_emulator.domain.marketing import QuestionKind
from store_emulator.domain.persona import AGE_GROUPS, GENDERS, AgeGroup, Gender
from store_emulator.engine.prompting import relevant_first

ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}
MAX_LISTED = 80
MAX_STIMULI = 4
MAX_PRICE = 9_007_199_254_740_991
_KINDS: tuple[QuestionKind, ...] = ("purchase_intent", "appeal", "value", "uniqueness", "price_vw", "preference", "open")


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Draft(BaseModel):
    name: str = Field(max_length=80, description="a short test name")
    images: list[str] = Field(default_factory=list[str], max_length=6,
                              description="one to four listed product images to show side by side, exactly as listed")
    questions: list[Literal["purchase_intent", "appeal", "value", "uniqueness", "price_vw", "preference", "open"]] = Field(
        min_length=1, max_length=7)
    context: str = Field(default="", max_length=400, description="one or two sentences respondents read before answering")
    reference_price: float | None = Field(default=None, ge=0, description="shelf price shown with image A, major units")
    age_groups: list[AgeGroup] = Field(default_factory=list[AgeGroup], max_length=6)
    genders: list[Gender] = Field(default_factory=list[Gender], max_length=2)
    rationale: str = Field(default="", max_length=500)

    @field_validator("images", "age_groups", "genders", mode="before")
    @classmethod
    def _optional_lists(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("context", "rationale", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> object:
        return "" if value is None else value


class SurveyDesign(BaseModel):
    name: str
    stimuli: list[str] = []            # product image ids, A to D
    stimulus_names: list[str] = []
    questions: list[QuestionKind]
    context: str = ""
    reference_price: int | None = None  # minor units
    currency: str
    age_groups: list[AgeGroup] = []
    genders: list[Gender] = []
    rationale: str = ""
    warnings: list[str] = []


DESIGN_PROMPT = """You design concept tests for retail managers: synthetic respondents look at one to four product
images side by side (A to D) and answer a short standard questionnaire. From the manager's question, draft one test:

- images: the listed product images the question is about, written exactly as listed, the current or reference one
  first; one image when the question is about a single product, two to four when it compares them;
- questions, from: purchase_intent (likelihood to buy, 1 to 5), appeal (pack appeal), value (value for money),
  uniqueness (stands out from the usual shelf), price_vw (Van Westendorp price range for image A), preference (which
  one they would take home; only with two or more images), open (why, in their own words). Ask what the question
  needs, and include open unless the manager asks for scales only;
- context: what respondents are told about the product, plainly, without leading them toward an answer;
- reference_price: the shelf price shown with image A in major units of {currency}, only when price matters to the
  question and a listed price or the question gives it;
- age_groups and genders: quotas only when the question names a group; otherwise leave them empty (everyone);
- a short name and rationale.
Use [] for unspecified images, age_groups and genders, and empty strings for unspecified context and rationale.
Use null only when reference_price is not given.
Write in English."""


def _listing(packages: Sequence[tuple[str, str, str]], question: str) -> str:
    """packages: (image name, brand, what it shows, e.g. 'Cola 500 ml at $1.99 on Drinks 1')."""
    entries = [(brand, f"{name} {shows}", f'"{name}"{f", brand {brand}" if brand else ""}{f", shows {shows}" if shows else ""}')
               for name, brand, shows in packages]
    shown = relevant_first(entries, question, MAX_LISTED)
    if not shown:
        return "Product images: none yet"
    return "Product images (write the quoted name only):\n" + "\n".join(f"- {line}" for line in shown)


def _resolve(asked: str, ids: dict[str, dict[str, str]]) -> tuple[str, str] | None:
    """Resolve an exact name or a uniquely longest name copied with its description."""
    key = asked.strip().strip('"').casefold()
    if not key:
        return None
    candidates = [key] if key in ids else [n for n in ids if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", key)]
    if not candidates:
        return None
    longest = max(map(len, candidates))
    matches = {aid: name for n in candidates if len(n) == longest for aid, name in ids[n].items()}
    return next(iter(matches.items())) if len(matches) == 1 else None


def to_design(draft: _Draft, packages: Sequence[tuple[str, str]], currency: str) -> SurveyDesign:
    """Resolve unique image identities and representable minor-unit prices for the builder."""
    ids: dict[str, dict[str, str]] = {}
    for name, aid in packages:
        if name.strip():
            ids.setdefault(name.strip().casefold(), {})[aid] = name.strip()
    warnings: list[str] = []
    stimuli: list[str] = []
    names: list[str] = []
    for asked in draft.images:
        hit = _resolve(asked, ids)
        if hit is None:
            warnings.append(f'No unique product image "{asked}" in the library (missing or ambiguous name); it was left out.')
        elif hit[0] not in stimuli:
            stimuli.append(hit[0])
            names.append(hit[1][:28])
    if len(stimuli) > MAX_STIMULI:
        warnings.append(f"Only the first {MAX_STIMULI} images are shown; {len(stimuli) - MAX_STIMULI} more were left out.")
        stimuli, names = stimuli[:MAX_STIMULI], names[:MAX_STIMULI]
    if not packages:
        warnings.append("The product library has no images yet. Add the packs to compare, then pick them below.")
    elif not stimuli:
        warnings.append("None of the drafted images is in the library. Pick the images to show below.")
    questions: list[QuestionKind] = [k for k in _KINDS if k in draft.questions and (k != "preference" or len(stimuli) > 1)]
    if not questions:
        questions = ["purchase_intent", "appeal", "open"]
    zero = currency.upper() in ZERO_DECIMAL
    price = draft.reference_price
    reference: int | None = None
    if price is not None and price > 0:
        if not isfinite(price):
            warnings.append("The reference price is not finite; it was left out.")
        else:
            amount = Decimal(str(price)) * (1 if zero else 100)
            if amount > MAX_PRICE:
                warnings.append("The reference price exceeds the safe integer limit; it was left out.")
            else:
                rounded = int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if rounded == 0:
                    warnings.append(f"The reference price rounds to zero in {currency.upper()}; it was left out.")
                else:
                    reference = rounded
    return SurveyDesign(
        name=draft.name.strip()[:80], stimuli=stimuli, stimulus_names=names, questions=questions,
        context=draft.context.strip()[:300], reference_price=reference, currency=currency.upper(),
        age_groups=[a for a in AGE_GROUPS if a in draft.age_groups], genders=[g for g in GENDERS if g in draft.genders],
        rationale=draft.rationale.strip(), warnings=warnings,
    )


async def design_survey(
    llm: StructuredLLM, question: str, currency: str, packages: Sequence[tuple[str, str, str, str]],
) -> SurveyDesign:
    """packages: (image name, asset id, brand, what it shows) for every image in the project's library."""
    draft = await llm.generate_structured_async(
        _Draft, DESIGN_PROMPT.format(currency=currency.upper()),
        f"{_listing([(n, b, s) for n, _, b, s in packages], question)}\n\nQuestion: {question.strip()}",
        max_retries=2, seed=0,
    )
    return to_design(draft, [(n, aid) for n, aid, _, _ in packages], currency)
