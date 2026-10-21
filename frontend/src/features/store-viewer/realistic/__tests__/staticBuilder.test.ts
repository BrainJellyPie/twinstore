import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { StaticBuilder } from "../staticBuilder";

describe("manufactured fixture edges", () => {
  it("keeps metric dimensions and finite normals when rounded parts merge with flat parts", () => {
    const builder = new StaticBuilder(true);
    builder.box("metalWhite", 1, 0.025, 0.6, 0, 0.5, 0);
    builder.quad("metalWhite", 0.1, 0.1, 0, 0.5, 0);
    const geometry = builder.build().get("metalWhite")!;
    const size = geometry.boundingBox!.getSize(new THREE.Vector3());
    expect(size.x).toBeCloseTo(1, 5);
    expect(size.z).toBeCloseTo(0.6, 5);
    expect(geometry.index).not.toBeNull();
    const normals = geometry.getAttribute("normal");
    for (let i = 0; i < normals.count; i++) {
      const normal = new THREE.Vector3().fromBufferAttribute(normals, i);
      expect(normal.length()).toBeCloseTo(1, 5);
    }
    geometry.dispose();
  });

  it("preserves the low-cost geometry budget for Medium, thin sheets and store walls", () => {
    for (const [beveled, material, thickness] of [
      [false, "counterTop", 0.04], [true, "wall", 0.12], [true, "metalWhite", 0.004],
    ] as const) {
      const builder = new StaticBuilder(beveled);
      builder.box(material, 1, thickness, 1, 0, 0, 0);
      const geometry = builder.build().get(material)!;
      expect(geometry.index!.count / 3).toBe(12);
      geometry.dispose();
    }
  });

  it("fits a rounded counter into its rotated layout footprint", () => {
    const builder = new StaticBuilder(true);
    builder.setFrame(3, 4, Math.PI / 2).box("counterTop", 1.2, 0.06, 0.5, 0, 0.9, 0);
    const geometry = builder.build().get("counterTop")!;
    const bounds = geometry.boundingBox!;
    expect(bounds.getCenter(new THREE.Vector3()).toArray()).toEqual([3, expect.closeTo(0.9, 5), 4]);
    expect(bounds.getSize(new THREE.Vector3()).toArray()).toEqual([expect.closeTo(0.5, 5), expect.closeTo(0.06, 5), expect.closeTo(1.2, 5)]);
    geometry.dispose();
  });

  it("keeps plaster density and UV continuity across differently sized wall segments", () => {
    const builder = new StaticBuilder();
    builder.span("wall", 0, 0, 0, 1, 2, 0.1);
    builder.span("wall", 1, 0, 0, 4, 2, 0.1);
    const geometry = builder.build().get("wall")!;
    const positions = geometry.getAttribute("position");
    const normals = geometry.getAttribute("normal");
    const uv = geometry.getAttribute("uv");
    const front: { x: number; y: number; u: number; v: number }[] = [];
    for (let i = 0; i < positions.count; i++) {
      if (normals.getZ(i) > 0.9) front.push({ x: positions.getX(i), y: positions.getY(i), u: uv.getX(i), v: uv.getY(i) });
    }
    const seam = front.filter((vertex) => vertex.x === 1 && vertex.y === 0);
    expect(seam).toHaveLength(2);
    expect(seam[0]).toEqual(seam[1]);
    const left = front.find((vertex) => vertex.x === 0 && vertex.y === 0)!;
    const right = front.find((vertex) => vertex.x === 4 && vertex.y === 0)!;
    expect(right.u - left.u).toBeCloseTo(right.x - left.x);
    geometry.dispose();
  });
});
