"""Concept tests answered by synthetic respondents: each persona looks at the stimuli (product images
side by side, labelled A–D) and answers a short questionnaire through a vision-language model.

Scales are 1–5. Van Westendorp prices are asked for stimulus A. The aggregation helpers are plain
statistics (normal-approximation CIs for means, Wilson intervals for shares) and need no model.
"""

import asyncio
import math
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel, Field, create_model, field_validator

from store_emulator.domain.marketing import (
    PreferenceShare,
    PriceRange,
    QuestionKind,
    ScaleSummary,
    SurveyAnswer,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import stable_seed
from store_emulator.engine.capture.detect import image_data_url
from store_emulator.engine.perception.shelf_render import load_font
from store_emulator.engine.prompting import display_price

LETTERS = "ABCD"
_MAX_PRICE_MINOR = 9_007_199_254_740_991
SCALES: tuple[QuestionKind, ...] = ("purchase_intent", "appeal", "value", "uniqueness")
SCALE_TEXT: dict[str, str] = {
    "purchase_intent": "how likely you are to buy it on your next trip (1 = definitely not, 5 = definitely)",
    "appeal": "how appealing the package looks to you (1 = not at all, 5 = very)",
    "value": "how good value it seems for the money (1 = poor, 5 = excellent)",
    "uniqueness": "how different it is from what you usually see on the shelf (1 = the same, 5 = very different)",
}


class VisionLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...


class StudyResponse(BaseModel):
    """Preserve measured answers when their optional explanation is absent."""

    @field_validator("why", mode="before", check_fields=False)
    @classmethod
    def _absent_reason(cls, value: object) -> object:
        return "" if value is None else value


def stimulus_board(images: Sequence[Image.Image], names: Sequence[str], *, height: int = 520) -> Image.Image:
    """The stimuli side by side on a light card, each with a letter and its name underneath."""
    pad, gap, label_h = 28, 36, 64
    cells: list[Image.Image] = []
    for img in images:
        im = ImageOps.exif_transpose(img).convert("RGBA")
        im.thumbnail((int(height * 0.8), height))
        cells.append(im)
    width = pad * 2 + sum(c.width for c in cells) + gap * (len(cells) - 1)
    board = Image.new("RGB", (max(width, 360), pad * 2 + height + label_h), (246, 245, 242))
    d = ImageDraw.Draw(board)
    font, small = load_font(30, bold=True), load_font(20)
    x = pad
    for i, cell in enumerate(cells):
        board.paste(cell, (x, pad + height - cell.height), cell)
        cx = x + cell.width // 2
        d.text((cx, pad + height + 8), LETTERS[i], font=font, fill=(20, 20, 24), anchor="mt")
        if i < len(names) and names[i]:
            d.text((cx, pad + height + 42), names[i][:28], font=small, fill=(90, 90, 96), anchor="mt")
        x += cell.width + gap
    return board


def response_model(questions: Sequence[QuestionKind], stimuli: int, *, minor_per_major: int = 100) -> type[BaseModel]:
    """The answer schema for this questionnaire (flat fields keep small models on track)."""
    fields: dict[str, Any] = {}
    for q in questions:
        if q in SCALES:
            for i in range(stimuli):
                fields[f"{q}_{LETTERS[i]}"] = (int, Field(ge=1, le=5))
        elif q == "price_vw":
            maximum = _MAX_PRICE_MINOR / minor_per_major
            fields["too_cheap"] = (float, Field(ge=0, le=maximum, allow_inf_nan=False, description="price at which A is so cheap you would doubt its quality"))
            fields["cheap"] = (float, Field(ge=0, le=maximum, allow_inf_nan=False, description="price at which A is a bargain"))
            fields["expensive"] = (float, Field(ge=0, le=maximum, allow_inf_nan=False, description="price at which A starts to feel expensive"))
            fields["too_expensive"] = (float, Field(ge=0, le=maximum, allow_inf_nan=False, description="price at which A is too expensive to consider"))
        elif q == "preference" and stimuli > 1:
            fields["preferred"] = (Literal[tuple(LETTERS[:stimuli])], ...)
        elif q == "open":
            fields["why"] = (str, Field(default="", max_length=240))
    return create_model("SurveyResponse", __base__=StudyResponse, **fields)


SURVEY_PROMPT = """You answer a short shopper survey as the person described below, honestly and in character: your age,
budget, habits and mood decide your answers, not what a marketer would like to hear. Look at the products in the image
(labelled with letters). Answer every question. Scales run from 1 to 5; most people use the middle of the scale for
ordinary products. Prices are finite, realistic amounts per product in the currency given, without symbols;
do not repeat digits or exceed the schema's price limits. Write any text in English.
Use an empty string, not null, when no explanation is given."""


def _questions_text(questions: Sequence[QuestionKind], stimuli: int, currency: str, reference: str) -> str:
    lines: list[str] = []
    labels = ", ".join(LETTERS[:stimuli])
    for q in questions:
        if q in SCALES:
            lines.append(f"- For each product ({labels}): {SCALE_TEXT[q]}.")
        elif q == "price_vw":
            lines.append(f"- For product A, in {currency}{reference}: at what price would it be so cheap you doubt its quality "
                         "(too_cheap), a bargain (cheap), getting expensive (expensive), too expensive to consider (too_expensive)?")
        elif q == "preference" and stimuli > 1:
            lines.append(f"- If you could take only one home, which one ({labels})?")
        elif q == "open":
            lines.append("- In one sentence: why did you answer that way?")
    return "\n".join(lines)


def persona_text(p: Persona, currency: str = "USD") -> str:
    budget = f"{display_price(p.budget_min, currency)}–{display_price(p.budget_max, currency)}" if p.budget_max else "not set"
    lines = [f"Who you are: {p.identity} ({p.age_group}, {p.gender}). {p.description} "
             f"Today you came to {p.purpose or 'shop'}; budget {budget}."]
    if p.intent:
        lines.append(f"Purchase intent: {p.intent}")
    if p.behavior_tendency:
        lines.append(f"Shopping habits: {p.behavior_tendency}")
    if p.preferred_categories:
        lines.append(f"Preferred categories: {', '.join(p.preferred_categories)}")
    return "\n".join(lines)


async def survey_panel(
    llm: VisionLLM,
    personas: Sequence[Persona],
    board: Image.Image,
    questions: Sequence[QuestionKind],
    stimuli: int,
    *,
    context: str = "",
    currency: str = "USD",
    reference_price: str = "",
    minor_per_major: int = 100,
    seed: int = 0,
    max_concurrent: int = 6,
) -> list[SurveyAnswer]:
    """One answer per persona (failed calls come back with `error` set)."""
    model = response_model(questions, stimuli, minor_per_major=minor_per_major)
    url, _ = image_data_url(board, max_side=1280, fmt="JPEG")
    ref = f" (it is sold for {reference_price})" if reference_price else ""
    asks = _questions_text(questions, stimuli, currency, ref)
    sem = asyncio.Semaphore(max_concurrent)

    async def ask(p: Persona) -> SurveyAnswer:
        base = SurveyAnswer(respondent=p.id, age_group=str(p.age_group), gender=str(p.gender))
        user = f"{persona_text(p, currency)}\n\n{('About the products: ' + context) if context else ''}\n\nQuestions:\n{asks}"
        try:
            async with sem:
                r = await llm.generate_structured_with_image_async(
                    model, SURVEY_PROMPT, user, url, max_retries=2, seed=stable_seed("survey", seed, p.id),
                )
            data = r.model_dump()
            upd: dict[str, Any] = {}
            for q in SCALES:
                if q in questions:
                    upd[q] = [int(data[f"{q}_{LETTERS[i]}"]) for i in range(stimuli)]
            if "price_vw" in questions:
                for key in ("too_cheap", "cheap", "expensive", "too_expensive"):
                    upd[key] = round(float(data[key]) * minor_per_major)
            if "preferred" in data:
                upd["preferred"] = LETTERS.index(str(data["preferred"]))
            if "why" in data:
                upd["why"] = str(data["why"]).strip()
            return base.model_copy(update=upd)
        except Exception as e:  # noqa: BLE001 — one respondent failing must not sink the panel
            return base.model_copy(update={"error": f"{type(e).__name__}: {str(e)[:160]}"})

    return list(await asyncio.gather(*(ask(p) for p in personas)))


# ── aggregation ─────────────────────────────────────────────────────────────────

def likert_summary(values: Sequence[int], question: QuestionKind, stimulus: int) -> ScaleSummary:
    n = len(values)
    mean = sum(values) / n if n else 0.0
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n) if n else 0.0
    return ScaleSummary(
        question=question, stimulus=stimulus, n=n, mean=round(mean, 3), ci_low=round(mean - half, 3), ci_high=round(mean + half, 3),
        top2=round(sum(1 for v in values if v >= 4) / n, 4) if n else 0.0,
        distribution=[sum(1 for v in values if v == k) for k in range(1, 6)],
    )


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def preference_shares(preferred: Sequence[int], names: Sequence[str], stimuli: int) -> list[PreferenceShare]:
    n = len(preferred)
    out: list[PreferenceShare] = []
    for i in range(stimuli):
        share, lo, hi = wilson(sum(1 for v in preferred if v == i), n)
        out.append(PreferenceShare(stimulus=i, name=names[i] if i < len(names) else LETTERS[i], share=round(share, 4),
                                   ci_low=round(lo, 4), ci_high=round(hi, 4)))
    return out


def _crossing(prices: Sequence[int], f: Sequence[float], g: Sequence[float]) -> int | None:
    """Price where f - g changes sign (linear interpolation between grid points)."""
    for i in range(1, len(prices)):
        d0, d1 = f[i - 1] - g[i - 1], f[i] - g[i]
        if d0 == 0:
            return prices[i - 1]
        if d1 == 0:
            return prices[i]
        if d0 * d1 < 0:
            t = d0 / (d0 - d1)
            return round(prices[i - 1] + t * (prices[i] - prices[i - 1]))
    return None


def van_westendorp(answers: Sequence[SurveyAnswer], steps: int = 60) -> PriceRange | None:
    """Price sensitivity meter from the four price answers (inconsistent answer sets are dropped)."""
    rows = [(a.too_cheap, a.cheap, a.expensive, a.too_expensive) for a in answers
            if a.too_cheap is not None and a.cheap is not None and a.expensive is not None and a.too_expensive is not None]
    clean = [(tc, c, e, te) for tc, c, e, te in rows if tc <= c <= e <= te and te > 0]
    if len(clean) < 5:
        return None
    lo = min(r[0] for r in clean)
    hi = max(r[3] for r in clean)
    if hi <= lo:
        return None
    n = len(clean)
    thresholds = [sorted(r[k] for r in clean) for k in range(4)]

    def counts(points: list[int]) -> tuple[list[int], list[int], list[int], list[int]]:
        return (
            [n - bisect_left(thresholds[0], p) for p in points],
            [n - bisect_left(thresholds[1], p) for p in points],
            [bisect_right(thresholds[2], p) for p in points],
            [bisect_right(thresholds[3], p) for p in points],
        )

    # Empirical curves change only at an observed threshold or its adjacent minor unit.
    # A uniform price grid can put every ordinary answer in one cell when an outlier is large.
    prices = sorted({value + delta for column in thresholds for value in column for delta in (-1, 0, 1)
                     if lo <= value + delta <= hi})
    # Equal respondent counts are exact intersections; subtracting rounded fractions
    # (for example 1 - 0.8 versus 0.2) can otherwise skip an entire flat interval.
    too_cheap, cheap, expensive, too_exp = counts(prices)
    not_cheap = [n - v for v in cheap]
    not_exp = [n - v for v in expensive]
    marginal_cheap = _crossing(prices, too_cheap, not_cheap)
    optimal = _crossing(prices, too_cheap, too_exp)
    indifferent = _crossing(prices, cheap, expensive)
    marginal_expensive = _crossing(prices, not_exp, too_exp)
    # Bound chart size independently of panel size, keeping the reported crossings and
    # their immediate neighbours. Sampling observed transitions preserves concentrated answers.
    steps = max(1, steps)
    chart_prices = {prices[round(k * (len(prices) - 1) / steps)] for k in range(steps + 1)}
    chart_prices.update(value + delta for value in (marginal_cheap, optimal, indifferent, marginal_expensive)
                        if value is not None for delta in (-1, 0, 1) if lo <= value + delta <= hi)
    chart = sorted(chart_prices)
    chart_counts = counts(chart)
    return PriceRange(
        n=n,
        point_of_marginal_cheapness=marginal_cheap,
        optimal_price_point=optimal,
        indifference_price_point=indifferent,
        point_of_marginal_expensiveness=marginal_expensive,
        curve=[(p, round(a / n, 4), round(b / n, 4), round(c / n, 4), round(d / n, 4))
               for p, a, b, c, d in zip(chart, *chart_counts, strict=True)],
    )
