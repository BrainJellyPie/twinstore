import { expect, it } from "vitest";
import * as THREE from "three";
import { classifyProduct, productPalette } from "../productCatalog";
import { createPackageGeometry } from "../productGeometries";
import { ZONE_BODY } from "../atlasLayout";

it.each([
  "Hamburger Bun",
  "Burger Bun",
  "Plain Hamburger Bun",
  "Fresh Burger Bun",
  "Unseeded Hamburger Bun",
  "Fresh Plain Hamburger Bun",
  "Hamburger Bun Each",
  "Burger Bun Loose",
  "Hamburger Bun Single",
  "Hamburger Buns Each",
  "Plain Burger Buns Loose",
  "Fresh Unseeded Hamburger Buns Single",
  "  Fresh Hamburger Bun  ",
  "Fresh  Burger Bun"
])('recognises %s as an individual plain burger bun', name => {
  const spec = classifyProduct(name);
  expect(spec.kind).toBe("burgerBun"); expect(classifyProduct(name.toUpperCase()).kind).toBe("burgerBun");
  expect(spec.w).toBeCloseTo(0.11082269); expect(spec.h).toBeCloseTo(0.05778436); expect(spec.d).toBeCloseTo(0.10592587);
});

it.each([
  "Hamburger Buns",
  "Burger Buns",
  "Fresh Hamburger Buns",
  "Plain Burger Buns",
  "Sesame Hamburger Bun",
  "Seeded Burger Bun",
  "Brioche Burger Bun",
  "Potato Burger Bun",
  "Whole Wheat Burger Bun",
  "Pretzel Burger Bun",
  "Gluten Free Burger Bun",
  "Black Burger Bun",
  "Bao Bun",
  "Cinnamon Bun",
  "Hot Dog Bun",
  "Dinner Roll",
  "Hamburger",
  "Cheeseburger",
  "Chicken Burger",
  "Hamburger Bun Sandwich",
  "Filled Burger Bun",
  "Frozen Hamburger Bun",
  "Toasted Burger Bun",
  "Sliced Hamburger Bun",
  "Half Hamburger Bun",
  "Hamburger Bun Crumbs",
  "Hamburger Bun Mix",
  "Hamburger Bun Dough",
  "Hamburger Bun Toy",
  "Hamburger Bun Candle",
  "Hamburger Buns 6pk",
  "Hamburger Bun 2-pack",
  "Burger Buns 8 count",
  "Hamburger Bun 500g",
  "Hamburger Bun 0kg",
  "Burger Bun -1kg",
  "Burger Bun NaN g",
  "Burger Bun Infinity kg",
  "Hamburger Bun Each 2pk",
  "Burger Bun Single Pack",
  "Burger Buns Loose 6pk",
  "Hamburger Bun Each Each",
  "Buns",
  "Bun"
])('keeps %s out of the individual plain-bun scan', name => {
  expect(classifyProduct(name).kind).not.toBe("burgerBun"); expect(classifyProduct(name.toUpperCase()).kind).not.toBe("burgerBun");
});

it.each(["Hamburger Buns", "Burger Buns", "Fresh Hamburger Buns", "Plain Burger Buns"])("keeps %s in its existing bag", name => {
  expect(classifyProduct(name).kind).toBe("bag");
});

it.each([0, 1] as const)("keeps a closed, golden-brown roll fallback at detail %s", detail => {
  const geometry = createPackageGeometry("burgerBun", detail), material = new THREE.MeshBasicMaterial();
  try {
    geometry.computeBoundingBox();
    geometry.boundingBox!.min.toArray().forEach((value, i) => expect(value).toBeCloseTo([-0.5, 0, -0.5][i]!, 6));
    geometry.boundingBox!.max.toArray().forEach((value, i) => expect(value).toBeCloseTo([0.5, 1, 0.5][i]!, 6));
    const normal = geometry.getAttribute("normal"), uv = geometry.getAttribute("uv");
    for (let i = 0; i < normal.count; i++) {
      expect(Math.hypot(normal.getX(i), normal.getY(i), normal.getZ(i))).toBeCloseTo(1, 5);
      expect(uv.getX(i)).toBeCloseTo(ZONE_BODY[0], 6); expect(uv.getY(i)).toBeCloseTo(ZONE_BODY[1], 6);
    }
    const mesh = new THREE.Mesh(geometry, material);
    for (const sign of [-1, 1]) {
      const ray = new THREE.Raycaster(new THREE.Vector3(0, sign > 0 ? 2 : -1, 0), new THREE.Vector3(0, -sign, 0));
      expect(ray.intersectObject(mesh).length).toBeGreaterThan(0);
    }
    const base = productPalette("Fresh Hamburger Bun").base;
    const [r, g, b] = [1, 3, 5].map(offset => parseInt(base.slice(offset, offset + 2), 16));
    expect(r).toBeGreaterThan(g!); expect(g).toBeGreaterThan(b!);
  } finally { geometry.dispose(); material.dispose(); }
});
