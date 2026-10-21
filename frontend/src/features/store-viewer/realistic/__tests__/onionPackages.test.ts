import { expect, it } from "vitest";
import { classifyProduct, productPalette } from "../productCatalog";

it.each([
  "Red Onions", "White Onion", "Sweet Onion", "Spring Onions", "Green Onion", "Pearl Onions",
  "Shallots", "Onion Seeds", "Onion Sets", "Onion Rings", "French Onion Soup", "Onion Powder",
  "Diced Onions", "Peeled Onion", "Frozen Onions", "Pickled Onions", "Onion Chutney",
  "Onion Chips", "Onion Bread", "Onion Dip", "Onion Sauce", "Onions 3pk", "Onions 2-pack",
  "Yellow Onions 4 count", "Onions 1kg 2pk", "Onions 0kg", "Onions 0.00 g", "Onions -1kg",
  "Onions NaN kg", "Onions Infinity kg", "Onions 1e3g", "Yellow Onion Cleaner",
])("keeps %s separate from a whole yellow onion", name => {
  expect(classifyProduct(name).kind).not.toBe("onion");
  expect(classifyProduct(name.toUpperCase()).kind).not.toBe("onion");
});

it.each(["Onion", "Yellow Onion", "Organic Brown Onions 500g", "Fresh Whole Onions Each"])("keeps the missing-scan fallback for %s warm brown", name => {
  const color = productPalette(name).base;
  const [red, green, blue] = [1, 3, 5].map(offset => parseInt(color.slice(offset, offset + 2), 16));
  expect(red).toBeGreaterThan(green!);
  expect(green).toBeGreaterThan(blue!);
});
