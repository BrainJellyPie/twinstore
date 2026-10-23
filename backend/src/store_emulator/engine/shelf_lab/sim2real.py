"""Sim2real: do vision shoppers decide the same on a photographed shelf as on its rendered twin?

The capture's planogram becomes a rack ("twin") that the simulator's own renderer draws. The same
personas, cues and per-call seeds then glance at three views of one shelf:

- `render`     the twin as the simulator renders it (packages with printed names, "#N price" tags);
- `photo`      the real photo with the same "#N price" tags laid on each product, so numbering and
               price text match the render and only the scene's appearance differs;
- `photo_raw`  the untouched photo: the shopper must name the product (set-of-mark ablation).

Answers are compared per persona at the product (SKU) level: how often the pick is the same, how
interest correlates, and where on the shelf the picks fall in each domain.
"""

import asyncio
import io
import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image, ImageDraw
from pydantic import BaseModel

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import RACK_LEVELS, Rack, RackType
from store_emulator.domain.shelf_lab import (
    Agreement,
    ConditionStats,
    GlanceAnswer,
    Sim2RealCondition,
)
from store_emulator.domain.types import Face, stable_seed
from store_emulator.engine.analysis.fidelity import spearman
from store_emulator.engine.capture.planogram import (
    SLOT_CAPACITY,
    PlacementReport,
    display_name,
    face_slots_from_capture,
    level_rows,
)
from store_emulator.engine.layout_gen.catalog import CATEGORY_LABELS
from store_emulator.engine.perception import MarkedItem, ShelfView, render_face
from store_emulator.engine.perception.shelf_render import load_font
from store_emulator.engine.prompting import display_price
from store_emulator.engine.simulation.engines.vlm_glance.prompt import (
    ShelfGlance,
    glance_system_prompt,
    resolve,
    user_prompt,
)

type ProgressCallback = Callable[[int, int], None]


class VisionLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...


@dataclass(frozen=True)
class TwinViews:
    rack: Rack
    face: Face
    views: dict[Sim2RealCondition, ShelfView]
    products: dict[str, str]          # sku → name of the products every view shows
    dropped_products: int = 0


def twin_rack(result: CaptureResult) -> tuple[Rack, Face]:
    """A free-standing rack holding the captured planogram on its S face, wide enough for the widest shelf."""
    widest = max((sum(i.facings for i in items) for items in level_rows(result).values()), default=1)
    k = max(1, min(8, math.ceil(widest / SLOT_CAPACITY)))
    rack = Rack(
        id="twin", type=RackType.FRIDGE if result.rack_type == "fridge" else RackType.SHELF,
        shape=[[1] * k], position=(0, 0), rack_desc=result.dominant_category,
        rack_name=CATEGORY_LABELS.get(result.dominant_category, ("Shelf", ""))[0],
    )
    rack.slots = face_slots_from_capture(result, list(range(k)), Face.S, PlacementReport(face=Face.S))
    return rack, Face.S


def _shelf_crop(photo: Image.Image, result: CaptureResult) -> tuple[Image.Image, tuple[float, float]]:
    """The shelf part of the photo (all products and shelf zones, small margin) and its offset."""
    xs: list[float] = []
    ys: list[float] = []
    for item in result.items:
        for b in item.boxes:
            xs += [b.x1, b.x2]
            ys += [b.y1, b.y2]
    for band in result.bands:
        for x, y in band.polygon:
            xs.append(x)
            ys.append(y)
    if not xs:
        return photo.convert("RGB"), (0.0, 0.0)
    w, h = photo.size
    mx, my = 0.03 * w, 0.03 * h
    x1, y1 = max(0.0, min(xs) - mx), max(0.0, min(ys) - my)
    x2, y2 = min(float(w), max(xs) + mx), min(float(h), max(ys) + my * 2.5)  # room for the tags below
    crop = photo.convert("RGB").crop((int(x1), int(y1), int(x2), int(y2)))
    return crop, (x1, y1)


def _encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _matched_offers(result: CaptureResult, render: ShelfView) -> list[tuple[CaptureItem, MarkedItem | None]]:
    # One SKU can appear at several prices or shelf levels. A photo tag must
    # identify the matching rendered offer instead of reusing that SKU's first tag.
    first_mark: dict[tuple[str, str, int, int], MarkedItem] = {}
    for marked in render.items:
        first_mark.setdefault((marked.item.sku, marked.item.name, marked.item.price, marked.slot.level), marked)
    return [(item, first_mark.get((item.sku, display_name(item), max(0, item.price or 0),
                                  min(RACK_LEVELS, max(1, item.level))))) for item in result.items]


def photo_view(
    photo: Image.Image, result: CaptureResult, render: ShelfView, *, tags: bool, width: int = 768,
) -> ShelfView:
    """The photo as a ShelfView of the twin rack: each product the twin holds carries the render's mark
    (and price) on a yellow tag at its first facing when `tags`; otherwise the photo is left as is."""
    crop, (ox, oy) = _shelf_crop(photo, result)
    scale = width / crop.width
    img = crop.resize((width, max(1, round(crop.height * scale))), Image.Resampling.LANCZOS)
    matched = _matched_offers(result, render)
    if tags:
        d = ImageDraw.Draw(img)
        font = load_font(max(11, width // 44), bold=True)
        for item, marked in matched:
            if marked is None or not item.boxes:
                continue
            b = item.boxes[0]
            text = f"#{marked.mark} {display_price(marked.item.price, result.currency)}"
            left, top, right, bottom = d.textbbox((0, 0), text, font=font)
            th, tw = bottom - top, right - left
            cx = ((b.x1 + b.x2) / 2 - ox) * scale
            y = min(img.height - th - 6, (b.y2 - oy) * scale - th * 0.4)
            x1 = max(1.0, min(img.width - tw - 8, cx - tw / 2 - 4))
            d.rounded_rectangle((x1 + 1, y + 2, x1 + tw + 9, y + th + 7), radius=3, fill=(0, 0, 0))
            d.rounded_rectangle((x1, y, x1 + tw + 8, y + th + 5), radius=3, fill=(255, 220, 40), outline=(120, 95, 0))
            d.text((x1 + 4 - left, y + 2 - top), text, font=font, fill=(15, 15, 15))
    items = tuple({marked.mark: marked for _, marked in matched if marked is not None}.values())
    return ShelfView(rack=render.rack, face=render.face, items=items, png=_encode(img), size=img.size)


def build_views(photo: Image.Image, result: CaptureResult, *, width: int = 768, seed: int = 0) -> TwinViews:
    rack, face = twin_rack(result)
    render = render_face(rack, face, currency=result.currency, width=width, rng=random.Random(stable_seed("sim2real-marks", seed)))
    views: dict[Sim2RealCondition, ShelfView] = {
        "render": render,
        "photo": photo_view(photo, result, render, tags=True, width=width),
        "photo_raw": photo_view(photo, result, render, tags=False, width=width),
    }
    products = {m.item.sku: m.item.name for m in views["photo"].items}
    dropped = sum(marked is None for _, marked in _matched_offers(result, render))
    return TwinViews(rack=rack, face=face, views=views, products=products, dropped_products=dropped)


def raw_system_prompt(store_type: str) -> str:
    """The glance prompt for an untagged photo: products are named, not numbered."""
    text = glance_system_prompt(store_type)
    text = text.replace(' and a yellow price tag "#N price" below it', ", with the store's own price tags on the shelf edge")
    return text.replace("- number: its N from the price tag, or 0", "- number: 0")


async def glance_panel(
    llm: VisionLLM,
    views: TwinViews,
    personas: list[Persona],
    *,
    conditions: list[Sim2RealCondition],
    cue_sampler: Callable[[random.Random], BehaviorCue],
    patterns: list[BehaviorPattern],
    store_type: str = "convenience",
    currency: str = "USD",
    situation: str = "",
    seed: int = 0,
    max_concurrent: int = 4,
    on_progress: ProgressCallback | None = None,
) -> list[GlanceAnswer]:
    """Every persona glances at every condition with the same prompt text and seed."""
    sem = asyncio.Semaphore(max_concurrent)
    total = len(personas) * len(conditions)
    done = 0

    async def one(persona: Persona, condition: Sim2RealCondition) -> GlanceAnswer:
        nonlocal done
        rng = random.Random(stable_seed("sim2real", seed, persona.id))
        cue = cue_sampler(rng)
        pattern = patterns[rng.randrange(len(patterns))]
        view = views.views[condition]
        prompt = user_prompt(persona, cue, pattern, view, basket=[], money_left=persona.budget_max or None,
                             currency=currency, situation=situation)
        system = raw_system_prompt(store_type) if condition == "photo_raw" else glance_system_prompt(store_type)
        answer = GlanceAnswer(persona_id=persona.id, condition=condition)
        async with sem:
            try:
                glance = await llm.generate_structured_with_image_async(
                    ShelfGlance, system, prompt, view.data_url(), seed=stable_seed(seed, "sim2real", persona.id),
                    route=persona.id, max_retries=1,
                )
            except Exception as e:  # noqa: BLE001 — one failed call must not end the panel
                answer.resolved_by, answer.error = "error", f"{type(e).__name__}: {e}"[:200]
                glance = None
        if glance is not None:
            raw_number_only = condition == "photo_raw" and glance.number != 0 and not glance.product.strip()
            if condition == "photo_raw":
                glance = glance.model_copy(update={"number": 0})
            marked, how = resolve(view, glance)
            if raw_number_only:
                how = "invalid"
            answer.resolved_by, answer.interest, answer.reason = how, glance.interest, glance.reason
            if how == "invalid":
                answer.error = "The model's choice could not be matched to a product in this shelf view."
            elif marked is not None:
                answer.sku, answer.name, answer.level = marked.item.sku, marked.item.name, marked.slot.level
        done += 1
        if on_progress is not None:
            on_progress(done, total)
        return answer

    return list(await asyncio.gather(*(one(p, c) for p in personas for c in conditions)))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def summarize(answers: list[GlanceAnswer], conditions: list[Sim2RealCondition]) -> tuple[list[ConditionStats], list[Agreement]]:
    by: dict[Sim2RealCondition, dict[str, GlanceAnswer]] = {c: {} for c in conditions}
    for a in answers:
        by[a.condition][a.persona_id] = a
    stats: list[ConditionStats] = []
    for c in conditions:
        ok = [a for a in by[c].values() if not a.error]
        picked = [a for a in ok if a.sku]
        levels: dict[int, int] = {}
        picks: dict[str, int] = {}
        for a in picked:
            levels[a.level] = levels.get(a.level, 0) + 1
            picks[a.sku] = picks.get(a.sku, 0) + 1
        stats.append(ConditionStats(
            condition=c, answers=len(ok), errors=len(by[c]) - len(ok),
            none_rate=round(1 - len(picked) / len(ok), 4) if ok else 0.0,
            mean_interest=round(sum(a.interest for a in ok) / len(ok), 3) if ok else 0.0,
            level_share={lv: round(n / len(picked), 4) for lv, n in sorted(levels.items(), reverse=True)} if picked else {},
            picks=dict(sorted(picks.items(), key=lambda kv: -kv[1])),
        ))
    agreement: list[Agreement] = []
    if "render" in by:
        for c in conditions:
            if c == "render":
                continue
            pairs = [(by["render"][pid], a) for pid, a in by[c].items()
                     if pid in by["render"] and not a.error and not by["render"][pid].error]
            if not pairs:
                continue
            same = sum(1 for r, a in pairs if r.sku == a.sku)
            p, lo, hi = wilson(same, len(pairs))
            rho: float | None = None
            if len(pairs) >= 3:
                x = np.array([r.interest for r, _ in pairs], dtype=np.float64)
                y = np.array([a.interest for _, a in pairs], dtype=np.float64)
                value = spearman(x, y)
                rho = None if math.isnan(value) else round(value, 4)
            agreement.append(Agreement(condition=c, pairs=len(pairs), same_pick=round(p, 4), ci_low=round(lo, 4),
                                       ci_high=round(hi, 4), interest_spearman=rho))
    return stats, agreement
