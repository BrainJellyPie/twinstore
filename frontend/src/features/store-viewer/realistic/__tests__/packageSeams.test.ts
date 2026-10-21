import { expect, it } from "vitest";
import * as THREE from "three";
import { createPackageGeometry } from "../productGeometries";
import { LABEL_U0 } from "../atlasLayout";

const kinds = ["bottle", "can", "jar", "tube", "cup", "pint"] as const;
const cases = kinds.flatMap(kind => ([0, 1] as const).map(lod => ({ kind, lod })));

it.each(cases)("keeps lighting continuous across the $kind label wrap at LOD $lod", ({ kind, lod }) => {
  const geometry = createPackageGeometry(kind, lod);
  try {
    const position = geometry.getAttribute("position"), normal = geometry.getAttribute("normal"), uv = geometry.getAttribute("uv");
    let pairs = 0;
    for (let a = 0; a < position.count; a++) {
      if (Math.abs(uv.getX(a) - LABEL_U0) > 1e-6) continue;
      for (let b = 0; b < position.count; b++) {
        if (uv.getX(b) < 0.98 || Math.abs(uv.getY(a) - uv.getY(b)) > 1e-6) continue;
        const pa = new THREE.Vector3().fromBufferAttribute(position, a), pb = new THREE.Vector3().fromBufferAttribute(position, b);
        if (pa.distanceTo(pb) > 1e-6) continue;
        const na = new THREE.Vector3().fromBufferAttribute(normal, a), nb = new THREE.Vector3().fromBufferAttribute(normal, b);
        expect(na.distanceTo(nb)).toBeLessThan(1e-6);
        expect(na.length()).toBeCloseTo(1, 6);
        // The two label edges remain separate UV vertices, preserving the print.
        expect(Math.abs(uv.getX(a) - uv.getX(b))).toBeGreaterThan(0.8);
        pairs++;
      }
    }
    expect(pairs).toBeGreaterThanOrEqual(2);
  } finally { geometry.dispose(); }
});
