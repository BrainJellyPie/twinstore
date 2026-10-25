"""A rival's shelf against ours: prices and assortment from a capture of the rival's shelf.

Products are matched by normalized name or an explicit alias to products our layout sells. Similar
names alone cannot establish the same brand, variant or pack size. The price index is the geometric mean
of rival / our price over matched products (1.0 = same prices, 0.9 = the rival is 10 % cheaper);
assortment overlap is the Jaccard index of the two product sets in the shelf's categories. A
price-adjusted pull for the rival venue scales its Huff attractiveness by (1 / index)^elasticity.
"""

import math
from collections.abc import Mapping

from pydantic import BaseModel

from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.store import Store
from store_emulator.engine.capture.catalog_match import match_category, normalize_text
from store_emulator.engine.capture.planogram import display_name
from store_emulator.engine.layout_gen.catalog import CATALOG


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


def _category_of(rack_desc: str, rack_name: str, product: str, rack_type: str) -> str:
    """Our product's catalog category, as the rival's products have one: a template rack's description is the
    category key; any other layout (the sample, model-made or hand-built) gets it from the rack's and the product's
    names. Only template racks had one, so every other layout counted no products in the rival's categories."""
    if rack_desc in CATALOG:
        return rack_desc
    return match_category(f"{rack_name} {rack_desc}".strip(), product, rack_type=rack_type)


def _product_key(name: str) -> str:
    return normalize_text(name) or f"symbol:{name.strip()}"


def unmatched_names(store: Store, rival: CaptureResult) -> tuple[list[str], list[str]]:
    """Names without an exact normalized match, for explicit product matching, and our product names."""
    ours = {_product_key(item.name): item.name for _, slot in store.all_slots for item in slot.items}
    missing: list[str] = []
    for item in rival.items:
        if not item.labeled:
            continue
        name = display_name(item)
        key = _product_key(name)
        if key not in ours:
            missing.append(name)
    return list(dict.fromkeys(missing)), list(dict.fromkeys(ours.values()))


def compare_rival(
    store: Store, rival: CaptureResult, *, elasticity: float = 1.0,
    aliases: Mapping[str, str] | None = None,
) -> RivalComparison:
    """`aliases`: rival product name → our product name for matches the names alone miss (e.g. read by a model)."""
    categories = {i.category for i in rival.items if i.category}
    ours: dict[str, tuple[str, int, str]] = {}          # normalized name → (name, price, category)
    for rack, slot in store.all_slots:
        for item in slot.items:
            key = _product_key(item.name)
            if key not in ours:
                category = _category_of(rack.rack_desc, rack.rack_name, item.name, rack.type) if categories else ""
                ours[key] = (item.name, item.price, category)
    ours_here = {k: v for k, v in ours.items() if not categories or v[2] in categories}
    prices: list[PriceComparison] = []
    canonical: dict[str, str] = {}                      # rival product name → our key, or its own normalized name
    for item in rival.items:
        if not item.labeled:
            continue
        name = display_name(item)
        key = _product_key(name)
        raw_alias = (aliases or {}).get(name)
        alias = _product_key(raw_alias) if raw_alias else None
        if key in ours:
            hit = key
        elif alias is not None and alias in ours:
            hit = alias
        else:
            hit = None
        canonical[name] = hit if hit is not None else f"rival:{key}"
        if hit is None:
            continue
        our_name, our_price, _ = ours[hit]
        if item.price is not None and not item.price_estimated and item.price > 0 and our_price > 0:
            prices.append(PriceComparison(name=our_name, rival_price=item.price, our_price=our_price, ratio=item.price / our_price))
    index = math.exp(sum(math.log(p.ratio) for p in prices) / len(prices)) if prices else None
    theirs = set(canonical.values())
    mine = set(ours_here) | {k for k in theirs if k in ours}
    matched = len(theirs & set(ours))
    overlap = len(theirs & mine) / len(theirs | mine) if theirs | mine else 0.0
    only_rival = [n for n, k in canonical.items() if k.startswith("rival:")]
    only_ours = [v[0] for k, v in ours_here.items() if k not in theirs]
    return RivalComparison(
        matched=matched, rival_products=len(canonical), our_products_in_categories=len(ours_here),
        price_index=index, overlap=round(overlap, 4),
        only_rival=only_rival[:20], only_ours=only_ours[:20], prices=sorted(prices, key=lambda p: p.ratio),
        suggested_pull_factor=round(min(1.5, max(0.67, (1 / index) ** elasticity)), 3) if index else None,
    )
