import { expect, it } from "vitest";
import { classifyProduct, productPalette } from "../productCatalog";

it.each([
  "Sweet Potato", "Sweet Potatoes", "Sweet-Potato", "Sweet-Potatoes", "Fresh Sweet Potatoes",
  "Organic Whole Sweet Potato", "Raw Sweet Potato Each", "Sweet Potatoes Loose", "Sweet Potato 500g",
  "Sweet Potatoes 1.5 kg", "Sweet Potato .25 lb", "Sweet Potato 0.5 lbs", "Sweet Potato 1g",
  "  Organic Raw Sweet Potatoes 1kg  ", "Fresh Sweet  Potatoes", "Whole Sweet-Potato Each",
])("recognises %s as an individual whole tuber", name => {
  const spec = classifyProduct(name);
  expect(spec.kind).toBe("sweetPotato");
  expect(classifyProduct(name.toUpperCase()).kind).toBe("sweetPotato");
  expect(spec.w).toBeGreaterThan(spec.h);
  expect(spec.w).toBeGreaterThan(spec.d);
  expect(spec.h).toBeCloseTo(0.05812428);
});

it.each([
  "Potato", "Potatoes", "Yam", "Yams", "Purple Sweet Potato", "White Sweet Potato", "Japanese Sweet Potato",
  "Orange Sweet Potato", "Sweet Potato Seeds", "Sweet Potato Plant", "Sweet Potato Slips", "Sweet Potato Toy",
  "Baked Sweet Potato", "Roasted Sweet Potatoes", "Cooked Sweet Potato", "Sweet Potato Fries", "Sweet Potato Chips",
  "Sweet Potato Crisps", "Sweet Potato Pie", "Sweet Potato Bread", "Sweet Potato Noodles", "Sweet Potato Flour",
  "Sweet Potato Powder", "Sweet Potato Puree", "Sweet Potato Mash", "Peeled Sweet Potato", "Sweet Potato Slices",
  "Diced Sweet Potato", "Sweet Potato Cubes", "Frozen Sweet Potatoes", "Canned Sweet Potato", "Sweet Potato Juice",
  "Sweet Potato Smoothie", "Sweet Potato Dog Treats", "Sweet Potato 3pk", "Sweet Potatoes 2-pack",
  "Sweet Potatoes 6 count", "Sweet Potato 1kg 2pk", "Sweet Potato 0kg", "Sweet Potato 0.00 g",
  "Sweet Potato -1kg", "Sweet Potato NaN kg", "Sweet Potato Infinity kg", "Sweet Potato 1e3g",
])("does not render %s as an individual raw sweet potato", name => {
  expect(classifyProduct(name).kind).not.toBe("sweetPotato");
  expect(classifyProduct(name.toUpperCase()).kind).not.toBe("sweetPotato");
});

it.each(["Sweet Potato", "Organic Sweet Potatoes", "Raw Sweet-Potato", "Fresh Whole Sweet Potato 500g"])("keeps the fallback skin reddish brown for %s", name => {
  const color = productPalette(name).base;
  const [red, green, blue] = [1, 3, 5].map(offset => parseInt(color.slice(offset, offset + 2), 16));
  expect(red).toBeGreaterThan(green!);
  expect(green).toBeGreaterThan(blue!);
});
