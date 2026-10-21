import { expect, it } from "vitest";
import { classifyProduct, productPalette } from "../productCatalog";

it.each([
  "Kiwi", "Kiwis", "Kiwifruit", "Kiwifruits", "Kiwi Fruit", "Kiwi Fruits",
  "Fresh Kiwi", "Organic Hayward Kiwis", "Ripe Whole Green Kiwifruit", "Kiwi Each",
  "Kiwis Loose", "Kiwi 500g", "Kiwis 1.5 kg", "Kiwifruit .25 lb", "KIWI 0.5 lbs",
  "  Fresh Whole Kiwi Fruit 1kg  ",
])("recognises %s as whole fuzzy-skinned fruit", name => {
  const spec = classifyProduct(name);
  expect(spec.kind).toBe("kiwi");
  expect(classifyProduct(name.toUpperCase()).kind).toBe("kiwi");
  expect(spec.w).toBeGreaterThan(spec.h);
  expect(spec.h).toBeCloseTo(0.06951961);
});

it.each([
  "Gold Kiwi", "Golden Kiwifruit", "Yellow Kiwi", "Red Kiwi", "Baby Kiwi", "Kiwiberries",
  "Kiwi Berries", "Kiwi Seeds", "Kiwi Plant", "Kiwi Bird Toy", "Kiwi Shoe Polish",
  "Peeled Kiwi", "Kiwi Slices", "Kiwi Halves", "Diced Kiwi", "Dried Kiwi", "Frozen Kiwis",
  "Kiwi Juice", "Kiwi Smoothie", "Kiwi Jam", "Kiwi Puree", "Kiwi Sorbet", "Kiwi Yogurt",
  "Kiwi 3pk", "Kiwis 2-pack", "Kiwi 6 count", "Kiwi 1kg 2pk", "Kiwi 0kg", "Kiwi 0.00 g",
  "Kiwi -1kg", "Kiwi NaN kg", "Kiwi Infinity kg", "Kiwi 1e3g", "Kiwi Strawberry Drink",
])("does not render %s as a single whole kiwi", name => {
  expect(classifyProduct(name).kind).not.toBe("kiwi");
  expect(classifyProduct(name.toUpperCase()).kind).not.toBe("kiwi");
});

it.each(["Kiwi", "Green Kiwi", "Organic Hayward Kiwifruit", "Fresh Kiwi Fruit 500g"])("keeps the fallback skin brown for %s", name => {
  const color = productPalette(name).base;
  const [red, green, blue] = [1, 3, 5].map(offset => parseInt(color.slice(offset, offset + 2), 16));
  expect(red).toBeGreaterThan(green!);
  expect(green).toBeGreaterThan(blue!);
});
