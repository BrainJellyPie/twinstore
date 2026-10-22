"""Currency-aware prompt fragments.

Prices and budgets are stored as integers in the currency's minor unit
(USD → cents, KRW → won). Prompts must tell the model which unit it is reading,
otherwise a Korean store's 1500 (= ₩1,500) would be read as $15.00.
Fragments are Korean because they are spliced into Korean prompt bodies
(see AGENTS.md, i18n policy).
"""

import re

_ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}


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
    return f"{format_price(budget_min, currency)}~{format_price(budget_max, currency)}"


def budget_example(currency: str) -> str:
    """Example line for persona generation (budget_min / budget_max field rule)."""
    code = currency.upper()
    if code == "USD":
        return "예산 범위를 US cents 정수로 (예: $3.00~$8.00이면 budget_min=300, budget_max=800)"
    if code == "KRW":
        return "예산 범위를 원(KRW) 정수로 (예: 3,000~8,000원이면 budget_min=3000, budget_max=8000)"
    if code in _ZERO_DECIMAL:
        return f"예산 범위를 {code} 정수로 (소수점 없음)"
    return f"예산 범위를 {code}의 최소 화폐 단위(1/100) 정수로"


def relevant_first[T](entries: list[tuple[str, str, T]], query: str, limit: int) -> list[T]:
    """Up to `limit` entries for a prompt, those whose text shares a word with `query` first, then the rest taken in
    turn from each group (a shelf), so a long catalog is never cut off at whichever shelf happens to come last.

    `entries` are (group, text, payload)."""
    asked = _words(query)
    hits = [e for e in entries if asked & _words(f"{e[0]} {e[1]}")]
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


def resolve_listed[T](asked: str, listed: dict[str, T]) -> T | None:
    """What a name a model copied from a prompt listing refers to. `listed` is keyed by casefolded name. The exact name
    wins; otherwise the longest listed name the answer starts with or contains, since a model sometimes copies the
    brand, price or description that followed the name in the listing."""
    key = asked.strip().strip('"').strip().casefold()
    if not key:
        return None
    if key in listed:
        return listed[key]
    found = [n for n in listed if n and key.startswith(n)] or [n for n in listed if n and n in key]
    return listed[max(found, key=len)] if found else None
