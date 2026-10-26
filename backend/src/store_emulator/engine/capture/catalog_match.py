"""Free text read off a shelf → the app's vocabulary: catalog category, typical price, price units.

Categories are the keys of the generic bilingual catalog (`engine.layout_gen.catalog.CATALOG`):
they drive rack labels, shopper category matching and the typical-price fallback used when a
price tag is unreadable.
"""

import difflib
import math
import re
import unicodedata
from functools import cache, lru_cache

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.domain.product_edits import MAX_PRICE
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


@lru_cache(maxsize=256)
def _category_names(items: tuple[CatalogItem, ...]) -> tuple[tuple[CatalogItem, str, str], ...]:
    """Normalize the bundled catalog once per category; retain no user-supplied labels."""
    rows: list[tuple[CatalogItem, str, str]] = []
    for item in items:
        for text in (item.en, item.ko):
            normalized = normalize_text(text)
            without_size = " ".join(t for t in normalized.split() if not _SIZE_RE.match(t))
            rows.append((item, normalized, without_size))
    return tuple(rows)


def best_catalog_item(name: str, categories: list[str] | None = None) -> tuple[str, CatalogItem, float] | None:
    """Closest catalog product by name (English or Korean): (category, item, similarity 0–1)."""
    query = normalize_text(name)
    if not query:
        return None
    query_without_size = " ".join(tokens(name))
    catalog = [(cat, _category_names(tuple(CATALOG.get(cat, [])))) for cat in categories or list(CATALOG)]
    # All exact matches score 1. Preserve the first one in catalog order, including omitted pack sizes.
    for cat, rows in catalog:
        for item, text, without_size in rows:
            if query == text or (query == query_without_size and query == without_size):
                return cat, item, 1.0
    best: tuple[str, CatalogItem, float] | None = None
    for cat, rows in catalog:
        for item, text, _ in rows:
            matcher = difflib.SequenceMatcher(None, query, text)
            # These are upper bounds: skipping a tie cannot change the first winning offer or score.
            if best is not None and (matcher.real_quick_ratio() <= best[2] or matcher.quick_ratio() <= best[2]):
                continue
            ratio = matcher.ratio()
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


_NUMBER_RE = re.compile(r"(?:\d|[.,](?=\d))[\d,.\s']*")
# Only compare recognized currencies. Shared symbols do not identify an ISO code:
# an unqualified dollar/yen sign still uses the store's currency as before.
_PRICE_CURRENCY_SYMBOLS = {
    "USD": "$", "KRW": "₩원", "JPY": "¥円", "EUR": "€", "GBP": "£", "CNY": "¥",
    "CAD": "$", "AUD": "$", "NZD": "$", "SGD": "$", "HKD": "$", "TWD": "$", "CLP": "$",
    "VND": "", "IDR": "", "ISK": "", "HUF": "", "CHF": "", "INR": "",
}
_PRICE_CURRENCY_CODE_RE = re.compile(
    rf"(?<![A-Za-z])({'|'.join(_PRICE_CURRENCY_SYMBOLS)})(?![A-Za-z])", re.IGNORECASE,
)
_NON_SELLING_PREFIX_RE = re.compile(
    r"(?:\b(?:save|saved|saving|savings|discount|rebate|cash[\s-]*back|coupon(?:\s+value)?|was|msrp|rrp)"
    r"|할인액|절약|値引き)\s*(?:(?:up\s+to|at\s+least|as\s+much\s+as)\s*)?:?\s*$",
    re.IGNORECASE,
)
_SAVINGS_SUFFIX_RE = re.compile(
    r"^(?:off\b|savings?\b|rebate\b|cash[\s-]*back\b|(?:할인|절약|引き|割引|値引き)(?:\s|$))", re.IGNORECASE,
)
_MEASURE_UNIT = (
    r"(?:fl\.?\s*oz|(?:kilo|milli)?grams?|(?:milli|centi|deci)?lit(?:er|re)s?"
    r"|pounds?|ounces?|kg|mg|g|lbs?|oz|ml|cl|dl|l|리터|밀리리터|킬로그램|그램)"
)
_MEASURE_RATE_RE = re.compile(
    rf"(?:(?:[/∕⁄]|\bper\s+)\s*{_MEASURE_UNIT}(?:\s*(?:당|当たり|あたり))?"
    rf"|(?<!\w){_MEASURE_UNIT}\s*(?:당|当たり|あたり))(?!\w)",
    re.IGNORECASE,
)


def _integer_digits(raw: str, separators: str) -> str | None:
    """Accept plain digits or complete western/Indian thousands groups, never joined price fragments."""
    if raw.isdecimal():
        return raw
    groups = re.split(rf"\s+|['{re.escape(separators)}]", raw)
    if len(groups) < 2 or any(not group.isdecimal() for group in groups):
        return None
    western = 1 <= len(groups[0]) <= 3 and all(len(group) == 3 for group in groups[1:])
    indian = 1 <= len(groups[0]) <= 2 and len(groups[-1]) == 3 and all(len(group) == 2 for group in groups[1:-1])
    return "".join(groups) if western or indian else None


def _parse_number(text: str) -> tuple[float, bool] | None:
    """'2.49' → (2.49, True); '1,800' → (1800, False); '1.800' → (1800, False); '12,50' → (12.5, True)."""
    normalized = unicodedata.normalize("NFKC", text).replace("’", "'")
    if "%" in normalized or "٪" in normalized:
        return None
    matches = list(_NUMBER_RE.finditer(normalized))
    if len(matches) != 1:
        return None
    match = matches[0]
    before, after = normalized[:match.start()].strip(), normalized[match.end():].strip()
    # A savings/coupon/reference value is not a selling price, even when the model left
    # its numeric price unknown. Strip currency marks only for this label test.
    price_context = [re.sub(r"[$€£¥₩¢원円]", "", _PRICE_CURRENCY_CODE_RE.sub("", part)).strip()
                     for part in (before, after)]
    if _NON_SELLING_PREFIX_RE.search(price_context[0]) or _SAVINGS_SUFFIX_RE.search(price_context[1]):
        return None
    if any(_MEASURE_RATE_RE.search(part) for part in price_context):
        # The photographed package can contain a different volume/weight.
        return None
    if (re.search(r"[-−–—]\s*(?:[$€£¥₩]|[A-Z]{3})?\s*$", before, re.IGNORECASE)
            or after.startswith(("-", "−")) or before.endswith((".", ","))
            or "(" in before and ")" in after):
        return None
    raw = re.sub(r"\s*([,.' ])\s*", r"\1", match.group(0).strip().rstrip(".,"))
    if not raw:
        return None
    decimal = ""
    if "," in raw and "." in raw:
        decimal = "," if raw.rfind(",") > raw.rfind(".") else "."
        if raw.count(decimal) != 1:
            return None
    else:
        for sep in (",", "."):
            if raw.count(sep) == 1:
                head, _, tail = raw.partition(sep)
                if not head or set(head) == {"0"} or len(tail) != 3:
                    decimal = sep
    if decimal:
        head, _, fraction = raw.rpartition(decimal)
        whole = _integer_digits(head, "." if decimal == "," else ",") if head else "0"
        if whole is None or not fraction.isdecimal():
            return None
        number = f"{whole}.{fraction}"
    else:
        number = _integer_digits(raw, ",.")
        if number is None:
            return None
    try:
        return float(number), bool(decimal)
    except ValueError:
        return None


def price_minor_units(label: ShelfItemLabel, currency: str, typical: int | None) -> int | None:
    """Tag price → integer minor units of `currency`, disambiguating units with the typical price.

    A tag read as "249" in a USD store is far more likely $2.49 than $249: among the readings
    (as written, ×100, ÷100) the one closest to the category's typical price wins, but the literal
    reading is kept unless it is more than 6× off.
    """
    code = currency.upper()
    printed = unicodedata.normalize("NFKC", label.price_text)
    if any(match.upper() != code for match in _PRICE_CURRENCY_CODE_RE.findall(printed)):
        return None
    if code in _PRICE_CURRENCY_SYMBOLS and any(
        symbol in printed and symbol not in _PRICE_CURRENCY_SYMBOLS[code] for symbol in "$€£¥₩원円"
    ):
        return None
    zero_decimal = code in ZERO_DECIMAL
    parsed = _parse_number(label.price_text) if label.price_text else None
    if parsed is None and any(character.isdigit() for character in label.price_text):
        # A numeric guess must not override an explicitly ambiguous/negative printed tag.
        return None
    if parsed is None and label.price is not None and label.price > 0:
        value = float(label.price)
        parsed = (value, not value.is_integer())
    if parsed is None:
        return None
    value, has_decimals = parsed
    if not math.isfinite(value) or value < 0:
        return None
    cents = "¢" in printed or re.search(r"\bcents?\b", printed, re.IGNORECASE) is not None
    major_symbol = any(symbol in printed for symbol in "$€£¥₩원円")
    major_unit = major_symbol or re.search(rf"(?<![A-Za-z]){re.escape(code)}(?![A-Za-z])", printed, re.IGNORECASE) is not None
    if cents and (zero_decimal or major_symbol):
        return None
    if value == 0:
        # Only an explicit printed price is free; a missing/unqualified zero
        # or a positive amount rounded down to zero still needs review.
        return 0 if major_unit or cents else None
    scaled = value if zero_decimal or cents else value * 100
    if not math.isfinite(scaled) or scaled > MAX_PRICE:
        return None
    literal = round(scaled)
    if cents or major_unit:
        # Printed currency/cent units outrank the catalog's guess about an unmarked number.
        return literal if literal > 0 else None
    candidates = {literal}
    if not zero_decimal and not has_decimals:
        candidates.add(round(value))          # cents written without the decimal point
    if zero_decimal and has_decimals:
        candidates.add(round(value * 1000))   # "1.8" for ₩1,800
    candidates = {c for c in candidates if 0 < c <= MAX_PRICE}
    if not candidates:
        return None
    if typical is None or typical <= 0:
        return literal if literal > 0 else None
    if len(candidates) == 1:
        return next(iter(candidates))
    best = min(candidates, key=lambda c: abs(math.log(c / typical)))
    if best != literal and abs(math.log(literal / typical)) <= math.log(6):
        return literal
    return best
