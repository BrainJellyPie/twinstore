import { expect, it } from "vitest";
import * as THREE from "three";
import { createCanParts, createPackageGeometry } from "../productGeometries";

it("keeps the distant can simple and the detailed pull tab inside the original footprint", () => {
  const coarse = createPackageGeometry("can", 0), fine = createPackageGeometry("can", 1);
  try {
    expect(coarse.index!.count / 3).toBe(48);
    expect(fine.index!.count / 3).toBeGreaterThan(280);
    expect(fine.index!.count / 3).toBeLessThanOrEqual(700);
    fine.computeBoundingBox();
    const bounds = fine.boundingBox!;
    expect(bounds.min.y).toBe(0); expect(bounds.max.y).toBe(1);
    expect(bounds.min.x).toBeGreaterThanOrEqual(-0.5); expect(bounds.max.x).toBeLessThanOrEqual(0.5);
    expect(bounds.min.z).toBeGreaterThanOrEqual(-0.5); expect(bounds.max.z).toBeLessThanOrEqual(0.5);
    const position = fine.getAttribute("position"), normal = fine.getAttribute("normal");
    let detailVertices = 0;
    for (let i = 0; i < position.count; i++) {
      if (position.getY(i) < 0.99 || Math.abs(position.getX(i)) > 0.15 || Math.abs(position.getZ(i)) > 0.18) continue;
      expect(Math.hypot(normal.getX(i), normal.getY(i), normal.getZ(i))).toBeCloseTo(1, 5);
      detailVertices++;
    }
    expect(detailVertices).toBeGreaterThan(20);
  } finally { coarse.dispose(); fine.dispose(); }
});

const cases = [false, true].flatMap(flat => [0, Math.PI / 2, Math.PI, 3 * Math.PI / 2].flatMap(yaw =>
  [[0.05, 0.12, 0.05], [0.08, 0.18, 0.08], [0.1, 0.2, 0.07]].map(size => ({ flat, yaw, size })),
));

it.each(cases)("retains the open tab, raised rivet and closed lid: flat $flat, yaw $yaw, size $size", ({ flat, yaw, size }) => {
  const whole = createPackageGeometry("can", 1), { body, metal } = createCanParts(1), material = new THREE.MeshBasicMaterial();
  const meshes = [whole, metal].map(geometry => {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(2, 1, -3); mesh.rotation.set(flat ? Math.PI / 2 : 0, yaw, 0); mesh.scale.fromArray(size); mesh.updateMatrixWorld(true);
    return mesh;
  });
  try {
    const matrix = meshes[0]!.matrixWorld, inverse = matrix.clone().invert();
    const ray = new THREE.Raycaster();
    const heightAt = (x: number, z: number) => {
      ray.set(new THREE.Vector3(x, 2, z).applyMatrix4(matrix), new THREE.Vector3(0, -1, 0).transformDirection(matrix));
      const hits = meshes.map(mesh => ray.intersectObject(mesh, false)[0]);
      expect(hits[0]).toBeDefined(); expect(hits[1]).toBeDefined();
      expect(hits[0]!.distance).toBeCloseTo(hits[1]!.distance, 7);
      return hits[0]!.point.clone().applyMatrix4(inverse).y;
    };
    // The hole exposes the sealed lid below, rather than an opaque tab polygon.
    // Sample inside faces, away from the original lid's triangle boundaries.
    const lid = heightAt(0.007, -0.035), tab = heightAt(0.08, 0.007), rivet = heightAt(0.007, 0.1);
    expect(lid).toBeCloseTo(0.985, 6);
    for (const [x, z] of [[0.23, 0.007], [0.007, -0.23], [-0.22, 0.02]]) {
      expect(heightAt(x!, z!)).toBeCloseTo(lid, 6);
    }
    expect(tab).toBeGreaterThan(0.996); expect(tab).toBeLessThan(1);
    expect(rivet).toBeGreaterThan(tab); expect(rivet).toBeLessThan(1);
  } finally { whole.dispose(); body.dispose(); metal.dispose(); material.dispose(); }
});
