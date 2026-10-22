"""Merchandising levers on real photos: does a vision shopper's pick move when one thing on the shelf changes?

For every counterfactual of a benchmark (see `bench`), the same persona panel — same cues, same
per-call seeds — glances at the original photo and at the counterfactual, both with the
"#N price" tags of the simulator's render laid on the products. The outcome per counterfactual is
the share of the panel picking the edited product before and after (for a swap: the product that
moved), plus how many shoppers changed their pick at all. Aggregated per edit kind with a
persona-level paired bootstrap interval.
"""

import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from pydantic import BaseModel

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.shelf_lab import GlanceAnswer, PhotoEdit

from .sim2real import VisionLLM, build_views, glance_panel


class LeverOutcome(BaseModel):
    id: str
    kind: str
    target_sku_before: str
    target_sku_after: str
    personas: int
    picked_before: float            # share of the panel picking the target on the original
    picked_after: float             # … on the counterfactual
    changed_pick: float             # share of the panel whose pick differs
    errors: int
    answers_before: list[GlanceAnswer]
    answers_after: list[GlanceAnswer]


class LeverSummary(BaseModel):
    kind: str
    counterfactuals: int
    delta_picked: float             # mean (after − before) share picking the target
    ci_low: float
    ci_high: float
    changed_pick: float


@dataclass(frozen=True)
class Counterfactual:
    id: str
    kind: str
    edit: PhotoEdit
    original: Image.Image
    before: CaptureResult
    edited: Image.Image
    after: CaptureResult


def load_counterfactuals(bench_dir: Path, *, limit: int | None = None, kinds: set[str] | None = None) -> list[Counterfactual]:
    out: list[Counterfactual] = []
    for line in (bench_dir / "index.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if kinds and rec["kind"] not in kinds:
            continue
        files = rec["files"]
        detail = json.loads((bench_dir / files["counterfactual"]).with_suffix(".json").read_text(encoding="utf-8"))
        out.append(Counterfactual(
            id=rec["id"], kind=rec["kind"], edit=PhotoEdit.model_validate(rec["edit"]),
            original=Image.open(bench_dir / files["original"]).convert("RGB"),
            before=CaptureResult.model_validate_json((bench_dir / files["planogram"]).read_text(encoding="utf-8")),
            edited=Image.open(bench_dir / files["counterfactual"]).convert("RGB"),
            after=CaptureResult.model_validate(detail["result"]),
        ))
        if limit and len(out) >= limit:
            break
    return out


def _target_skus(cf: Counterfactual) -> tuple[str, str]:
    before = next((i.sku for i in cf.before.items if i.id == cf.edit.item_id), "")
    after = next((i.sku for i in cf.after.items if i.id == cf.edit.item_id), "")
    if cf.kind == "swap":
        return before, before  # the product that moved: same SKU, new place
    if cf.kind == "duplicate":
        return before, before  # the extended product: more facings after
    return before, after       # replace: the new product; price / promo: same; remove: gone ("")


async def run_lever(
    llm: VisionLLM, cf: Counterfactual, personas: list[Persona], *,
    cue_sampler: Callable[[random.Random], BehaviorCue], patterns: list[BehaviorPattern],
    store_type: str = "convenience", seed: int = 0,
) -> LeverOutcome:
    views_before = build_views(cf.original, cf.before, seed=seed)
    views_after = build_views(cf.edited, cf.after, seed=seed)
    before = await glance_panel(llm, views_before, personas, conditions=["photo"], cue_sampler=cue_sampler, patterns=patterns,
                                store_type=store_type, currency=cf.before.currency, seed=seed)
    after = await glance_panel(llm, views_after, personas, conditions=["photo"], cue_sampler=cue_sampler, patterns=patterns,
                               store_type=store_type, currency=cf.before.currency, seed=seed)
    t_before, t_after = _target_skus(cf)
    by_b = {a.persona_id: a for a in before}
    by_a = {a.persona_id: a for a in after}
    pairs = [(by_b[p.id], by_a[p.id]) for p in personas if not by_b[p.id].error and not by_a[p.id].error]
    n = max(1, len(pairs))
    return LeverOutcome(
        id=cf.id, kind=cf.kind, target_sku_before=t_before, target_sku_after=t_after, personas=len(pairs),
        picked_before=round(sum(1 for b, _ in pairs if b.sku and b.sku == t_before) / n, 4),
        picked_after=round(sum(1 for _, a in pairs if a.sku and a.sku == t_after) / n, 4),
        changed_pick=round(sum(1 for b, a in pairs if b.sku != a.sku) / n, 4),
        errors=len(personas) - len(pairs), answers_before=before, answers_after=after,
    )


def summarize_levers(outcomes: list[LeverOutcome], *, n_boot: int = 2000, seed: int = 0) -> list[LeverSummary]:
    rng = random.Random(seed)
    out: list[LeverSummary] = []
    for kind in sorted({o.kind for o in outcomes}):
        group = [o for o in outcomes if o.kind == kind]
        deltas = [o.picked_after - o.picked_before for o in group]
        mean = sum(deltas) / len(deltas)
        boots = sorted(sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(n_boot))
        out.append(LeverSummary(
            kind=kind, counterfactuals=len(group), delta_picked=round(mean, 4),
            ci_low=round(boots[int(0.025 * n_boot)], 4), ci_high=round(boots[int(0.975 * n_boot) - 1], 4),
            changed_pick=round(sum(o.changed_pick for o in group) / len(group), 4),
        ))
    return out
