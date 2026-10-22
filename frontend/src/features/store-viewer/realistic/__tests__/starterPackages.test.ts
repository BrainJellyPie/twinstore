import { expect, it } from "vitest";
import { classifyProduct } from "../productCatalog";

it.each([
  [0, "Barista Oat Milk 1L", "box", "drink"],
  [1, "Roasted Almond Butter 250g", "jar", "pantry"],
  [2, "Ceremonial Matcha Pouch 50g", "bag", "pantry"],
  [3, "House Roast Coffee Beans 250g", "bag", "pantry"],
  [4, "Gentle Botanical Hand Soap 300ml", "bottle", "other"],
  [5, "Flexible Fabric Bandages 20pk", "box", "other"],
  [6, "Vitamin C Tablets 60ct", "bottle", "other"],
  [7, "Compact Digital Thermometer", "box", "other"],
  [11, "Green Handle Camping Mug", "cup", "other"],
  [12, "Butter Croissant Bag 2pk", "bag", "bakery"],
  [13, "Glass Bottle Lemon Sparkling Water", "bottle", "drink"],
  [14, "Sea Salt Sweet Potato Chips", "bag", "snack"],
  [15, "Strawberry Preserve 200g", "jar", "pantry"],
])("uses the bundled %i packshot's package for the original or renamed item", (index, name, kind, category) => {
  for (const label of [String(name), "Renamed local product", "商品"])
    expect(classifyProduct(label, `/api/catalog-images/starter-01/${index}.webp`)).toMatchObject({ kind, category });
});

it.each([null, undefined, "/custom.png", "/api/catalog-images/starter-01/16.webp", "/api/catalog-images/unknown/3.webp", "https://other.test/api/catalog-images/starter-01/3.webp", "/api/catalog-images/starter-01/-1.webp"])("retains ordinary classification for unrelated image %s", (url) => {
  expect(classifyProduct("Mineral Water 500ml", url)).toMatchObject({ kind: "bottle", category: "drink" });
});
