import { expect, it } from "vitest";
import { DEFAULT_TEMPLATE_CHOICE, choiceFromGeneration, templateRequest, validTemplateChoice } from "../templateOptions";

it.each([1, 4, 16])("preserves category limit %i through request and saved reuse", (limit) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, products_per_category: 2, category_product_limits: { soft_drinks: limit, desserts: 1 } };
  expect(validTemplateChoice(choice)).toBe(true);
  expect(templateRequest(choice)).toMatchObject({ products_per_category: 2, category_product_limits: choice.category_product_limits });
  expect(choiceFromGeneration(templateRequest(choice), "saved")).toMatchObject({ ...choice, sourceSetupId: "saved" });
});
it.each([0, -1, 17, 1.5, NaN, Infinity])("blocks invalid category limit %s before preview and export", (limit) => {
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, category_product_limits: { soft_drinks: limit } })).toBe(false);
});
it.each(["", "x".repeat(81)])("blocks invalid category identifier %s", (category) => {
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, category_product_limits: { [category]: 1 } })).toBe(false);
});
it("enforces the 64-entry file boundary without requiring unused categories to be on the current format", () => {
  const category_product_limits = Object.fromEntries(Array.from({ length: 64 }, (_, i) => [`category_${i}`, 1]));
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, category_product_limits })).toBe(true);
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, category_product_limits: { ...category_product_limits, extra: 1 } })).toBe(false);
});
it("restores inherited limits for saved layouts that predate category overrides", () => {
  const restored = choiceFromGeneration({ template_id: "compact_pharmacy", currency: "USD", seed: 0 }, "legacy");
  expect(restored.category_product_limits).toEqual({});
  expect(validTemplateChoice(restored)).toBe(true);
});
