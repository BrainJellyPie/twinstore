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

it.each(["bottle", "box", "bag", "cup", "croissant", "cup", "bag", "can", "banana", "applePair", "box", "box", "bottle", "box", "tube", "tube"].map((kind, index) => [index, kind] as const))("matches grocery packshot %i after renaming", (index, kind) => {
  expect(classifyProduct("Renamed item", `/api/catalog-images/starter-02/${index}.webp`).kind).toBe(kind);
});

it.each([
  ["starter-03", ["box", "box", "box", "bag", "box", "box", "box", "box", "jar", "jar", "bag", "bag", "tube", "tube", "box", "box"]],
  ["starter-04", ["bag", "jar", "box", "box", "cup", "box", "box", "box", "box", "bag", "box", "box", "box", "box", "box", "bottle"]],
] as const)("retains non-food and specialty packages for %s in any language", (sheet, kinds) => {
  for (const [index, kind] of kinds.entries()) {
    for (const name of ["Renamed", "지역 상품", "商品"]) {
      const product = classifyProduct(name, `/api/catalog-images/${sheet}/${index}.webp`);
      expect(product.kind).toBe(kind);
      expect([product.w, product.h, product.d].every(n => n > 0 && Number.isFinite(n))).toBe(true);
    }
  }
});

it("keeps frozen meals flat and art supplies out of drink classification", () => {
  expect(classifyProduct("Renamed", "/api/catalog-images/starter-04/3.webp")).toMatchObject({ category: "frozen", lieFlatInChest: true });
  for (const url of ["/api/catalog-images/starter-03/14.webp", "/api/catalog-images/starter-04/11.webp"])
    expect(classifyProduct("Watercolor Paint", url)).toMatchObject({ kind: "box", category: "other" });
});

it.each([
  ["starter-05", ["cup", "box", "box", "cup", "box", "cup", "bag", "cup", "cup", "bag", "teaCup", "bottle", "cup", "pot", "box", "cup"]],
  ["starter-06", ["box", "box", "box", "bag", "box", "box", "box", "bottle", "bag", "tube", "perfumeBottle", "box", "box", "box", "bag", "bottle"]],
] as const)("keeps menu and specialty photos attached to their package for %s", (sheet, kinds) => {
  for (const [index, kind] of kinds.entries())
    expect(classifyProduct("이름을 바꾼 상품", `/api/catalog-images/${sheet}/${index}.webp`).kind).toBe(kind);
});

it("distinguishes cafe drinks from milk and coffee tools after renaming", () => {
  for (let index = 0; index < 16; index++) {
    const product = classifyProduct("지역 상품", `/api/catalog-images/starter-07/${index}.webp`);
    expect(product.category).toBe(index < 12 ? "drink" : "bakery");
    expect(product.h).toBeGreaterThan(0);
  }
  for (const index of [12, 13, 14, 15])
    expect(classifyProduct("Milk Coffee", `/api/catalog-images/starter-08/${index}.webp`).category).toBe("other");
});

it("places fresh seafood photo trays flat in chest displays", () => {
  for (const index of [10, 11]) {
    const product = classifyProduct("상품", `/api/catalog-images/starter-08/${index}.webp`);
    expect(product.lieFlatInChest).toBe(true);
    expect(product.h).toBeLessThan(product.d);
  }
});

it("preserves grocery departments and non-food merchandise after localized renaming", () => {
  for (const index of [0, 1, 2, 3])
    expect(classifyProduct("지역 상품", `/api/catalog-images/starter-09/${index}.webp`).category).toBe("produce");
  for (const index of [10, 11])
    expect(classifyProduct("지역 상품", `/api/catalog-images/starter-09/${index}.webp`).category).toBe("candy");
  expect(classifyProduct("지역 상품", "/api/catalog-images/starter-09/12.webp")).toMatchObject({ category: "icecream", lieFlatInChest: true });
  for (let index = 0; index < 16; index++)
    expect(classifyProduct("Coffee", `/api/catalog-images/starter-10/${index}.webp`).category).toBe("other");
});

it("keeps pet food, cooking tools and detergent out of human-food departments", () => {
  for (let index = 0; index < 16; index++)
    expect(classifyProduct("Coffee", `/api/catalog-images/starter-11/${index}.webp`).category).toBe("other");
  for (let index = 0; index < 16; index++)
    expect(classifyProduct("지역 상품", `/api/catalog-images/starter-12/${index}.webp`).category).toBe(index === 12 || index === 13 ? "candy" : "other");
});

it("keeps meal photos separate from personal-care packaging after renaming", () => {
  for (let index = 0; index < 16; index++) {
    expect(classifyProduct("지역 상품", `/api/catalog-images/starter-13/${index}.webp`).category).toBe("pantry");
    expect(classifyProduct("Milk Tea", `/api/catalog-images/starter-14/${index}.webp`).category).toBe("other");
  }
  expect(classifyProduct("상품", "/api/catalog-images/starter-14/11.webp").kind).toBe("jar");
  expect(classifyProduct("상품", "/api/catalog-images/starter-14/12.webp").kind).toBe("tube");
});
