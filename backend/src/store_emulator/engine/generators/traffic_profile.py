"""When shoppers come: a weekday × hour traffic profile, fitted from timestamps or given by hand.

Asking a language model to pick the day and hour of each visit collapses onto a few modes (in the
real-data validation, three quarters of generated visits fell on a Saturday at 10:00 or 17:00).
A profile fitted from a store's own transaction times (or a format default) assigns visit times
with the right spread; the model then plans each visit *given* its time.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, Field

from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Weekday, stable_seed


class TrafficProfile(BaseModel):
    """Share of visits per (weekday 1–7, hour 0–23); rows need not be normalized."""
    weights: dict[int, dict[int, float]] = Field(default_factory=dict[int, dict[int, float]])
    source: str = ""

    def cells(self) -> list[tuple[int, int, float]]:
        return [(d, h, w) for d, hours in sorted(self.weights.items()) for h, w in sorted(hours.items()) if w > 0]

    def weekday_shares(self) -> dict[int, float]:
        tot = sum(w for _, _, w in self.cells()) or 1.0
        out: dict[int, float] = {}
        for d, _, w in self.cells():
            out[d] = out.get(d, 0.0) + w / tot
        return out

    def hour_shares(self) -> dict[int, float]:
        tot = sum(w for _, _, w in self.cells()) or 1.0
        out: dict[int, float] = {}
        for _, h, w in self.cells():
            out[h] = out.get(h, 0.0) + w / tot
        return out


def fit_traffic_profile(visits: Iterable[tuple[int, int]], *, smoothing: float = 0.5, source: str = "") -> TrafficProfile:
    """Profile from (weekday 1–7, hour 0–23) of observed visits, with additive smoothing over the
    hours that saw any visit on some day (a closed hour stays closed)."""
    counts: Counter[tuple[int, int]] = Counter(visits)
    if not counts:
        return TrafficProfile(source=source)
    open_hours = sorted({h for _, h in counts})
    weights = {d: {h: counts.get((d, h), 0) + smoothing for h in open_hours} for d in range(1, 8)}
    return TrafficProfile(weights=weights, source=source or f"{sum(counts.values())} visits")


def assign_visit_times(personas: Sequence[Persona], profile: TrafficProfile, *, seed: int = 0) -> list[Persona]:
    """Copies of `personas` with day and arrival_hour drawn from the profile (see draw_visit_times)."""
    slots = draw_visit_times(len(personas), profile, seed=seed)
    if not slots:
        return list(personas)
    return [p.model_copy(update={"day": Weekday(d), "arrival_hour": h}) for p, (d, h) in zip(personas, slots, strict=True)]


def draw_visit_times(n: int, profile: TrafficProfile, *, seed: int = 0) -> list[tuple[int, int]]:
    """n (weekday, hour) slots from the profile; empty when the profile is.

    Systematic sampling rather than i.i.d.: n evenly spaced points (one seeded offset) on the
    cumulative weights, with cells ordered hour-major, so every cell gets floor or ceil of its
    expected count and even a small panel reproduces the hour curve; the order is a seeded shuffle.
    """
    cells = sorted(profile.cells(), key=lambda c: (c[1], c[0]))
    if not cells or n <= 0:
        return []
    total = sum(w for _, _, w in cells)
    rng = random.Random(stable_seed("visit-times", seed, n))
    offset = rng.random()
    slots: list[tuple[int, int]] = []
    cum, i = 0.0, 0
    for k in range(n):
        target = (k + offset) / n * total
        while i < len(cells) - 1 and cum + cells[i][2] <= target:
            cum += cells[i][2]
            i += 1
        slots.append((cells[i][0], cells[i][1]))
    rng.shuffle(slots)
    return slots


def reshape_hourly_counts(counts: dict[int, int], profile: TrafficProfile, day: int, *,
                          scale_by_day: bool = True) -> dict[int, int]:
    """Redistribute a day's visitor counts over hours by the profile (largest remainder, same total).

    The language model's own hourly estimate keeps deciding *who* comes; *when* follows the store's
    data. With `scale_by_day`, the day's total is also scaled by the profile's weekday share (×7, so a
    profile covering the whole week keeps the weekly total). Hours outside `counts` (closed) stay out;
    a day the profile does not cover is returned unchanged.
    """
    hours = profile.weights.get(day, {})
    open_hours = [h for h in counts if hours.get(h, 0) > 0]
    if not open_hours:
        return dict(counts)
    total = sum(counts.values())
    if scale_by_day and len(profile.weights) == 7:
        total = round(total * 7 * profile.weekday_shares().get(day, 1 / 7))
    w = sum(hours[h] for h in open_hours)
    expected = {h: total * hours[h] / w for h in open_hours}
    out = {h: int(x) for h, x in expected.items()}
    for h in sorted(open_hours, key=lambda h: -(expected[h] - int(expected[h])))[: total - sum(out.values())]:
        out[h] += 1
    return {h: out.get(h, 0) for h in counts}


def fit_segment_profiles(visits: Iterable[tuple[str, int, int]], *, prior_visits: float = 50.0,
                         smoothing: float = 0.5) -> dict[str, TrafficProfile]:
    """One profile per segment (e.g. age band, from loyalty-card data), shrunk toward the pooled
    profile with the weight of `prior_visits` visits so a thin segment does not overfit. Key ""
    holds the pooled profile (the fallback for a segment without data)."""
    rows = list(visits)
    pooled = fit_traffic_profile(((d, h) for _, d, h in rows), smoothing=smoothing, source="pooled")
    total = sum(w for _, _, w in pooled.cells()) or 1.0
    by_seg: dict[str, Counter[tuple[int, int]]] = {}
    for seg, d, h in rows:
        by_seg.setdefault(seg, Counter())[(d, h)] += 1
    out = {"": pooled}
    for seg, counts in by_seg.items():
        weights = {d: {h: counts.get((d, h), 0) + prior_visits * w / total for h, w in hours.items()}
                   for d, hours in pooled.weights.items()}
        out[seg] = TrafficProfile(weights=weights, source=f"{seg}: {sum(counts.values())} visits")
    return out


def draw_segment_visit_times(segments: Sequence[str], profiles: dict[str, TrafficProfile], *,
                             seed: int = 0) -> list[tuple[int, int]]:
    """(weekday, hour) per entry of `segments`, each segment sampled from its own profile (or the
    pooled one under key "")."""
    out: list[tuple[int, int] | None] = [None] * len(segments)
    groups: dict[str, list[int]] = {}
    for i, seg in enumerate(segments):
        groups.setdefault(seg, []).append(i)
    for seg, idx in sorted(groups.items()):
        profile = profiles.get(seg) or profiles.get("") or TrafficProfile()
        for i, slot in zip(idx, draw_visit_times(len(idx), profile, seed=stable_seed(seed, seg)), strict=False):
            out[i] = slot
    return [s if s is not None else (int(Weekday.MON), 12) for s in out]
