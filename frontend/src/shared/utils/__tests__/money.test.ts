import { describe, expect, it } from "vitest";
import { currencyCode, formatMoney, formatPercent, majorUnitText, minorUnitDivisor, toMinor } from "../money";

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
