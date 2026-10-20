import { describe, expect, it } from "vitest";
import { currencyCode, formatMoney, formatPercent, minorUnitDivisor } from "../money";

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
