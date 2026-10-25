"""Choice-based conjoint answered by synthetic respondents.

Each respondent gets their own random choice tasks (levels balanced per respondent, as little overlap inside a task as
the levels allow) and answers all of them in one model call. A multinomial logit over every choice gives the
part-worth of each level; price enters as one linear slope, which turns utility differences into willingness to pay.
Intervals come from resampling respondents, so they respect that one person's choices go together.
"""

import asyncio
import random
from collections.abc import Sequence
from itertools import product
from typing import Any, Literal, Protocol

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field, ValidationInfo, create_model, field_validator

from store_emulator.domain.marketing import (
    AttributeImportance,
    ConjointAttribute,
    ConjointFit,
    ConjointRespondent,
    ConjointSegment,
    ConjointTask,
    PartWorth,
)
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import stable_seed
from store_emulator.engine.prompting import canonical_identifier, display_price

from .survey import LETTERS, StudyResponse, persona_text

type Floats = npt.NDArray[np.float64]

MIN_SEGMENT = 15
RIDGE = 0.1   # a weak normal prior on every coefficient keeps estimates finite when choices are fully predictable


class TextLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T: ...


# ── design ──────────────────────────────────────────────────────────────────────

def _draw(bag: list[int], levels: int, taken: list[int], rng: random.Random) -> int:
    for i, level in enumerate(bag):
        if level not in taken:
            return bag.pop(i)
    fresh = list(range(levels))
    rng.shuffle(fresh)
    pick = next((level for level in fresh if level not in taken), fresh[0])
    bag.extend(level for level in fresh if level != pick)
    return pick


def design(levels: Sequence[int], tasks: int, options: int, rng: random.Random) -> list[list[list[int]]]:
    """Choice tasks for one respondent: tasks × options × level index per attribute."""
    bags: list[list[int]] = [[] for _ in levels]
    out: list[list[list[int]]] = []
    for _ in range(tasks):
        columns: list[list[int]] = [[] for _ in levels]
        for a, n in enumerate(levels):
            for _ in range(options):
                columns[a].append(_draw(bags[a], n, columns[a], rng))
        profiles = [[columns[a][o] for a in range(len(levels))] for o in range(options)]
        for o in range(1, options):   # only possible when every attribute has fewer levels than options
            for _ in range(20):
                if profiles[o] not in profiles[:o]:
                    break
                a = rng.randrange(len(levels))
                profiles[o][a] = rng.randrange(levels[a])
            if profiles[o] in profiles[:o]:
                # Legal designs have enough combinations; checking at most o + 1 finds an unused one.
                used = {tuple(p) for p in profiles[:o]}
                profiles[o] = next(list(p) for p in product(*(range(n) for n in levels)) if p not in used)
        out.append(profiles)
    return out


# ── asking ──────────────────────────────────────────────────────────────────────

CONJOINT_PROMPT = """You are shopping, as the person described below, and choose between versions of the same product. In each
choice task, {choice_instruction}
Different people care about different things: trade off what matters to you and ignore what
does not. Answer every task. Write any text in English.
Use an empty string, not null, when no explanation is given."""


def choice_model(tasks: int, options: int, none_option: bool) -> type[BaseModel]:
    choices = [*LETTERS[:options], *(["none"] if none_option else [])]
    allowed = tuple(choices)

    class ConjointChoices(StudyResponse):
        @field_validator("*", mode="before")
        @classmethod
        def canonical_choice(cls, value: object, info: ValidationInfo) -> object:
            if isinstance(value, str) and info.field_name and info.field_name.startswith("task_"):
                return canonical_identifier(value, choices)
            return value

    fields: dict[str, Any] = {f"task_{t + 1}": (Literal[allowed], ...) for t in range(tasks)}
    fields["why"] = (str, Field(default="", max_length=240, description="in one sentence, what mattered most in your choices"))
    return create_model("ConjointChoices", __base__=ConjointChoices, **fields)


def profile_text(attributes: Sequence[ConjointAttribute], prices: Sequence[int], currency: str, profile: Sequence[int]) -> str:
    parts = [f"{a.name}: {a.levels[profile[i]]}" for i, a in enumerate(attributes)]
    if prices:
        parts.append(f"Price: {display_price(prices[profile[len(attributes)]], currency)}")
    return " · ".join(parts)


def tasks_text(attributes: Sequence[ConjointAttribute], prices: Sequence[int], currency: str,
               tasks: Sequence[Sequence[Sequence[int]]], none_option: bool) -> str:
    blocks: list[str] = []
    for t, profiles in enumerate(tasks):
        lines = [f"Task {t + 1}:"]
        lines += [f"  {LETTERS[o]}: {profile_text(attributes, prices, currency, p)}" for o, p in enumerate(profiles)]
        if none_option:
            lines.append("  none: buy none of these")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


async def conjoint_panel(
    llm: TextLLM,
    personas: Sequence[Persona],
    attributes: Sequence[ConjointAttribute],
    prices: Sequence[int],
    *,
    product: str,
    context: str = "",
    currency: str = "USD",
    tasks: int = 8,
    options: int = 3,
    none_option: bool = True,
    seed: int = 0,
    max_concurrent: int = 6,
) -> list[ConjointRespondent]:
    """One respondent per persona, each with their own design (failed calls come back with `error` set)."""
    levels = [len(a.levels) for a in attributes] + ([len(prices)] if prices else [])
    model = choice_model(tasks, options, none_option)
    choice_instruction = (
        'pick the one option you would really buy on this trip, given your budget, habits and taste, or "none" if you '
        "would rather buy none of them."
        if none_option else
        "choose your most preferred displayed product, given your budget, habits and taste. "
        "This is a forced-choice task: you must return one displayed product letter."
    )
    system = CONJOINT_PROMPT.format(choice_instruction=choice_instruction)
    sem = asyncio.Semaphore(max_concurrent)

    async def ask(p: Persona) -> ConjointRespondent:
        rng = random.Random(stable_seed("conjoint-design", seed, p.id))
        plan = design(levels, tasks, options, rng)
        base = ConjointRespondent(respondent=p.id, age_group=str(p.age_group), gender=str(p.gender),
                                  tasks=[ConjointTask(profiles=profiles) for profiles in plan])
        about = f"\nAbout the product: {context}" if context else ""
        user = (f"{persona_text(p, currency)}\n\nYou are choosing {product}.{about}\n\n"
                f"{tasks_text(attributes, prices, currency, plan, none_option)}")
        try:
            async with sem:
                r = await llm.generate_structured_async(model, system, user, max_retries=1,
                                                        seed=stable_seed("conjoint", seed, p.id))
            data = r.model_dump()
            answered = [ConjointTask(profiles=profiles, choice=None if data[f"task_{t + 1}"] == "none" else LETTERS.index(data[f"task_{t + 1}"]))
                        for t, profiles in enumerate(plan)]
            return base.model_copy(update={"tasks": answered, "why": str(data.get("why", "")).strip()})
        except Exception as e:  # noqa: BLE001 — one respondent failing must not sink the panel
            return base.model_copy(update={"error": f"{type(e).__name__}: {str(e)[:160]}"})

    return list(await asyncio.gather(*(ask(p) for p in personas)))


# ── estimation ──────────────────────────────────────────────────────────────────

class Coding:
    """Columns of the logit: level dummies (first level of each attribute is the base), one price column (centred and
    scaled), and a constant for "none"."""

    def __init__(self, levels: Sequence[int], prices: Sequence[int], none_option: bool):
        self.levels = list(levels)
        self.prices = [float(p) for p in prices]
        self.none_option = none_option
        self.offsets: list[int] = []
        k = 0
        for n in self.levels:
            self.offsets.append(k)
            k += n - 1
        self.price_col = k if self.prices else -1
        k += 1 if self.prices else 0
        self.none_col = k if none_option else -1
        self.width = k + (1 if none_option else 0)
        self.price_mean = sum(self.prices) / len(self.prices) if self.prices else 0.0
        self.price_scale = (max(self.prices) - min(self.prices)) if self.prices else 1.0

    def matrix(self, people: Sequence[ConjointRespondent]) -> tuple[Floats, npt.NDArray[np.int64], npt.NDArray[np.int64]]:
        """X (choices × alternatives × columns), the chosen alternative, and the respondent of each choice."""
        rows: list[Floats] = []
        chosen: list[int] = []
        owner: list[int] = []
        alternatives = 0
        for r, person in enumerate(people):
            for task in person.tasks:
                alternatives = len(task.profiles) + (1 if self.none_option else 0)
                x = np.zeros((alternatives, self.width))
                for o, profile in enumerate(task.profiles):
                    for a in range(len(self.levels)):
                        if profile[a] > 0:
                            x[o, self.offsets[a] + profile[a] - 1] = 1.0
                    if self.prices:
                        x[o, self.price_col] = (self.prices[profile[len(self.levels)]] - self.price_mean) / self.price_scale
                if self.none_option:
                    x[-1, self.none_col] = 1.0
                if task.choice is None and not self.none_option:
                    continue
                rows.append(x)
                chosen.append(len(task.profiles) if task.choice is None else task.choice)
                owner.append(r)
        if not rows:
            return np.zeros((0, max(alternatives, 1), self.width)), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
        return np.stack(rows), np.array(chosen, dtype=np.int64), np.array(owner, dtype=np.int64)


def _probabilities(x: Floats, beta: Floats) -> Floats:
    u = x @ beta
    u -= u.max(axis=1, keepdims=True)
    e = np.exp(u)
    return e / e.sum(axis=1, keepdims=True)


def fit_logit(x: Floats, y: npt.NDArray[np.int64], *, ridge: float = RIDGE, start: Floats | None = None,
              weights: Floats | None = None) -> Floats:
    """Penalised maximum likelihood by damped Newton steps, including separated choices and bootstrap warm starts."""
    t, a, k = x.shape
    w = np.ones(t) if weights is None else weights
    onehot = np.zeros((t, a))
    onehot[np.arange(t), y] = 1.0
    beta: Floats = np.zeros(k) if start is None else start.copy()
    flat = x.reshape(t * a, k)

    def objective(coefficients: Floats) -> float:
        u = x @ coefficients
        return float(w @ (u[np.arange(t), y] - np.logaddexp.reduce(u, axis=1))
                     - 0.5 * ridge * (coefficients @ coefficients))

    value = objective(beta)
    for _ in range(100):
        p = _probabilities(x, beta)
        grad = flat.T @ ((onehot - p) * w[:, None]).reshape(-1) - ridge * beta
        mean_x = (p[:, :, None] * x).sum(axis=1)
        hess = (flat * (p * w[:, None]).reshape(-1, 1)).T @ flat - (mean_x * w[:, None]).T @ mean_x + ridge * np.eye(k)
        step = np.linalg.solve(hess, grad)
        scale = 1.0
        for _ in range(50):
            candidate = beta + scale * step
            updated = objective(candidate)
            if updated >= value + 1e-4 * scale * float(grad @ step):
                break
            scale *= 0.5
        else:
            break
        beta, value = candidate, updated
        if float(np.abs(scale * step).max()) < 1e-7:
            break
    return beta


def log_likelihood(x: Floats, y: npt.NDArray[np.int64], beta: Floats) -> float:
    p = _probabilities(x, beta)
    return float(np.log(np.maximum(p[np.arange(len(y)), y], 1e-300)).sum())


class Derived(BaseModel):
    utilities: list[list[float]]      # per attribute (price last), centred
    importances: list[float]
    wtp: list[list[float | None]]     # per non-price attribute and level, minor units over the first level
    price_slope: float | None
    none_utility: float | None


def derive(beta: Floats, coding: Coding) -> Derived:
    utilities: list[list[float]] = []
    offset = 0.0
    for a, n in enumerate(coding.levels):
        raw = [0.0, *(float(beta[coding.offsets[a] + i]) for i in range(n - 1))]
        mean = sum(raw) / n
        offset += mean
        utilities.append([u - mean for u in raw])
    slope: float | None = None
    if coding.prices:
        slope = float(beta[coding.price_col]) / coding.price_scale
        utilities.append([slope * (p - coding.price_mean) for p in coding.prices])
    ranges = [max(u) - min(u) for u in utilities]
    total = sum(ranges) or 1.0
    wtp: list[list[float | None]] = []
    for a in range(len(coding.levels)):
        u = utilities[a]
        wtp.append([(u[i] - u[0]) / -slope if slope is not None and slope < 0 else None for i in range(len(u))])
    none = float(beta[coding.none_col]) - offset if coding.none_option else None
    return Derived(utilities=utilities, importances=[r / total for r in ranges], wtp=wtp, price_slope=slope, none_utility=none)


def _interval(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    lo, hi = np.percentile(np.array(values), [2.5, 97.5])
    return float(lo), float(hi)


class Estimate(BaseModel):
    part_worths: list[PartWorth]
    importances: list[AttributeImportance]
    price_slope: float | None
    price_mean: float
    none_utility: float | None
    fit: ConjointFit
    segments: list[ConjointSegment] = []


def estimate(
    people: Sequence[ConjointRespondent],
    attributes: Sequence[ConjointAttribute],
    prices: Sequence[int],
    *,
    none_option: bool,
    currency: str = "USD",
    draws: int = 200,
    seed: int = 0,
) -> Estimate | None:
    """Pooled logit with respondent-bootstrap intervals; None when nobody answered."""
    ok = [p for p in people if not p.error and p.tasks]
    coding = Coding([len(a.levels) for a in attributes], prices, none_option)
    x, y, owner = coding.matrix(ok)
    if len(y) == 0:
        return None
    beta = fit_logit(x, y)
    point = derive(beta, coding)
    # Bootstrap over respondents: each draw weights a respondent's choices by how often they were resampled.
    rng = np.random.default_rng(abs(seed))
    n = len(ok)
    samples: list[Derived] = []
    for _ in range(draws):
        counts = np.bincount(rng.integers(0, n, n), minlength=n).astype(np.float64)
        samples.append(derive(fit_logit(x, y, start=beta, weights=counts[owner]), coding))
    names = [a.name for a in attributes] + (["Price"] if prices else [])
    level_names = [list(a.levels) for a in attributes] + ([[display_price(p, currency) for p in prices]] if prices else [])
    part_worths: list[PartWorth] = []
    for a, levels in enumerate(level_names):
        for i, level in enumerate(levels):
            lo, hi = _interval([s.utilities[a][i] for s in samples])
            pw = PartWorth(attribute=names[a], level=level, utility=round(point.utilities[a][i], 4), ci_low=round(lo, 4), ci_high=round(hi, 4))
            if a < len(attributes) and i > 0 and point.wtp[a][i] is not None:
                draws_wtp = [w for s in samples if (w := s.wtp[a][i]) is not None]
                wlo, whi = _interval(draws_wtp)
                # A slope that is not clearly negative in every draw makes the ratio unstable: no interval then.
                stable = len(draws_wtp) == len(samples)
                pw = pw.model_copy(update={"wtp": round(point.wtp[a][i] or 0.0, 2),
                                           "wtp_low": round(wlo, 2) if stable else None, "wtp_high": round(whi, 2) if stable else None})
            part_worths.append(pw)
    importances: list[AttributeImportance] = []
    for a, name in enumerate(names):
        lo, hi = _interval([s.importances[a] for s in samples])
        importances.append(AttributeImportance(attribute=name, importance=round(point.importances[a], 4), ci_low=round(lo, 4), ci_high=round(hi, 4)))
    ll = log_likelihood(x, y, beta)
    null = float(-np.log(x.shape[1]) * len(y))
    hits = float((_probabilities(x, beta).argmax(axis=1) == y).mean())
    fit = ConjointFit(choices=len(y), log_likelihood=round(ll, 2), null_log_likelihood=round(null, 2),
                      mcfadden_r2=round(1 - ll / null, 4) if null else 0.0, hit_rate=round(hits, 4), chance_rate=round(1 / x.shape[1], 4))
    return Estimate(part_worths=part_worths, importances=importances, price_slope=point.price_slope, price_mean=coding.price_mean,
                    none_utility=round(point.none_utility, 4) if point.none_utility is not None else None, fit=fit,
                    segments=segments(ok, coding, names))


def none_share(people: Sequence[ConjointRespondent]) -> float:
    choices = [t.choice for p in people if not p.error for t in p.tasks]
    return round(sum(1 for c in choices if c is None) / len(choices), 4) if choices else 0.0


def segments(people: Sequence[ConjointRespondent], coding: Coding, names: Sequence[str]) -> list[ConjointSegment]:
    """Attribute importance per age group and gender, for groups of at least MIN_SEGMENT respondents."""
    out: list[ConjointSegment] = []
    for field, label in (("age_group", "age"), ("gender", "gender")):
        for value in sorted({getattr(p, field) for p in people}):
            group = [p for p in people if getattr(p, field) == value]
            if len(group) < MIN_SEGMENT:
                continue
            x, y, _ = coding.matrix(group)
            if len(y) == 0:
                continue
            d = derive(fit_logit(x, y), coding)
            out.append(ConjointSegment(segment=f"{label} {value}", n=len(group), none_share=none_share(group),
                                       importances={n: round(i, 4) for n, i in zip(names, d.importances, strict=True)}))
    return out
