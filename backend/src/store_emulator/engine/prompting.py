"""Currency-aware prompt fragments.

Prices and budgets are stored as integers in the currency's minor unit
(USD → cents, KRW → won). Prompts must tell the model which unit it is reading,
otherwise a Korean store's 1500 (= ₩1,500) would be read as $15.00.
Fragments are Korean because they are spliced into Korean prompt bodies
(see AGENTS.md, i18n policy).
"""

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
