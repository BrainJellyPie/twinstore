import { expect, it } from "vitest";
import { classifyProduct, productPalette } from "../productCatalog";

it.each([
  "Asian Pear", "Asian Pears", "Nashi Pear", "Nashi Pears", "Asian-Pear", "Nashi-Pears",
  "Fresh Asian Pears", "Organic Whole Nashi Pear", "Ripe Asian Pear Each", "Asian Pears Loose",
  "Asian Pear 500g", "Nashi Pears 1.5 kg", "Asian Pear .25 lb", "Asian Pear 0.5 lbs", "Asian Pear 1g",
  "  Organic Raw Asian Pears 1kg  ", "Fresh Asian  Pears", "Whole Nashi-Pear Each",
])("recognises %s as a whole Asian pear", name => {
  const spec = classifyProduct(name);
  expect(spec.kind).toBe("asianPear");
  expect(classifyProduct(name.toUpperCase()).kind).toBe("asianPear");
  expect(spec.w).toBeCloseTo(0.04344488);
  expect(spec.h).toBeCloseTo(0.06696554);
  expect(spec.d).toBeCloseTo(0.04342672);
});

it.each([
  "Pear", "Pears", "Bartlett Pear", "Bosc Pear", "Anjou Pear", "Conference Pear", "Red Pear",
  "Korean Pear", "Chinese White Pear", "Ya Pear", "Shinko Pear", "Asian Pear Tree", "Asian Pear Seeds",
  "Asian Pear Plant", "Asian Pear Toy", "Nashi Pear Candle", "Poached Asian Pear", "Roasted Asian Pears",
  "Dried Asian Pear", "Asian Pear Chips", "Asian Pear Pie", "Asian Pear Bread", "Asian Pear Tea",
  "Asian Pear Puree", "Asian Pear Powder", "Peeled Asian Pear", "Asian Pear Slices", "Diced Asian Pear",
  "Frozen Asian Pears", "Canned Asian Pear", "Asian Pear Juice", "Nashi Pear Smoothie", "Asian Pear Jam",
  "Asian Pear 3pk", "Asian Pears 2-pack", "Asian Pears 6 count", "Asian Pear 1kg 2pk",
  "Asian Pear 0kg", "Asian Pear 0.00 g", "Asian Pear -1kg", "Asian Pear NaN kg", "Asian Pear Infinity kg",
  "Asian Pear 1e3g", "Asian Pears 00.5kg", "Nashi", "Pearlescent Asian Ornament",
])("does not render %s as the scanned whole fruit", name => {
  expect(classifyProduct(name).kind).not.toBe("asianPear");
  expect(classifyProduct(name.toUpperCase()).kind).not.toBe("asianPear");
});

it.each(["Asian Pear", "Organic Nashi Pears", "Raw Asian-Pear", "Fresh Whole Asian Pear 500g"])("keeps the fallback skin yellow-green for %s", name => {
  const color = productPalette(name).base;
  const [red, green, blue] = [1, 3, 5].map(offset => parseInt(color.slice(offset, offset + 2), 16));
  expect(green).toBeGreaterThan(red!);
  expect(red).toBeGreaterThan(blue!);
});
