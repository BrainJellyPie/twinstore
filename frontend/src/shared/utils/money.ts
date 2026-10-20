// Prices and budgets are integers in the currency's minor unit (USD → cents,
// KRW → won). The run summary carries the currency ("USD_CENTS" for legacy USD
// runs, an ISO code otherwise).

const ZERO_DECIMAL = new Set(["KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"]);

export function currencyCode(summaryCurrency: string | undefined): string {
  if (!summaryCurrency || summaryCurrency === "USD_CENTS") return "USD";
  return summaryCurrency.toUpperCase();
}

export function minorUnitDivisor(code: string): number {
  return ZERO_DECIMAL.has(code) ? 1 : 100;
}

const formatters = new Map<string, Intl.NumberFormat>();

function formatter(code: string, compact: boolean): Intl.NumberFormat {
  const key = `${code}:${compact}`;
  let f = formatters.get(key);
  if (!f) {
    f = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: code,
      notation: compact ? "compact" : "standard",
      maximumFractionDigits: compact ? 1 : ZERO_DECIMAL.has(code) ? 0 : 2,
    });
    formatters.set(key, f);
  }
  return f;
}

export function formatMoney(minor: number, code = "USD", opts: { compact?: boolean } = {}): string {
  const value = minor / minorUnitDivisor(code);
  try {
    return formatter(code, opts.compact ?? false).format(value);
  } catch {
    // Unknown ISO code — fall back to a plain number with the code appended.
    return `${value.toLocaleString()} ${code}`;
  }
}

export function formatPercent(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}
