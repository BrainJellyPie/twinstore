import { DEFAULT_TEMPLATE_CHOICE, validTemplateChoice, type TemplateChoice } from "./templateOptions";

export interface AssortmentSettings {
  seed: number;
  products_per_category: number | null;
  category_product_limits: Record<string, number>;
  excluded_categories: string[];
}

type AssortmentChoice = Pick<TemplateChoice, "seed" | "products_per_category" | "category_product_limits" | "excluded_categories">;

export function resolveAssortmentSettings(value: AssortmentChoice): AssortmentSettings | null {
  const settings: AssortmentSettings = {
    seed: value.seed,
    products_per_category: value.products_per_category ?? null,
    category_product_limits: { ...value.category_product_limits },
    excluded_categories: [...(value.excluded_categories ?? [])],
  };
  return validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, ...settings }) ? settings : null;
}

export function sameAssortmentSettings(left: AssortmentChoice, right: AssortmentChoice): boolean {
  const a = resolveAssortmentSettings(left), b = resolveAssortmentSettings(right);
  if (!a || !b || a.seed !== b.seed || a.products_per_category !== b.products_per_category) return false;
  const categories = Object.keys(a.category_product_limits);
  if (categories.length !== Object.keys(b.category_product_limits).length ||
    categories.some((category) => a.category_product_limits[category] !== b.category_product_limits[category])) return false;
  const excluded = new Set(a.excluded_categories), otherExcluded = new Set(b.excluded_categories);
  return excluded.size === otherExcluded.size && [...excluded].every((category) => otherExcluded.has(category));
}
