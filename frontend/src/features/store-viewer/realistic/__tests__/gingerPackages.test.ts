import { expect, it } from "vitest";
import * as THREE from "three";
import { classifyProduct, productPalette } from "../productCatalog";
import { createPackageGeometry } from "../productGeometries";
import { ZONE_BODY } from "../atlasLayout";

it.each([
  "Ginger", "Ginger Root", "Ginger Roots", "Fresh Ginger", "Raw Ginger Root", "Whole Ginger",
  "Organic Whole Ginger Roots", "Ginger Each", "Ginger Root Loose", "Fresh Ginger 500g", "Ginger 1.5 kg",
  "Ginger Root .25 lb", "Ginger 0.5 lbs", "Ginger 1g", "Ginger 0.01kg", "  Organic Raw Ginger Root 1kg  ",
])("recognises %s as a whole ginger root", name => {
  const spec = classifyProduct(name);
  expect(spec.kind).toBe("ginger"); expect(classifyProduct(name.toUpperCase()).kind).toBe("ginger");
  expect(spec.w).toBeCloseTo(0.20110649); expect(spec.h).toBeCloseTo(0.05158130); expect(spec.d).toBeCloseTo(0.08397771);
});

it.each([
  "Ginger Ale", "Ginger Beer", "Ginger Tea", "Ginger Juice", "Ginger Shot", "Ginger Latte", "Ginger Kombucha",
  "Ground Ginger", "Ginger Powder", "Minced Ginger", "Ginger Paste", "Ginger Puree", "Pickled Ginger",
  "Candied Ginger", "Crystallized Ginger", "Dried Ginger", "Peeled Ginger", "Ginger Slices", "Chopped Ginger",
  "Ginger Cubes", "Frozen Ginger", "Ginger Oil", "Ginger Sauce", "Ginger Candy", "Ginger Cookies", "Gingerbread",
  "Young Ginger", "Baby Ginger", "Galangal", "Turmeric", "Ginger Plant", "Ginger Seeds", "Ginger Root Extract",
  "Ginger Root Capsules", "Ginger Root Supplement", "Ginger Candle", "Ginger Toy", "Ginger 2pk", "Ginger 2-pack",
  "Ginger Roots 3 count", "Ginger 1kg 2pk", "Ginger 0kg", "Ginger 0.00g", "Ginger -1kg", "Ginger NaN kg",
  "Ginger Infinity kg", "Ginger 1e3g", "Ginger 00.5kg", "Ginger 1..2kg", "Gingerbread Root", "Gingersnap",
])("keeps %s out of the whole-root scan", name => {
  expect(classifyProduct(name).kind).not.toBe("ginger"); expect(classifyProduct(name.toUpperCase()).kind).not.toBe("ginger");
});

it.each([0, 1] as const)("keeps a closed, beige root fallback at detail %s", detail => {
  const geometry = createPackageGeometry("ginger", detail), material = new THREE.MeshBasicMaterial();
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
    const base = productPalette("Fresh Ginger Root").base;
    const [r, g, b] = [1, 3, 5].map(offset => parseInt(base.slice(offset, offset + 2), 16));
    expect(r).toBeGreaterThan(g!); expect(g).toBeGreaterThan(b!);
  } finally { geometry.dispose(); material.dispose(); }
});
