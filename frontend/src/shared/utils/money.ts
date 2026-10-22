// Prices and budgets are integers in the currency's minor unit (USD → cents,
// KRW → won). The run summary carries the currency ("USD_CENTS" for legacy USD
// runs, an ISO code otherwise).

import { useLocale } from "@/shared/i18n/i18n";

const ZERO_DECIMAL = new Set(["KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"]);

export function currencyCode(summaryCurrency: string | undefined): string {
  if (!summaryCurrency || summaryCurrency === "USD_CENTS") return "USD";
  return summaryCurrency.toUpperCase();
}

export function minorUnitDivisor(code: string): number {
  return ZERO_DECIMAL.has(code) ? 1 : 100;
}

export function majorUnitText(minor: number, code: string, opts: { fixed?: boolean } = {}): string {
  const divisor = minorUnitDivisor(code);
  if (divisor === 1 || !Number.isSafeInteger(minor)) return String(minor / divisor);
  const amount = BigInt(Math.abs(minor));
  const whole = `${minor < 0 ? "-" : ""}${amount / 100n}`;
  const fraction = String(amount % 100n).padStart(2, "0");
  const digits = opts.fixed ? fraction : fraction.replace(/0+$/, "");
  return digits ? `${whole}.${digits}` : whole;
}

export function toMinor(text: string, divisor: number): number | null {
  const amount = text.trim().replace(/^[$€£¥₩]\s*|\s*[$€£¥₩]$/g, "");
  if (!/^(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d*)?|\.\d+)$/.test(amount)) return null;
  if (!Number.isSafeInteger(divisor) || divisor <= 0) return null;
  const [whole = "", fraction = ""] = amount.replace(/,/g, "").split(".");
  const scale = 10n ** BigInt(fraction.length);
  // Round the decimal price before converting to binary floating point (1.005 USD = 101 cents).
  const scaled = BigInt(whole + fraction) * BigInt(divisor);
  const minor = Number((scaled + scale / 2n) / scale);
  return Number.isSafeInteger(minor) && minor >= 0 ? minor : null;
}

const formatters = new Map<string, Intl.NumberFormat>();

function cachedFormatter(key: string, create: () => Intl.NumberFormat): Intl.NumberFormat {
  let f = formatters.get(key);
  if (!f) {
    f = create();
    formatters.set(key, f);
  }
  return f;
}

function formatter(locale: string, code: string, compact: boolean): Intl.NumberFormat {
  return cachedFormatter(`${locale}:${code}:${compact}`, () => new Intl.NumberFormat(locale, {
    style: "currency",
    currency: code,
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : ZERO_DECIMAL.has(code) ? 0 : 2,
  }));
}

/** Formats in the app's selected language unless `locale` is given. */
export function formatMoney(minor: number, code = "USD", opts: { compact?: boolean; locale?: string } = {}): string {
  const locale = opts.locale ?? useLocale.getState().locale;
  const value = minor / minorUnitDivisor(code);
  try {
    const f = formatter(locale, code, opts.compact ?? false);
    if (!opts.compact && minorUnitDivisor(code) === 100 && Number.isSafeInteger(minor)) {
      // Dividing a large safe integer by 100 can already lose a cent. Format the
      // integer part with Intl and insert the exact minor units separately.
      const amount = BigInt(minor);
      const whole = amount / 100n;
      const fractionFormatter = cachedFormatter(`${locale}:fraction`, () => new Intl.NumberFormat(locale, {
        minimumIntegerDigits: 2, maximumFractionDigits: 0, useGrouping: false,
      }));
      const fraction = fractionFormatter.format((amount < 0n ? -amount : amount) % 100n);
      return f.formatToParts(whole === 0n && (minor < 0 || Object.is(minor, -0)) ? -0 : whole)
        .map((part) => part.type === "fraction" ? fraction : part.value).join("");
    }
    return f.format(value);
  } catch {
    // Unknown ISO code — fall back to a plain number with the code appended.
    return `${value.toLocaleString(locale)} ${code}`;
  }
}

export function formatPercent(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}
