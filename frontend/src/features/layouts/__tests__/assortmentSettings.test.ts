import { expect, it } from "vitest";
import { resolveAssortmentSettings, sameAssortmentSettings } from "../assortmentSettings";
import { DEFAULT_TEMPLATE_CHOICE, type TemplateChoice } from "../templateOptions";

const source = { ...DEFAULT_TEMPLATE_CHOICE, seed: 26, products_per_category: 2,
  category_product_limits: { soft_drinks: 3, electronics: 1 }, excluded_categories: ["household", "beer_alcohol"] };

it("resolves independent copies without carrying spatial or design settings", () => {
  const choice = { ...source, width: NaN, table_clearance: 0, requirements: "Retain this brief" };
  const settings = resolveAssortmentSettings(choice)!;
  expect(settings).toEqual({ seed: 26, products_per_category: 2, category_product_limits: source.category_product_limits, excluded_categories: source.excluded_categories });
  expect(settings.category_product_limits).not.toBe(source.category_product_limits);
  expect(settings.excluded_categories).not.toBe(source.excluded_categories);
  settings.category_product_limits.soft_drinks = 8; settings.excluded_categories.pop();
  expect(source.category_product_limits.soft_drinks).toBe(3);
  expect(source.excluded_categories).toHaveLength(2);
});
it("normalizes legacy omissions to full assortment and no exclusions", () => {
  expect(resolveAssortmentSettings({ seed: 0 })).toEqual({ seed: 0, products_per_category: null, category_product_limits: {}, excluded_categories: [] });
  expect(sameAssortmentSettings({ seed: 0 }, DEFAULT_TEMPLATE_CHOICE)).toBe(true);
});
it.each([Number.MIN_SAFE_INTEGER, -1, 0, Number.MAX_SAFE_INTEGER])("accepts reproducible safe seed %s", (seed) => {
  expect(resolveAssortmentSettings({ ...source, seed })?.seed).toBe(seed);
});
it.each<Partial<TemplateChoice>>([
  { seed: Number.MAX_SAFE_INTEGER + 1 }, { seed: NaN }, { seed: Infinity }, { seed: 1.5 },
  { products_per_category: 0 }, { products_per_category: 17 }, { products_per_category: 1.5 },
  { category_product_limits: { soft_drinks: 0 } }, { category_product_limits: { soft_drinks: NaN } },
  { category_product_limits: { soft_drinks: 17 } }, { category_product_limits: { "": 2 } },
  { category_product_limits: { ["x".repeat(81)]: 2 } },
  { category_product_limits: Object.fromEntries(Array.from({ length: 65 }, (_, i) => [String(i), 1])) },
  { excluded_categories: [""] }, { excluded_categories: ["x".repeat(81)] },
  { excluded_categories: Array.from({ length: 65 }, (_, i) => String(i)) },
])("rejects invalid assortment values: %o", (patch) => {
  expect(resolveAssortmentSettings({ ...source, ...patch })).toBeNull();
  expect(sameAssortmentSettings(source, { ...source, ...patch })).toBe(false);
});
it("compares category selections by meaning rather than insertion order or duplicate exclusions", () => {
  expect(sameAssortmentSettings(source, { ...source, category_product_limits: { electronics: 1, soft_drinks: 3 },
    excluded_categories: ["beer_alcohol", "household", "household"] })).toBe(true);
});
it.each<Partial<TemplateChoice>>([
  { seed: 27 }, { products_per_category: null }, { products_per_category: 16 },
  { category_product_limits: { soft_drinks: 4, electronics: 1 } },
  { category_product_limits: { soft_drinks: 3 } }, { excluded_categories: ["household"] },
])("detects a differing assortment setting: %o", (patch) => {
  expect(sameAssortmentSettings(source, { ...source, ...patch })).toBe(false);
});
