import { expect, it } from "vitest";
import * as THREE from "three";
import { createCanParts, createPackageGeometry } from "../productGeometries";
import { ZONE_ACCENT } from "../atlasLayout";

it.each([0, 1] as const)("partitions every can triangle exactly once at LOD %s", lod => {
  const source = createPackageGeometry("can", lod);
  const { body, metal } = createCanParts(lod);
  try {
    const triangles = (g: THREE.BufferGeometry) => Array.from({ length: g.index!.count / 3 }, (_, i) =>
      [0, 1, 2].map(k => g.index!.getX(i * 3 + k)).join(","),
    );
    expect([...triangles(body), ...triangles(metal)].sort()).toEqual(triangles(source).sort());
    expect(body.index!.count).toBeGreaterThan(0);
    expect(metal.index!.count).toBeGreaterThan(0);
    for (const name of ["position", "normal", "uv"]) {
      expect(Array.from(body.getAttribute(name).array)).toEqual(Array.from(source.getAttribute(name).array));
      expect(Array.from(metal.getAttribute(name).array)).toEqual(Array.from(source.getAttribute(name).array));
      expect(body.getAttribute(name).array).not.toBe(metal.getAttribute(name).array);
    }
    const uv = metal.getAttribute("uv");
    for (let i = 0; i < metal.index!.count; i++) {
      const vertex = metal.index!.getX(i);
      expect(uv.getX(vertex)).toBeCloseTo(ZONE_ACCENT[0], 6);
      expect(uv.getY(vertex)).toBeCloseTo(ZONE_ACCENT[1], 6);
    }
  } finally { source.dispose(); body.dispose(); metal.dispose(); }
});

const cases = ([0, 1] as const).flatMap(lod => [0, Math.PI / 2, Math.PI, 3 * Math.PI / 2].flatMap(yaw =>
  [[0.05, 0.12, 0.05], [0.08, 0.18, 0.08], [0.1, 0.2, 0.07]].map(size => ({ lod, yaw, size })),
));

it.each(cases)("keeps the original silhouette and seams: LOD $lod, yaw $yaw, size $size", ({ lod, yaw, size }) => {
  const source = createPackageGeometry("can", lod), { body, metal } = createCanParts(lod);
  const material = new THREE.MeshBasicMaterial();
  const meshes = [source, body, metal].map(geometry => {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(2, 1, -3); mesh.rotation.y = yaw; mesh.scale.fromArray(size); mesh.updateMatrixWorld(true);
    return mesh;
  });
  try {
    const ray = new THREE.Raycaster(), matrix = meshes[0]!.matrixWorld;
    for (const height of [0.02, 0.055, 0.06, 0.5, 0.92, 0.935, 0.94, 0.97, 0.99]) {
      for (const angle of [0.13, 0.7, 1.4, 2.6, 3.7, 5.2]) {
        const x = Math.cos(angle), z = Math.sin(angle);
        ray.set(new THREE.Vector3(2 * x, height, 2 * z).applyMatrix4(matrix), new THREE.Vector3(-x, 0, -z).transformDirection(matrix));
        const original = ray.intersectObject(meshes[0]!, false)[0];
        const split = ray.intersectObjects(meshes.slice(1), false)[0];
        expect(original).toBeDefined();
        expect(split).toBeDefined();
        expect(split!.distance).toBeCloseTo(original!.distance, 7);
      }
    }
    // A ray from above must reach the metallic lid, not an overlapping body face.
    ray.set(new THREE.Vector3(0.1, 2, 0.1).applyMatrix4(matrix), new THREE.Vector3(0, -1, 0).transformDirection(matrix));
    expect(ray.intersectObjects(meshes.slice(1), false)[0]!.object).toBe(meshes[2]);
  } finally { source.dispose(); body.dispose(); metal.dispose(); material.dispose(); }
});
