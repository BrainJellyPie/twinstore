import { describe, expect, it } from "vitest";
import { useLocale } from "@/shared/i18n/i18n";
import { currencyCode, formatDecimal, formatMoney, formatPercent, majorUnitText, minorUnitDivisor, splitPriceList, toMinor } from "../money";

describe("money", () => {
  it("maps the legacy USD_CENTS label to USD", () => {
    expect(currencyCode("USD_CENTS")).toBe("USD");
    expect(currencyCode(undefined)).toBe("USD");
    expect(currencyCode("krw")).toBe("KRW");
  });

  it("knows zero-decimal currencies", () => {
    expect(minorUnitDivisor("USD")).toBe(100);
    expect(minorUnitDivisor("KRW")).toBe(1);
  });

  it("formats minor units", () => {
    expect(formatMoney(549, "USD")).toContain("5.49");
    expect(formatMoney(1500, "KRW")).toContain("1,500");
    expect(formatPercent(0.1234)).toBe("12.3%");
    expect(formatPercent(0.1234, 1, "fr").replace(/\s/g, " ")).toBe("12,3 %");
    expect(formatPercent(0.375, 0, "ko")).toBe("38%");
    expect(formatPercent(-0.0004)).toBe("0.0%");
    expect(formatDecimal(0.5, 2)).toBe("0.50");
    expect(formatDecimal(0.5, 1, "fr")).toBe("0,5");
    expect(formatDecimal(1234.5, 1, "es").replace(/\s/g, " ")).toMatch(/^1[ .]?234,5$/);
  });
});

it.each(["USD", "EUR", "GBP", "CAD", "AUD", "NZD", "CHF", "PLN"])("does not drop a minor unit when formatting a large %s amount", (currency) => {
  expect(formatMoney(Number.MAX_SAFE_INTEGER, currency)).toMatch(/[.,]91(?:\D|$)/);
  expect(formatMoney(-Number.MAX_SAFE_INTEGER, currency)).toMatch(/[.,]91(?:\D|$)/);
  expect(formatMoney(Number.MAX_SAFE_INTEGER - 1, currency)).toMatch(/[.,]90(?:\D|$)/);
});

it.each([
  [0, "0", "0.00"], [1, "0.01", "0.01"], [10, "0.1", "0.10"], [100, "1", "1.00"],
  [123456789, "1234567.89", "1234567.89"],
  [9007199254740990, "90071992547409.9", "90071992547409.90"],
  [9007199254740991, "90071992547409.91", "90071992547409.91"],
] as const)("round-trips %i minor units without losing precision", (minor, trimmed, fixed) => {
  expect(majorUnitText(minor, "USD")).toBe(trimmed);
  expect(majorUnitText(minor, "USD", { fixed: true })).toBe(fixed);
  expect(toMinor(trimmed, 100)).toBe(minor);
  expect(toMinor(fixed, 100)).toBe(minor);
  expect(majorUnitText(minor, "JPY", { fixed: true })).toBe(String(minor));
});

it.each([-1, -10, -99, -100, -101, -9007199254740991])("keeps the sign of %i including negative subunit amounts", (minor) => {
  expect(majorUnitText(minor, "USD")).toBe(`-${majorUnitText(-minor, "USD")}`);
  expect(formatMoney(minor, "USD")).toBe(`-${formatMoney(-minor, "USD")}`);
});

it("retains compact, fractional-minor-unit and unknown-code formatting", () => {
  expect(formatMoney(123456700, "USD", { compact: true })).toBe("$1.2M");
  expect(formatMoney(1.5, "USD")).toBe("$0.02");
  expect(formatMoney(123, "invalid")).toBe("1.23 invalid");
  expect(formatMoney(-0, "USD")).toBe("-$0.00");
});

it.each(["en", "ko", "zh", "ja", "es", "fr"] as const)("formats money in the app's selected %s locale, not the browser's", (locale) => {
  const previous = useLocale.getState().locale;
  try {
    useLocale.getState().setLocale(locale);
    const euro = new Intl.NumberFormat(locale, { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
    expect(formatMoney(123456, "EUR")).toBe(euro.format(1234.56));
    expect(formatMoney(123456700, "EUR", { compact: true })).toBe(new Intl.NumberFormat(locale, {
      style: "currency", currency: "EUR", notation: "compact", maximumFractionDigits: 1 }).format(1234567));
    expect(formatMoney(1234567, "invalid")).toBe(`${(12345.67).toLocaleString(locale)} invalid`);
  } finally {
    useLocale.getState().setLocale(previous);
  }
});

it("keeps cached formatters apart per locale and honours an explicit locale", () => {
  const previous = useLocale.getState().locale;
  try {
    useLocale.getState().setLocale("en");
    expect(formatMoney(123456, "EUR")).toBe("€1,234.56");
    useLocale.getState().setLocale("fr");
    expect(formatMoney(123456, "EUR")).toBe(new Intl.NumberFormat("fr", { style: "currency", currency: "EUR" }).format(1234.56));
    expect(formatMoney(123456, "EUR", { locale: "en" })).toBe("€1,234.56");
  } finally {
    useLocale.getState().setLocale(previous);
  }
});

it.each([["fr", "2,50", 250], ["es", "0,5", 50], ["fr", "12,99", 1299], ["fr", "1,500", 150000], ["es", "2.50", 250]] as const)(
  "reads a decimal comma typed in %s (%s), keeping a three-digit group as thousands", (locale, text, minor) => {
    expect(toMinor(text, 100, locale)).toBe(minor);
  },
);

it("keeps rejecting a decimal comma where the language writes a decimal point", () => {
  expect(toMinor("2,50", 100, "en")).toBeNull();
  expect(toMinor("2,50", 100, "ko")).toBeNull();
});

it("splits a typed price list by the language's list separator", () => {
  expect(splitPriceList("1,49, 1,79 ; 1.99;2,5", "fr")).toEqual(["1,49", "1,79", "1.99", "2,5"]);
  expect(splitPriceList("1.49,1.79, 1,500", "en")).toEqual(["1.49", "1.79", "1", "500"]);
});
