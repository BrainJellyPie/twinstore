"""Virtual shelf test: respondents stand in front of one shelf face, pick the product they would take and
say what caught their eye first — once on the control shelf and once on the changed shelf (new pack,
price, sign or placement). The same people see both, so the target's pick share and stand-out are
compared pair by pair (paired bootstrap over respondents).
"""

import asyncio
import random
from store_emulator.engine.perception.product_images import ProductImageLoader
from collections.abc import Callable, Sequence
from typing import Literal, Protocol

import numpy as np
from pydantic import BaseModel, Field

from store_emulator.domain.marketing import ShareComparison, ShelfChoice, SkuShare
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack
from store_emulator.domain.types import Face, stable_seed
from store_emulator.engine.marketing.survey import persona_text
from store_emulator.engine.perception.shelf_render import ShelfView, render_face


class VisionLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...


SHELF_TEST_PROMPT = """You are a shopper standing in front of one store shelf, as the person described below. Look at
the shelf the way you would in a real store: you notice some products before others, and you take what suits you, or
nothing. Each product has a number badge. Answer in character, with numbers from the badges. Write any text in English."""


class ShelfAnswer(BaseModel):
    noticed: list[int] = Field(default_factory=list[int], max_length=3, description="badge numbers of the products that caught your eye first, in order")
    pick: int = Field(ge=0, description="badge number of the one product you would take, 0 = none")
    why: str = Field(default="", max_length=240)


def render_arm(rack: Rack, face: Face, currency: str, seed: int, image_loader: ProductImageLoader | None = None) -> ShelfView:
    """The face with badge numbers shuffled per respondent, so no position wins by its number."""
    return render_face(rack, face, currency=currency, width=900, rng=random.Random(seed), image_loader=image_loader)


async def shelf_panel(
    llm: VisionLLM,
    personas: Sequence[Persona],
    control: Rack,
    test: Rack,
    face: Face,
    *,
    currency: str = "USD",
    seed: int = 0,
    max_concurrent: int = 6,
    image_loader: ProductImageLoader | None = None,
) -> list[ShelfChoice]:
    sem = asyncio.Semaphore(max_concurrent)

    async def ask(p: Persona, arm: Literal["control", "test"], rack: Rack) -> ShelfChoice:
        base = ShelfChoice(respondent=p.id, age_group=str(p.age_group), gender=str(p.gender), arm=arm)
        view = render_arm(rack, face, currency, stable_seed("shelf-marks", seed, p.id), image_loader)
        user = (f"{persona_text(p, currency)}\n\nYou are at the {rack.rack_name or 'shelf'}. Which products catch your eye first "
                "(up to three badge numbers, in order), and which one product would you take (its number, or 0 for none)? Why, in one sentence?")
        async with sem:
            try:
                a = await llm.generate_structured_with_image_async(
                    ShelfAnswer, SHELF_TEST_PROMPT, user, view.data_url(), max_retries=1, seed=stable_seed("shelf", seed, p.id, arm),
                )
            except Exception as e:  # one respondent failing must not sink the panel
                return base.model_copy(update={"error": f"{type(e).__name__}: {str(e)[:160]}"})
        picked = view.by_mark(a.pick) if a.pick else None
        noticed = [m.item.sku for n in a.noticed if (m := view.by_mark(n)) is not None]
        return base.model_copy(update={
            "pick_sku": picked.item.sku if picked else "", "pick_name": picked.item.name if picked else "",
            "noticed": list(dict.fromkeys(noticed))[:3], "why": a.why.strip(),
        })

    arms: list[tuple[Literal["control", "test"], Rack]] = [("control", control), ("test", test)]
    jobs = [ask(p, arm, rack) for p in personas for arm, rack in arms]
    return list(await asyncio.gather(*jobs))


def _paired(a: np.ndarray, b: np.ndarray, n_bootstrap: int, rng: np.random.Generator) -> tuple[float, float, float]:
    d = b - a
    idx = rng.integers(0, len(d), size=(n_bootstrap, len(d)))
    boot = d[idx].mean(axis=1)
    return float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)), float((boot > 0).mean())


def compare_shelves(choices: Sequence[ShelfChoice], target: str, *, n_bootstrap: int = 2000, seed: int = 0) -> list[ShareComparison]:
    """Target pick share, noticed (top three) and noticed first, control vs test, over respondents who answered both."""
    by: dict[str, dict[str, ShelfChoice]] = {}
    for c in choices:
        if not c.error:
            by.setdefault(c.respondent, {})[c.arm] = c
    pairs = [(v["control"], v["test"]) for v in by.values() if "control" in v and "test" in v]
    if not pairs:
        return []
    rng = np.random.default_rng(abs(seed))
    out: list[ShareComparison] = []
    tests: dict[Literal["pick", "noticed", "noticed_first"], Callable[[ShelfChoice], bool]] = {
        "pick": lambda c: c.pick_sku == target,
        "noticed": lambda c: target in c.noticed,
        "noticed_first": lambda c: bool(c.noticed) and c.noticed[0] == target,
    }
    for metric, hit in tests.items():
        a = np.array([1.0 if hit(c) else 0.0 for c, _ in pairs])
        b = np.array([1.0 if hit(t) else 0.0 for _, t in pairs])
        lo, hi, p = _paired(a, b, n_bootstrap, rng)
        out.append(ShareComparison(metric=metric, control=round(float(a.mean()), 4), test=round(float(b.mean()), 4),
                                   diff=round(float(b.mean() - a.mean()), 4), ci_low=round(lo, 4), ci_high=round(hi, 4), prob_better=round(p, 4)))
    return out


def pick_shares(choices: Sequence[ShelfChoice], names: dict[str, str], top: int = 8) -> list[SkuShare]:
    counts: dict[str, dict[str, int]] = {"control": {}, "test": {}}
    totals = {"control": 0, "test": 0}
    for c in choices:
        if c.error:
            continue
        totals[c.arm] += 1
        key = c.pick_sku or ""
        counts[c.arm][key] = counts[c.arm].get(key, 0) + 1
    skus = sorted({*counts["control"], *counts["test"]}, key=lambda k: -(counts["control"].get(k, 0) + counts["test"].get(k, 0)))[:top]
    return [SkuShare(sku=k, name=names.get(k, "Nothing") if k else "Nothing",
                     control=round(counts["control"].get(k, 0) / max(1, totals["control"]), 4),
                     test=round(counts["test"].get(k, 0) / max(1, totals["test"]), 4)) for k in skus]
