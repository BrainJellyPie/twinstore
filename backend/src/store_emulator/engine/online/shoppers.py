"""Online shoppers: a panel drawn from a site's own catalog, or the project's customers taken online.

Every shopper has a mission — why they opened the site — and what that mission needs: what they look for, the words
they would type, a budget, how price-sensitive, patient and at ease with websites they are, and their device. The
panel depends only on the request and the control site's catalog, so every variant of a study is shopped by the very
same people.
"""

import random
import re
from statistics import median

from store_emulator.domain.online import (
    SHOPPER_MISSIONS,
    Accessibility,
    OnlineProduct,
    OnlineShopper,
    OnlineSite,
    ShopperMission,
    Vision,
)
from store_emulator.domain.persona import AGE_GROUPS, GENDERS, AgeGroup, Persona
from store_emulator.domain.types import stable_seed
from store_emulator.engine.prompting import display_price

_AGE_WEIGHTS: dict[AgeGroup, float] = {"10s": 0.08, "20s": 0.24, "30s": 0.24, "40s": 0.19, "50s": 0.14, "60s+": 0.11}
_SAVVY: dict[AgeGroup, float] = {"10s": 0.85, "20s": 0.85, "30s": 0.75, "40s": 0.65, "50s": 0.5, "60s+": 0.35}
_MOBILE: dict[AgeGroup, float] = {"10s": 1.35, "20s": 1.25, "30s": 1.05, "40s": 0.95, "50s": 0.8, "60s+": 0.6}
_IDENTITIES: dict[AgeGroup, tuple[str, ...]] = {
    "10s": ("High-school student", "First-year university student"),
    "20s": ("University student", "Young professional", "Junior designer", "Graduate student"),
    "30s": ("Busy parent", "Office worker", "Freelancer", "New homeowner"),
    "40s": ("Working parent", "Small-business owner", "Team manager"),
    "50s": ("Empty-nester", "Teacher", "Senior manager"),
    "60s+": ("Retiree", "Grandparent", "Semi-retired consultant"),
}
_PATIENCE: dict[ShopperMission, tuple[int, int]] = {
    "purchase": (360, 720), "browse": (240, 900), "compare": (480, 1080), "deal_hunt": (300, 720), "gift": (360, 840),
    "replenish": (180, 360),
}
_SENSITIVITY: dict[ShopperMission, float] = {
    "purchase": 0.45, "browse": 0.5, "compare": 0.6, "deal_hunt": 0.9, "gift": 0.35, "replenish": 0.3,
}
_UNIT = re.compile(r"^\d|^(ml|l|g|kg|pk|pc|pcs|cm|mm|ct|oz|x)$", re.IGNORECASE)


_FILLER = frozenset({"pair", "pairs", "set", "pack", "duo", "trio", "kit", "refill", "with", "and", "for", "the", "of",
                     "over", "in", "on", "to"})


def product_terms(name: str) -> str:
    """The words a shopper would search a product by: its kind, without sizes, pack counts and packaging words."""
    words = [w for w in re.findall(r"[^\s/,()]+", name)
             if not _UNIT.match(w) and len(w) > 1 and w.lower() not in _FILLER]
    return " ".join(words[-2:]).lower() if words else name.lower()


def _level(value: float) -> str:
    return "low" if value < 0.4 else "high" if value > 0.7 else "medium"


def _pick_mission(rng: random.Random, missions: dict[ShopperMission, float]) -> ShopperMission:
    keys: list[ShopperMission] = [k for k in SHOPPER_MISSIONS if missions.get(k, 0) > 0]
    if not keys:
        return "purchase"
    return rng.choices(keys, weights=[missions[k] for k in keys], k=1)[0]


def _mission_details(
    site: OnlineSite, mission: ShopperMission, rng: random.Random, preferred: list[str],
) -> tuple[str, str, list[str], str, int]:
    """(goal, target category, search terms, target product, budget) of one mission."""
    in_stock = [p for p in site.products if p.stock != 0] or site.products
    prices = sorted(p.price for p in in_stock)
    typical = int(median(prices)) if prices else 0

    def money(amount: int) -> str:
        return display_price(amount, site.currency)

    liked = [c for c in site.categories if any(w.lower() in c.name.lower() or c.name.lower() in w.lower() for w in preferred)]
    category = rng.choice(liked) if liked and rng.random() < 0.7 else rng.choice(site.categories)
    in_category = [p for p in in_stock if p.category_id == category.id] or in_stock
    if mission in ("purchase", "replenish"):
        pool = in_category if mission == "purchase" else sorted(in_stock, key=lambda p: -p.weekly_sales)[:max(4, len(in_stock) // 3)]
        product: OnlineProduct = rng.choice(pool)
        if mission == "replenish":
            budget = round(product.price * rng.uniform(1.5, 3.0))
            return (f"Reorder {product.name}, which you buy regularly", product.category_id, [product.name.lower()],
                    product.id, budget)
        terms = product_terms(product.name)
        budget = round(product.price * rng.uniform(1.15, 2.2))
        return (f"Buy {terms} (you expect to pay about {money(product.price)})", product.category_id, [terms], "", budget)
    cat_prices = sorted(p.price for p in in_category)
    if mission == "compare":
        budget = round(cat_prices[len(cat_prices) * 3 // 4] * rng.uniform(1.0, 1.4))
        words = category.name.lower()
        return (f"Compare a few {words} options and buy the best one for the money, up to {money(budget)}",
                category.id, [words], "", budget)
    if mission == "gift":
        budget = round(cat_prices[len(cat_prices) * 2 // 3] * rng.uniform(1.1, 1.6))
        return (f"Find a gift from {category.name.lower()} for a friend's birthday, up to {money(budget)}",
                category.id, [category.name.lower()], "", budget)
    if mission == "deal_hunt":
        budget = round(typical * rng.uniform(2.0, 4.0))
        return ("Look for real bargains; buy only something that is clearly discounted", "", [], "", budget)
    budget = round(typical * rng.uniform(1.0, 3.0))
    return (f"Window-shop {category.name.lower()} for ideas, with no plan to buy anything in particular",
            category.id, [category.name.lower()], "", budget)


def _shopper(
    site: OnlineSite, index: int, rng: random.Random, *, missions: dict[ShopperMission, float], mobile_share: float,
    persona: Persona | None,
) -> OnlineShopper:
    if persona is not None:
        age, gender = persona.age_group, persona.gender
        identity, description = persona.identity, persona.description
        preferred = persona.preferred_categories
    else:
        age = rng.choices(AGE_GROUPS, weights=[_AGE_WEIGHTS[a] for a in AGE_GROUPS], k=1)[0]
        gender = rng.choice(GENDERS)
        identity, description, preferred = rng.choice(_IDENTITIES[age]), "", []
    mission = _pick_mission(rng, missions)
    goal, category, terms, product, budget = _mission_details(site, mission, rng, preferred)
    savvy = min(1.0, max(0.05, rng.gauss(_SAVVY[age], 0.12)))
    device = "mobile" if rng.random() < min(1.0, mobile_share * _MOBILE[age]) else "desktop"
    sensitivity = min(1.0, max(0.0, rng.gauss(_SENSITIVITY[mission], 0.12)))
    low, high = _PATIENCE[mission]
    patience = round(rng.uniform(low, high) * (0.8 + 0.4 * (1 - savvy)))
    has_account = rng.random() < (0.9 if mission == "replenish" else 0.3)
    if not description:
        description = (f"{identity} in their {age.removesuffix('+')}{' or older' if age == '60s+' else ''}, shopping on "
                       f"a {device}. Comfort with websites: {_level(savvy)}; price sensitivity: {_level(sensitivity)}.")
    return OnlineShopper(
        id=f"os{index + 1:04d}",
        identity=identity, age_group=age, gender=gender, device=device, mission=mission, goal=goal,
        target_category=category, target_terms=terms, target_product=product, budget=max(0, budget),
        price_sensitivity=round(sensitivity, 2), patience_sec=max(30, patience), tech_savvy=round(savvy, 2),
        has_account=has_account, description=description[:600], persona_id=persona.id if persona else "",
    )


# Shares used by the "realistic" eyesight mix. Red–green colour vision deficiency affects about 8 % of men and 0.5 %
# of women of northern European descent; presbyopia ("older eyes") is near-universal after 50; low vision rises
# with age. Rounded literature figures, not a calibrated population.
_LOW_VISION: dict[AgeGroup, float] = {"10s": 0.01, "20s": 0.01, "30s": 0.015, "40s": 0.02, "50s": 0.03, "60s+": 0.07}
_OLDER_EYES: dict[AgeGroup, float] = {"10s": 0.0, "20s": 0.0, "30s": 0.0, "40s": 0.25, "50s": 0.6, "60s+": 0.8}


def _vision(accessibility: Accessibility, shopper: OnlineShopper, rng: random.Random) -> Vision:
    if accessibility != "realistic":
        return accessibility
    if rng.random() < _LOW_VISION[shopper.age_group]:
        return "low_vision"
    if rng.random() < (0.08 if shopper.gender == "Male" else 0.005):
        return "color_blind"
    return "aging_eyes" if rng.random() < _OLDER_EYES[shopper.age_group] else "typical"


def sample_shoppers(
    site: OnlineSite, count: int, *, seed: int, missions: dict[ShopperMission, float], mobile_share: float,
    personas: list[Persona] | None = None, accessibility: Accessibility = "typical",
) -> list[OnlineShopper]:
    """`count` shoppers for `site`. With `personas`, each shopper is one of them (drawn without repeats while there
    are enough) given an online mission; otherwise the panel's own people. Eyesight is drawn from its own random
    stream, so changing `accessibility` keeps everything else about the shoppers the same."""
    pool: list[Persona] = []
    if personas:
        order = list(personas)
        random.Random(stable_seed(seed, "online-personas")).shuffle(order)
        pool = order
    shoppers: list[OnlineShopper] = []
    for i in range(count):
        rng = random.Random(stable_seed(seed, "online-shopper", i))
        persona = pool[i % len(pool)] if pool else None
        shopper = _shopper(site, i, rng, missions=missions, mobile_share=mobile_share, persona=persona)
        eyes = _vision(accessibility, shopper, random.Random(stable_seed(seed, "online-vision", i)))
        shoppers.append(shopper.model_copy(update={"vision": eyes}))
    return shoppers
