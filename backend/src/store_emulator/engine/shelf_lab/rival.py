"""A rival's shelf against ours: prices and assortment from a capture of the rival's shelf.

Products are matched by name to the products our layout sells. The price index is the geometric mean
of rival / our price over matched products (1.0 = same prices, 0.9 = the rival is 10 % cheaper);
assortment overlap is the Jaccard index of the two product sets in the shelf's categories. A
price-adjusted pull for the rival venue scales its Huff attractiveness by (1 / index)^elasticity.
"""

import difflib
import math
from collections.abc import Mapping

from pydantic import BaseModel

from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.store import Store
from store_emulator.engine.capture.catalog_match import normalize_text
from store_emulator.engine.capture.planogram import display_name


class PriceComparison(BaseModel):
    name: str
    rival_price: int
    our_price: int
    ratio: float


class RivalComparison(BaseModel):
    matched: int
    rival_products: int
    our_products_in_categories: int
    price_index: float | None          # geometric mean rival / ours (None: nothing matched with prices)
    overlap: float                     # Jaccard of the product sets (shelf's categories)
    only_rival: list[str]
    only_ours: list[str]
    prices: list[PriceComparison]
    suggested_pull_factor: float | None


def unmatched_names(store: Store, rival: CaptureResult, *, cutoff: float = 0.86) -> tuple[list[str], list[str]]:
    """Rival product names that neither an exact nor a close name match reaches, and our product names."""
    ours = {normalize_text(item.name): item.name for _, slot in store.all_slots for item in slot.items}
    keys = list(ours)
    missing: list[str] = []
    for item in rival.items:
        if not item.labeled:
            continue
        name = display_name(item)
        key = normalize_text(name)
        if key not in ours and not difflib.get_close_matches(key, keys, n=1, cutoff=cutoff):
            missing.append(name)
    return list(dict.fromkeys(missing)), list(dict.fromkeys(ours.values()))


def compare_rival(
    store: Store, rival: CaptureResult, *, elasticity: float = 1.0, cutoff: float = 0.86,
    aliases: Mapping[str, str] | None = None,
) -> RivalComparison:
    """`aliases`: rival product name → our product name for matches the names alone miss (e.g. read by a model)."""
    ours: dict[str, tuple[str, int, str]] = {}          # normalized name → (name, price, category)
    for rack, slot in store.all_slots:
        for item in slot.items:
            ours.setdefault(normalize_text(item.name), (item.name, item.price, rack.rack_desc))
    categories = {i.category for i in rival.items if i.category}
    ours_here = {k: v for k, v in ours.items() if not categories or v[2] in categories}
    keys = list(ours)
    prices: list[PriceComparison] = []
    canonical: dict[str, str] = {}                      # rival product name → our key, or its own normalized name
    for item in rival.items:
        if not item.labeled:
            continue
        name = display_name(item)
        key = normalize_text(name)
        alias = normalize_text((aliases or {}).get(name, ""))
        hit = key if key in ours else alias if alias in ours else next(iter(difflib.get_close_matches(key, keys, n=1, cutoff=cutoff)), None)
        canonical[name] = hit or f"rival:{key}"
        if hit is None:
            continue
        our_name, our_price, _ = ours[hit]
        if item.price is not None and not item.price_estimated and item.price > 0 and our_price > 0:
            prices.append(PriceComparison(name=our_name, rival_price=item.price, our_price=our_price, ratio=round(item.price / our_price, 4)))
    index = math.exp(sum(math.log(p.ratio) for p in prices) / len(prices)) if prices else None
    theirs = set(canonical.values())
    mine = set(ours_here) | {k for k in theirs if k in ours}
    matched = len(theirs & set(ours))
    overlap = len(theirs & mine) / len(theirs | mine) if theirs | mine else 0.0
    only_rival = [n for n, k in canonical.items() if k.startswith("rival:")]
    only_ours = [v[0] for k, v in ours_here.items() if k not in theirs]
    return RivalComparison(
        matched=matched, rival_products=len(canonical), our_products_in_categories=len(ours_here),
        price_index=round(index, 4) if index is not None else None, overlap=round(overlap, 4),
        only_rival=only_rival[:20], only_ours=only_ours[:20], prices=sorted(prices, key=lambda p: p.ratio),
        suggested_pull_factor=round(min(1.5, max(0.67, (1 / index) ** elasticity)), 3) if index else None,
    )
