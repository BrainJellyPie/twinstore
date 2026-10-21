import { expect, it } from "vitest";
import * as THREE from "three";
import { classifyProduct } from "../productCatalog";
import { createPackageGeometry } from "../productGeometries";
import { layoutProducts } from "../productLayout";
import { planFixture } from "../fixtureSpecs";
import type { Rack } from "@/shared/types/domain";

it.each([
  ["Citrus Eau de Toilette 50ml", "perfumeBottle", "other"],
  ["Rose Eau de Parfum 50ml", "perfumeBottle", "other"],
  ["Cedar Eau de Parfum 50ml", "perfumeBottle", "other"],
  ["Vanilla Perfume Oil 10ml", "perfumeBottle", "other"],
  ["Green Tea Body Mist 100ml", "bottle", "other"],
  ["Lavender Room Spray 100ml", "bottle", "other"],
  ["Fig Reed Diffuser 100ml", "bottle", "other"],
  ["Amber Travel Spray 10ml", "bottle", "other"],
  ["Refillable Perfume Atomizer", "bottle", "other"],
  ["Fragrance Discovery Set 6pc", "box", "other"],
  ["Fragrance Gift Pouch", "bag", "other"],
  ["Sandalwood Candle 180g", "jar", "other"],
  ["Loose Black Tea Refill 100g", "bag", "pantry"],
  ["Ground Coffee Refill 250g", "bag", "pantry"],
  ["Brown Rice Refill 1kg", "bag", "pantry"],
  ["Wholegrain Pasta Refill 500g", "bag", "pantry"],
  ["Dish Soap Refill 500ml", "bag", "other"],
  ["Laundry Liquid Refill 1L", "bag", "other"],
  ["Classic Pearl Milk Tea", "teaCup", "drink"],
  ["Brown Sugar Pearl Milk", "teaCup", "drink"],
  ["Taro Milk Tea", "teaCup", "drink"],
  ["Matcha Pearl Latte", "teaCup", "drink"],
  ["Thai Milk Tea", "teaCup", "drink"],
  ["Jasmine Milk Tea", "teaCup", "drink"],
  ["Mango Fruit Tea", "teaCup", "drink"],
  ["Passion Fruit Green Tea", "teaCup", "drink"],
  ["Peach Oolong Tea", "teaCup", "drink"],
  ["Lychee Coconut Jelly Tea", "teaCup", "drink"],
  ["Oat Milk Pearl Tea", "teaCup", "drink"],
  ["Mini Milk Tea Tasting Set", "box", "drink"],
])("renders specialty packaging for %s", (name, kind, category) => {
  expect(classifyProduct(name)).toMatchObject({ kind, category, lieFlatInChest: false });
  expect(classifyProduct(`  ${name.toUpperCase()}  `)).toEqual(classifyProduct(name));
});

it.each([
  ["Black Tea 500ml", "bottle", "drink"], ["Bottled Jasmine Milk Tea", "bottle", "drink"],
  ["Mango Fruit Tea 6-pack", "box", "noodle"], ["Green Tea Ice Cream", "pint", "icecream"],
  ["Vanilla Cooking Oil", "bottle", "pantry"], ["Coffee Ice Cream", "pint", "icecream"],
  ["Milk Chocolate Bar", "bag", "candy"], ["Dark Chocolate Bar", "bag", "candy"],
  ["White Chocolate Block", "bag", "candy"], ["Chocolate Milk", "bottle", "drink"],
  ["Chocolate Protein Shake", "bottle", "drink"], ["Coconut Jelly", "jar", "pantry"],
])("keeps existing retail packaging for %s", (name, kind, category) => {
  expect(classifyProduct(name)).toMatchObject({ kind, category });
});

it("keeps perfume oils smaller than cooking oils", () => {
  const perfume = classifyProduct("Vanilla Perfume Oil 10ml");
  expect(perfume.h).toBeLessThan(0.12);
  expect(perfume.h).toBeLessThan(classifyProduct("Cooking Oil 1L").h);
});

it.each([0, 1] as const)("builds finite upright specialty meshes at detail level %s", (lod) => {
  for (const kind of ["perfumeBottle", "teaCup"] as const) {
    const geometry = createPackageGeometry(kind, lod);
    geometry.computeBoundingBox();
    const size = geometry.boundingBox!.getSize(new THREE.Vector3());
    expect(size.x).toBeCloseTo(1, 5); expect(size.y).toBeCloseTo(1, 5); expect(size.z).toBeCloseTo(1, 5);
    expect(geometry.boundingBox!.min.y).toBeCloseTo(0, 5);
    for (const name of ["position", "normal", "uv"]) {
      expect([...geometry.getAttribute(name).array].every(Number.isFinite)).toBe(true);
    }
    const uvs = geometry.getAttribute("uv");
    for (const value of uvs.array) expect(value).toBeGreaterThanOrEqual(0);
    for (const value of uvs.array) expect(value).toBeLessThanOrEqual(1);
    geometry.dispose();
  }
});

it.each([0, 1] as const)("keeps perfume caps and tea straws distinct from the package body at detail %s", (lod) => {
  for (const [kind, x, z, expected] of [["perfumeBottle", 0.4, 0.4, 0.72], ["perfumeBottle", 0, 0, 1],
    ["teaCup", 0, 0, 0.76], ["teaCup", 0.16, 0, 1]] as const) {
    const geometry = createPackageGeometry(kind, lod);
    const material = new THREE.MeshBasicMaterial();
    const mesh = new THREE.Mesh(geometry, material);
    const hits = new THREE.Raycaster(new THREE.Vector3(x, 2, z), new THREE.Vector3(0, -1, 0)).intersectObject(mesh);
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0]!.point.y).toBeCloseTo(expected, 5);
    geometry.dispose(); material.dispose();
  }
});

it.each(["Classic Pearl Milk Tea", "Rose Eau de Parfum 50ml"])("keeps %s upright without vertical stacks", (name) => {
  for (const type of ["shelf", "fridge"] as const) {
    const rack: Rack = { id: "specialty", type, design_variant: type === "fridge" ? "c" : "a", shape: [[1]], position: [2, 2], rotation: 0,
      levels: 4, dwell_min: 5, dwell_max: 30, rack_name: "Specialty", rack_desc: "", rack_decoration_desc: "", locked_faces: [],
      slots: [{ block: 0, face: "S", level: 1, items: [{ sku: "specialty", name, price: 599, promo: "" }] }] };
    const products = layoutProducts([planFixture(rack, 8, 8)], { maxRows: 3 }).products;
    expect(products.length).toBeGreaterThan(0);
    expect(new Set(products.map((product) => product.y)).size).toBe(1);
    expect(products.every((product) => !product.flat)).toBe(true);
  }
});
