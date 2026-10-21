import { expect, it } from "vitest";
import { draftEdits, priceText } from "../productDrafts";
it("rounds exact decimal text, supports zero-decimal currencies and retains maximum safe cents", () => {
  expect(draftEdits(new Map([["A", { price: "1.005" }]]), "USD")).toEqual([{ sku: "A", price: 101 }]);
  expect(draftEdits(new Map([["A", { price: "1500.5" }]]), "KRW")).toEqual([{ sku: "A", price: 1501 }]);
  expect(priceText(Number.MAX_SAFE_INTEGER, "USD")).toBe("90071992547409.91");
  expect(draftEdits(new Map([["__proto__", { price: "90071992547409.91", promo: "" }]]), "USD")).toEqual([{ sku: "__proto__", price: Number.MAX_SAFE_INTEGER, promo: "" }]);
});
it.each(["", " ", "-1", "NaN", "Infinity", "1e2", "90071992547409.92", "1".repeat(101)])("rejects invalid prices: %s", (price) => {
  expect(() => draftEdits(new Map([["A", { price }]]), "USD")).toThrow();
});
it("bounds edited rows, trims text and preserves Unicode", () => {
  expect(draftEdits(new Map([["차", { name: " café 🍵 ", promo: " " }]]), "USD")).toEqual([{ sku: "차", name: "café 🍵", promo: "" }]);
  expect(() => draftEdits(new Map([["A", { name: " " }]]), "USD")).toThrow();
  expect(() => draftEdits(new Map(Array.from({ length: 501 }, (_, i) => [String(i), { price: "1" } as const])), "USD")).toThrow("500");
});
