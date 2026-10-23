"""Resolving a VLM entry plan ("2 × iced coffee from Drinks") to products on the shelves.

Resolution order, most specific first; name matches prefer the named category before falling
back to the full catalog:
1. exact   — the product name as printed (case-insensitive).
2. name    — fuzzy name match: most of the named words appear in the product name.
3. words   — a distinctive named word appears in product names ("coffee" → coffee drinks).
4. category — the named category matches rack signs/descriptions (synonyms expanded).
5. demand_category — the scenario layer's demand categories (cold drinks, hot food, …).
Several equally good candidates are drawn by the customer's seeded RNG (shelf level, price fit,
promotion), so the same customer always gets the same SKU.
"""

import random
from dataclasses import dataclass

from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.engine.perception import category_label
from store_emulator.engine.scenario import item_categories, words_categories

from ..rule_based import expand_category, tokenize
from .prompt import PlannedItem

type CatalogEntry = tuple[Rack, Slot, SlotItem, set[str], set[str]]

# Words that say nothing about which product is meant.
_FILLER = frozenset({
    "a", "an", "the", "and", "or", "of", "for", "with", "some", "any", "one", "two", "item", "thing", "something",
    "pack", "bottle", "can", "cup", "bag", "box", "small", "large", "big", "quick", "light", "fresh", "cold", "hot",
    "good", "nice", "new", "drink", "food", "snack",
})


@dataclass(frozen=True)
class PlanMatch:
    how: str  # exact | name | words | category | demand_category | unresolved
    candidates: tuple[CatalogEntry, ...]

    @property
    def key(self) -> str:
        """Identity of what was asked for, for ensemble votes: the candidate set (or "")."""
        return "|".join(sorted({entry[2].sku for entry in self.candidates}))


def _category_entries(catalog: list[CatalogEntry], category: str) -> list[CatalogEntry]:
    """Entries on racks whose sign (or description) matches the named category."""
    if not category.strip():
        return []
    said = category.strip().lower()
    by_label = [e for e in catalog if category_label(e[0]).lower() == said]
    if by_label:
        return by_label
    words = expand_category(category)
    return [e for e in catalog if words & e[3]]


def match_plan_item(item: PlannedItem, catalog: list[CatalogEntry]) -> PlanMatch:
    in_category = _category_entries(catalog, item.category)
    product = item.product.strip()
    if product:
        exact = [e for e in in_category if e[2].name.casefold() == product.casefold()]
        if not exact:
            exact = [e for e in catalog if e[2].name.casefold() == product.casefold()]
        if exact:
            return PlanMatch("exact", tuple(exact))
        said = tokenize(product) - _FILLER
        if said:
            for pool, min_jaccard in ((in_category, 0.0), (catalog, 0.3)):
                best: list[CatalogEntry] = []
                best_score = (0.0, 0.0)
                for entry in pool:
                    common = len(said & entry[4])
                    if not common:
                        continue
                    score = (common / len(said), common / len(said | entry[4]))
                    if score > best_score:
                        best, best_score = [entry], score
                    elif score == best_score:
                        best.append(entry)
                if best and best_score[0] >= 0.6 and best_score[1] >= min_jaccard:
                    return PlanMatch("name", tuple(best))
            distinctive = {w for w in said if len(w) >= 3}
            for pool in (in_category, catalog):
                hits = [e for e in pool if distinctive & e[4]]
                if hits:
                    return PlanMatch("words", tuple(hits))
    if in_category:
        return PlanMatch("category", tuple(in_category))
    if not item.category.strip() and product:
        by_words = _category_entries(catalog, product)
        if by_words:
            return PlanMatch("category", tuple(by_words))
    wanted = words_categories(f"{item.category} {product}")
    if wanted:
        hits = [e for e in catalog if wanted & item_categories(e[0], e[2])]
        if hits:
            return PlanMatch("demand_category", tuple(hits))
    return PlanMatch("unresolved", ())


def pick_candidate(
    match: PlanMatch,
    *,
    chosen: set[str],
    remaining: int | None,
    attention: dict[int, float],
    promo_multiplier: float,
    rng: random.Random,
) -> CatalogEntry | None:
    """Seeded draw among the candidates not yet in the basket: shelf level × price fit × promotion.
    No scenario demand multipliers: the model already read the situation."""
    pool = [e for e in match.candidates if e[2].sku not in chosen]
    if not pool:
        return None
    pool.sort(key=lambda e: (e[2].sku, e[0].id, e[1].face.value, e[1].level))
    candidates: list[CatalogEntry] = []
    weights: list[float] = []
    for entry in pool:
        weight = (attention.get(entry[1].level, 0.7)
                  * (1.0 if remaining is None or entry[2].price <= remaining else 0.15)
                  * (promo_multiplier if entry[2].promo else 1.0))
        if weight > 0:
            candidates.append(entry)
            weights.append(weight)
    return rng.choices(candidates, weights=weights, k=1)[0] if candidates else None


@dataclass(frozen=True)
class PlanRecord:
    persona_id: str
    pattern: str
    source: str  # vlm | vote | fallback
    enter: bool
    mission: str
    reason: str
    items: tuple[tuple[str, str, int], ...]  # (category, product, qty) as the model named them
    # (named, resolved SKU or "", how, store category) per named item; how adds "duplicate",
    # "unavailable", "over_budget", "unreachable" and "cap" to the PlanMatch kinds.
    resolved: tuple[tuple[str, str, str, str], ...] = ()
    model: str = ""
    agreement: float | None = None
    error: str = ""
