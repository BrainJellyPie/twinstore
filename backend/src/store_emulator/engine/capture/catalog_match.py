"""Free text read off a shelf → the app's vocabulary: catalog category, typical price, price units.

Categories are the keys of the generic bilingual catalog (`engine.layout_gen.catalog.CATALOG`):
they drive rack labels, shopper category matching and the typical-price fallback used when a
price tag is unreadable.
"""

import difflib
import math
import re
import unicodedata
from functools import cache

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.engine.layout_gen.catalog import (
    CATALOG,
    CATEGORY_LABELS,
    ZERO_DECIMAL,
    CatalogItem,
    localized,
)

# Words a model (or a shopper) uses for a category that the catalog's own names may not contain.
_EXTRA_WORDS: dict[str, set[str]] = {
    "soft_drinks": {"soft", "drink", "drinks", "soda", "cola", "pop", "juice", "lemonade", "carbonated", "beverage",
                    "tea", "iced", "음료", "탄산", "주스", "사이다", "콜라"},
    "water_sports": {"water", "mineral", "sparkling", "sports", "isotonic", "electrolyte", "hydration", "생수", "물",
                     "이온음료"},
    "energy_coffee": {"energy", "coffee", "latte", "espresso", "americano", "caffeine", "cold", "brew", "커피", "에너지"},
    "dairy": {"dairy", "milk", "yogurt", "yoghurt", "cheese", "kefir", "cream", "우유", "요거트", "치즈", "유제품"},
    "beer_alcohol": {"beer", "lager", "ale", "ipa", "wine", "soju", "sake", "liquor", "alcohol", "spirits", "whisky",
                     "vodka", "cider", "맥주", "소주", "와인", "주류", "막걸리"},
    "chips": {"chips", "chip", "crisps", "snack", "snacks", "puffs", "crackers", "popcorn", "pretzels", "nachos",
              "과자", "스낵", "칩"},
    "sweets": {"candy", "chocolate", "sweets", "confectionery", "gum", "cookie", "cookies", "biscuit", "biscuits",
               "jelly", "gummy", "gummies", "wafer", "caramel", "사탕", "초콜릿", "젤리", "쿠키", "껌"},
    "instant_food": {"instant", "noodle", "noodles", "ramen", "ramyeon", "cup", "soup", "canned", "rice", "pasta",
                     "sauce", "curry", "라면", "즉석", "통조림"},
    "fresh_meals": {"sandwich", "kimbap", "lunch", "bento", "meal", "wrap", "salad", "rice ball", "onigiri",
                    "burger", "도시락", "김밥", "샌드위치"},
    "bakery": {"bread", "bakery", "bun", "buns", "croissant", "muffin", "cake", "donut", "pastry", "bagel", "빵"},
    "ice_cream": {"ice", "frozen", "popsicle", "gelato", "sorbet", "dumplings", "pizza", "아이스크림", "냉동"},
    "household": {"household", "cleaning", "detergent", "soap", "tissue", "tissues", "toilet", "paper", "battery",
                  "batteries", "bags", "cable", "umbrella", "생활용품", "세제", "휴지"},
    "health_beauty": {"shampoo", "conditioner", "toothpaste", "toothbrush", "lotion", "cream", "cosmetic",
                      "cosmetics", "beauty", "skincare", "deodorant", "vitamin", "vitamins", "medicine", "mask",
                      "sunscreen", "personal", "care", "hygiene", "샴푸", "치약", "화장품", "비타민"},
    "stationery": {"pen", "pens", "pencil", "notebook", "stationery", "tape", "glue", "marker", "문구"},
    "car_care": {"car", "motor", "oil", "windshield", "automotive", "차량"},
    "fresh_produce": {"fruit", "fruits", "vegetable", "vegetables", "produce", "eggs", "egg", "tofu", "kimchi",
                      "banana", "apple", "과일", "채소", "계란"},
    "souvenirs": {"souvenir", "gift", "postcard", "keychain", "magnet", "기념품"},
    "checkout_impulse": set(),
    "coffee_station": set(),
}

# Rack types that hold each category by default (used to break ties).
_COLD = {"soft_drinks", "water_sports", "energy_coffee", "dairy", "beer_alcohol", "fresh_meals", "ice_cream",
         "fresh_produce"}

_SIZE_RE = re.compile(r"^\d+([.,]\d+)?(ml|l|g|kg|oz|pk|입|매|구|캔)?$")


def normalize_text(text: str) -> str:
    """Lowercase, NFKC, punctuation → space, single spaces (keeps Hangul)."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = re.sub(r"[^\w]+", " ", t)
    return " ".join(t.split())


def tokens(text: str) -> list[str]:
    return [t for t in normalize_text(text).split() if t and not _SIZE_RE.match(t)]


@cache
def _vocabulary() -> dict[str, dict[str, float]]:
    """category → token weights. Category words (labels, synonyms) weigh 1, words of product names 0.5,
    each divided by the number of categories sharing the word ("beer" names the beer category even
    though "Root Beer" is a soft drink)."""
    explicit: dict[str, set[str]] = {}
    derived: dict[str, set[str]] = {}
    for cat, items in CATALOG.items():
        en, ko = CATEGORY_LABELS.get(cat, (cat, cat))
        explicit[cat] = {w for w in {*_EXTRA_WORDS.get(cat, set()), *tokens(en), *tokens(ko)} if w}
        names: set[str] = set()
        for item in items:
            names |= {t for t in tokens(item.en) if len(t) >= 3} | set(tokens(item.ko))
        derived[cat] = names - explicit[cat]

    def counts(groups: dict[str, set[str]]) -> dict[str, int]:
        out: dict[str, int] = {}
        for words in groups.values():
            for w in words:
                out[w] = out.get(w, 0) + 1
        return out

    n_explicit, n_derived = counts(explicit), counts(derived)
    vocab: dict[str, dict[str, float]] = {}
    for cat in CATALOG:
        weights = {w: 0.5 / n_derived[w] for w in derived[cat]}
        weights.update({w: 1.0 / n_explicit[w] for w in explicit[cat]})
        vocab[cat] = weights
    return vocab


def best_catalog_item(name: str, categories: list[str] | None = None) -> tuple[str, CatalogItem, float] | None:
    """Closest catalog product by name (English or Korean): (category, item, similarity 0–1)."""
    query = normalize_text(name)
    if not query:
        return None
    query_without_size = " ".join(tokens(name))
    best: tuple[str, CatalogItem, float] | None = None
    for cat in categories or list(CATALOG):
        for item in CATALOG.get(cat, []):
            for text in (item.en, item.ko):
                ratio = difflib.SequenceMatcher(None, query, normalize_text(text)).ratio()
                # A missing pack size must not let unrelated categories outweigh an exact product name.
                if query == query_without_size and query == " ".join(tokens(text)):
                    ratio = 1.0
                if ratio == 1.0:
                    return cat, item, ratio
                if best is None or ratio > best[2]:
                    best = (cat, item, ratio)
    return best


def match_category(category_text: str, name: str = "", *, rack_type: str = "shelf") -> str:
    """Best catalog category for a model's free-text category and product name; "" if nothing matches.

    A name that is almost exactly a catalog product decides directly. Otherwise category words count
    twice as much as name words; ties go to categories that fit the rack type (fridges hold drinks,
    dairy, meals, frozen food).
    """
    exact = best_catalog_item(name)
    if exact is not None and exact[2] >= 0.85:
        return exact[0]
    vocab = _vocabulary()
    cat_tokens = tokens(category_text)
    name_tokens = tokens(name)
    joined_cat = normalize_text(category_text)
    best, best_score = "", 0.0
    for cat, weights in vocab.items():
        if cat in ("checkout_impulse", "coffee_station"):
            continue
        score = 2.0 * sum(weights.get(t, 0.0) for t in cat_tokens)
        score += sum(weights.get(t, 0.0) for t in name_tokens)
        score += 2.0 * sum(1.0 for phrase in _EXTRA_WORDS.get(cat, set()) if " " in phrase and phrase in joined_cat)
        if score > 0 and (rack_type == "fridge") == (cat in _COLD):
            score += 0.05
        if score > best_score:
            best, best_score = cat, score
    return best


def typical_price(category: str, name: str, currency: str) -> tuple[int | None, str]:
    """(typical price in minor units, catalog product it came from or "category median")."""
    anywhere = best_catalog_item(name)
    if anywhere is not None and anywhere[2] >= 0.85:
        return localized(anywhere[1], currency)[1], anywhere[1].en
    if category in CATALOG:
        within = best_catalog_item(name, [category])
        if within is not None and within[2] >= 0.6:
            return localized(within[1], currency)[1], within[1].en
        prices = sorted(localized(i, currency)[1] for i in CATALOG[category])
        return prices[len(prices) // 2], "category median"
    return None, ""


_NUMBER_RE = re.compile(r"\d[\d,.\s']*")


def _parse_number(text: str) -> tuple[float, bool] | None:
    """'2.49' → (2.49, True); '1,800' → (1800, False); '1.800' → (1800, False); '12,50' → (12.5, True)."""
    m = _NUMBER_RE.search(text)
    if m is None:
        return None
    raw = re.sub(r"[\s']", "", m.group(0)).rstrip(".,")
    if not raw:
        return None
    if "," in raw and "." in raw:
        decimal_sep = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands = "." if decimal_sep == "," else ","
        raw = raw.replace(thousands, "").replace(decimal_sep, ".")
        return float(raw), True
    for sep in (",", "."):
        if sep in raw:
            head, _, tail = raw.rpartition(sep)
            if len(tail) == 3 and head.replace(sep, "").isdigit():
                return float(raw.replace(sep, "")), False      # thousands separator
            if len(tail) in (1, 2):
                return float(head.replace(sep, "") + "." + tail), True
            return float(raw.replace(sep, "")), False
    return float(raw), False


def price_minor_units(label: ShelfItemLabel, currency: str, typical: int | None) -> int | None:
    """Tag price → integer minor units of `currency`, disambiguating units with the typical price.

    A tag read as "249" in a USD store is far more likely $2.49 than $249: among the readings
    (as written, ×100, ÷100) the one closest to the category's typical price wins, but the literal
    reading is kept unless it is more than 6× off.
    """
    code = currency.upper()
    zero_decimal = code in ZERO_DECIMAL
    parsed = _parse_number(label.price_text) if label.price_text else None
    if parsed is None and label.price is not None and label.price > 0:
        value = float(label.price)
        parsed = (value, not value.is_integer())
    if parsed is None:
        return None
    value, has_decimals = parsed
    if value <= 0:
        return None
    literal = round(value) if zero_decimal else round(value * 100)
    candidates = {literal}
    if not zero_decimal and not has_decimals:
        candidates.add(round(value))          # cents written without the decimal point
    if zero_decimal and has_decimals:
        candidates.add(round(value * 1000))   # "1.8" for ₩1,800
    candidates = {c for c in candidates if c > 0}
    if typical is None or typical <= 0 or len(candidates) == 1:
        return literal if literal > 0 else None
    best = min(candidates, key=lambda c: abs(math.log(c / typical)))
    if best != literal and abs(math.log(literal / typical)) <= math.log(6):
        return literal
    return best
