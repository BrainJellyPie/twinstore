"""Online shoppers: a panel drawn from a site's own catalog, or the project's customers taken online.

Every shopper has a mission — why they opened the site — and what that mission needs: what they look for, the words
they would type, a budget, how price-sensitive, patient and at ease with websites they are, and their device. The
panel depends only on the request and the control site's catalog, so every variant of a study is shopped by the very
same people.
"""

import math
import random
import re
from statistics import median

from store_emulator.domain.online import (
    SHOPPER_MISSIONS,
    Accessibility,
    Arrival,
    OnlineProduct,
    OnlineShopper,
    OnlineSite,
    PageKind,
    PageRef,
    ShopperMission,
    Vision,
)
from store_emulator.domain.persona import AGE_GROUPS, GENDERS, AgeGroup, Persona
from store_emulator.domain.types import stable_seed
from store_emulator.engine.prompting import display_price

from .browser import search_products

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
    "purchase": (830, 1660), "browse": (70, 550), "compare": (1100, 2480), "deal_hunt": (690, 1660), "gift": (830, 1930),
    "replenish": (410, 830),
}
# Window shoppers who only glance around rather than browse at length; those who do browse give the site longer.
_GLANCING = 0.75
_BROWSING_PATIENCE = (140, 2070)
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
) -> tuple[str, str, list[str], str, int, tuple[int, int]]:
    """(goal, target category, search terms, target product, budget, patience range) of one mission."""
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
                    product.id, budget, _PATIENCE[mission])
        terms = product_terms(product.name)
        budget = round(product.price * rng.uniform(1.15, 2.2))
        return (f"Buy {terms} (you expect to pay about {money(product.price)})", product.category_id, [terms], "", budget,
                _PATIENCE[mission])
    cat_prices = sorted(p.price for p in in_category)
    if mission == "compare":
        budget = round(cat_prices[len(cat_prices) * 3 // 4] * rng.uniform(1.0, 1.4))
        words = category.name.lower()
        return (f"Compare a few {words} options and buy the best one for the money, up to {money(budget)}",
                category.id, [words], "", budget, _PATIENCE[mission])
    if mission == "gift":
        budget = round(cat_prices[len(cat_prices) * 2 // 3] * rng.uniform(1.1, 1.6))
        return (f"Find a gift from {category.name.lower()} for a friend's birthday, up to {money(budget)}",
                category.id, [category.name.lower()], "", budget, _PATIENCE[mission])
    if mission == "deal_hunt":
        budget = round(typical * rng.uniform(2.0, 4.0))
        return ("Look for real bargains; buy only something that is clearly discounted", "", [], "", budget,
                _PATIENCE[mission])
    budget = round(typical * rng.uniform(0.4, 1.2))
    if rng.random() < _GLANCING:
        goal = (f"Look around {category.name.lower()} out of mild curiosity, with no plan to buy; you move on as soon as "
                "nothing catches your eye")
        patience = _PATIENCE[mission]
    else:
        goal = f"Window-shop {category.name.lower()} for ideas, with no plan to buy anything in particular"
        patience = _BROWSING_PATIENCE
    return goal, category.id, [category.name.lower()], "", budget, patience


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
    goal, category, terms, product, budget, (low, high) = _mission_details(site, mission, rng, preferred)
    savvy = min(1.0, max(0.05, rng.gauss(_SAVVY[age], 0.12)))
    # Weight the odds so age preferences preserve both all-mobile and all-desktop panels.
    mobile_weight = mobile_share * _MOBILE[age]
    device = "mobile" if rng.random() < mobile_weight / (1 - mobile_share + mobile_weight) else "desktop"
    sensitivity = min(1.0, max(0.0, rng.gauss(_SENSITIVITY[mission], 0.12)))
    # Log-uniform: most visits are short and a few run long, as real session times are right-skewed.
    patience = round(math.exp(rng.uniform(math.log(low), math.log(high))) * (0.8 + 0.4 * (1 - savvy)))
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
    arrivals: dict[Arrival, float] | None = None,
) -> list[OnlineShopper]:
    """`count` shoppers for `site`. With `personas`, each shopper is one of them (drawn without repeats while there
    are enough) given an online mission; otherwise the panel's own people. Eyesight and where each visit comes from
    (`arrivals`: share per source, default all direct) are drawn from their own random streams, so changing them
    keeps everything else about the shoppers the same."""
    shares: dict[Arrival, float] = {a: w for a, w in (arrivals or {}).items() if w > 0} or {"direct": 1.0}
    sources, weights = list(shares), list(shares.values())
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
        arrival = random.Random(stable_seed(seed, "online-arrival", i)).choices(sources, weights)[0]
        shoppers.append(shopper.model_copy(update={"vision": eyes, "arrival": arrival}))
    return shoppers


_SOCIAL_PICKS = 8  # social posts feature one of the shop's most popular products


def landing(site: OnlineSite, shopper: OnlineShopper) -> PageRef:
    """The page a visit starts on. Direct visits open the home page; a search engine leads to the product page that
    best fits what the shopper looks for; a social post to one of the shop's most popular products; the shop's email
    to its deals (or the home page when nothing is discounted)."""
    if shopper.arrival == "search_engine":
        product = site.product(shopper.target_product) if shopper.target_product else None
        if product is None and shopper.target_terms:
            # An external search engine is independent of the shop's own search configuration.
            matches = search_products(site, " ".join(shopper.target_terms), mode="smart")
            product = matches[0] if matches else None
        if product is None:
            pool = [p for p in site.products if p.category_id == shopper.target_category] or site.products
            product = max(pool, key=lambda p: (p.weekly_sales, p.id))
        return PageRef(page=PageKind.PRODUCT, product_id=product.id)
    if shopper.arrival == "social":
        popular = sorted(site.products, key=lambda p: (-p.weekly_sales, p.id))[:_SOCIAL_PICKS]
        pick = random.Random(stable_seed("online-social", shopper.id)).choice(popular)
        return PageRef(page=PageKind.PRODUCT, product_id=pick.id)
    if shopper.arrival == "email" and any(p.discount_percent for p in site.products):
        return PageRef(page=PageKind.DEALS)
    return PageRef()


def at_rival(rival: OnlineSite, shopper: OnlineShopper, source: OnlineSite) -> OnlineShopper | None:
    """The same shopper looking for the same thing at a rival shop after leaving without buying, or None when the rival
    has nothing that fits (a search engine would not send them there). They arrive from a search engine on the rival's
    best match. A product the rival does not sell becomes its best search match for the same words; a category it does
    not have, its category of the same name or else that of the best match. Bargain hunters, who want nothing in
    particular, always fit."""
    moved = shopper.model_copy(update={"arrival": "search_engine"})
    matches = search_products(rival, " ".join(shopper.target_terms), mode="smart") if shopper.target_terms else []
    category = source.category(shopper.target_category) if shopper.target_category else None
    if shopper.target_product:
        wanted = source.product(shopper.target_product)
        same = [] if wanted is None else [p for p in rival.products if (
            p.sku == wanted.sku if wanted.sku else p.name.strip().casefold() == wanted.name.strip().casefold()
            and category is not None and (c := rival.category(p.category_id)) is not None
            and c.name.strip().casefold() == category.name.strip().casefold())]
        found = (next((p for p in same if p.id == shopper.target_product), None)
                 or (same[0] if len(same) == 1 else None) or (matches[0] if matches else None))
        if found is None:
            return None
        return moved.model_copy(update={"target_product": found.id, "target_category": found.category_id})
    if not shopper.target_category:
        return moved
    names = {category.name.strip().casefold()} if category is not None else {t.strip().casefold() for t in shopper.target_terms}
    same_categories = [c.id for c in rival.categories if c.name.strip().casefold() in names]
    named = (shopper.target_category if shopper.target_category in same_categories
             else same_categories[0] if len(same_categories) == 1 else None)
    if named is None and not matches:
        return None
    return moved.model_copy(update={"target_category": named or matches[0].category_id})
