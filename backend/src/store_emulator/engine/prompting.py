"""Currency-aware prompt fragments.

Prices and budgets are stored as integers in the currency's minor unit
(USD → cents, KRW → won). Prompts must tell the model which unit it is reading,
otherwise a Korean store's 1500 (= ₩1,500) would be read as $15.00.
Shopper-facing fragments use the simulation prompts' Korean wording; the
customer-generation budget instruction follows its English field definitions.
"""

import re
from collections.abc import Collection

_ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}


def canonical_identifier(value: str, allowed: Collection[str]) -> str:
    """Keep exact identifiers; recover only one known whitespace/case variant."""
    if value in allowed:
        return value
    stripped = value.strip()
    if stripped in allowed:
        return stripped
    matches = [key for key in allowed if key.casefold() == stripped.casefold()]
    return matches[0] if len(matches) == 1 else value


def price_unit_rule(currency: str) -> str:
    code = currency.upper()
    if code == "USD":
        return "모든 가격과 예산은 US cents 단위입니다 (예: 549¢ = $5.49)."
    if code == "KRW":
        return "모든 가격과 예산은 원(KRW) 단위 정수입니다 (예: 1500 = 1,500원)."
    if code in _ZERO_DECIMAL:
        return f"모든 가격과 예산은 {code} 단위 정수입니다 (소수점 없음)."
    return f"모든 가격과 예산은 {code}의 최소 화폐 단위(1/100) 정수입니다."


def format_price(amount: int, currency: str) -> str:
    code = currency.upper()
    if code == "USD":
        return f"{amount}¢"
    if code == "KRW":
        return f"{amount}원"
    return f"{amount} {code}"


def display_price(amount: int, currency: str) -> str:
    """Price as printed on a shelf tag: $2.49, 1,500원, ¥300, 12.34 EUR."""
    code = currency.upper()
    if code == "USD":
        return f"${amount / 100:,.2f}"
    if code == "KRW":
        return f"{amount:,}원"
    if code == "JPY":
        return f"¥{amount:,}"
    if code in _ZERO_DECIMAL:
        return f"{amount:,} {code}"
    return f"{amount / 100:,.2f} {code}"


def format_budget(budget_min: int, budget_max: int, currency: str) -> str:
    if budget_max <= 0:
        return (f"최소 {format_price(budget_min, currency)} (상한 미지정)" if budget_min > 0
                else "미지정 (고정된 지출 상한 없음)")
    return f"{format_price(budget_min, currency)}~{format_price(budget_max, currency)}"


def minor_unit_scale(currency: str) -> int:
    """Stored money units per major unit, matching the simulator's currency convention."""
    return 1 if currency.upper() in _ZERO_DECIMAL else 100


def budget_example(currency: str) -> str:
    """Model-facing major amounts; the customer harness performs the unit conversion."""
    code = currency.upper()
    precision = "whole amounts" if minor_unit_scale(code) == 1 else "amounts with at most two decimal places"
    return (f"Write {precision} in {code}, as quoted numeric strings with a dot for decimals and no currency symbols. "
            f"Use the amounts in {code} as stated in the customer profile. Do not convert to cents or multiply by 100; "
            "the application converts to stored money units")


def relevant_first[T](entries: list[tuple[str, str, T]], query: str, limit: int) -> list[T]:
    """Up to `limit` entries for a prompt, the strongest word matches first, then the rest taken in turn from
    each group (a shelf), so a long catalog is never cut off at whichever shelf happens to come last.

    `entries` are (group, text, payload)."""
    asked = _words(query)
    scored: list[tuple[int, int, tuple[str, str, T]]] = []
    for entry in entries:
        text_matches = asked & _words(entry[1])
        all_matches = asked & _words(f"{entry[0]} {entry[1]}")
        if all_matches:
            # A plural and its generated singular are one clue, not two. Prefer product text over shelf words.
            text_score = len(text_matches) - sum(w.endswith("s") and w[:-1] in text_matches for w in text_matches)
            all_score = len(all_matches) - sum(w.endswith("s") and w[:-1] in all_matches for w in all_matches)
            scored.append((text_score, all_score, entry))
    hits = [entry for _, _, entry in sorted(scored, key=lambda row: (-row[0], -row[1]))]
    taken = {id(e) for e in hits}
    rest: dict[str, list[tuple[str, str, T]]] = {}
    for e in entries:
        if id(e) not in taken:
            rest.setdefault(e[0], []).append(e)
    ordered: list[tuple[str, str, T]] = list(hits)
    queues: list[list[tuple[str, str, T]]] = [q for q in rest.values() if q]
    while queues and len(ordered) < limit:
        for q in queues:
            ordered.append(q.pop(0))
        queues = [q for q in queues if q]
    return [payload for _, _, payload in ordered[:limit]]


def _words(text: str) -> set[str]:
    out = {w for w in re.split(r"[^\w]+", text.casefold()) if len(w) > 2}
    return out | {w[:-1] for w in out if w.endswith("s") and len(w) > 3}


def resolve_listed[T](asked: str, listed: dict[str, T], *, max_name_length: int | None = None) -> T | None:
    """Resolve an exact name or a copied description referring to only one target.

    `listed` is keyed by casefolded name. Separate mentions must refer to the same value.
    At a model field's limit, a known long-name prefix takes precedence over shorter word matches.
    """
    key = asked.strip().strip('"').strip().casefold()
    if not key:
        return None
    if max_name_length is not None and len(asked) == max_name_length:
        matches = [value for name, value in listed.items() if name.startswith(key)]
        if matches:
            return matches[0] if all(value == matches[0] for value in matches) else None
    if key in listed:
        return listed[key]
    hits = [(m.start(), m.end(), name) for name in listed if name
            for m in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", key)]
    # A shorter name inside a full longer name is not a second target. Its
    # separate occurrence elsewhere still counts, as do overlapping names.
    found = {name for start, end, name in hits if not any(
        other_start <= start and end <= other_end and (start, end) != (other_start, other_end)
        for other_start, other_end, _ in hits)}
    if not found:
        return None
    matches = [listed[n] for n in found]
    return matches[0] if all(value == matches[0] for value in matches) else None
