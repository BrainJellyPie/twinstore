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

  it.each([0, Math.PI / 2, Math.PI, 3 * Math.PI / 2].flatMap(yaw => [
    { part: "monitor", w: 0.3, h: 0.21, d: 0.03, tilt: -0.25 },
    { part: "base", w: 0.36, h: 0.1, d: 0.34, tilt: 0 },
    { part: "customer display", w: 0.13, h: 0.08, d: 0.02, tilt: 0.2 },
    { part: "card reader", w: 0.08, h: 0.04, d: 0.14, tilt: 0.35 },
    { part: "printer", w: 0.12, h: 0.1, d: 0.14, tilt: 0 },
  ].map(part => ({ yaw, ...part }))))("rounds the $part at yaw $yaw within its authored footprint", ({ yaw, w, h, d, tilt }) => {
    const build = (rounded: boolean) => {
      const builder = new StaticBuilder(rounded);
      builder.setFrame(3, -2, yaw).box("black", w, h, d, 0.1, 0.9, 0.2, tilt);
      return builder.build().get("black")!;
    };
    const rounded = build(true), plain = build(false);
    expect(plain.index!.count / 3).toBe(12);
    expect(rounded.index!.count / 3).toBeGreaterThan(12);
    expect(rounded.index!.count / 3).toBeLessThanOrEqual(108);
    const expected = plain.boundingBox!.clone().expandByScalar(0.00001);
    expect(expected.containsBox(rounded.boundingBox!)).toBe(true);
    const center = rounded.boundingBox!.getCenter(new THREE.Vector3());
    expect(center.distanceTo(plain.boundingBox!.getCenter(new THREE.Vector3()))).toBeLessThan(0.00001);
    const normal = rounded.getAttribute("normal");
    let maxError = 0;
    for (let i = 0; i < normal.count; i++) maxError = Math.max(maxError, Math.abs(Math.hypot(normal.getX(i), normal.getY(i), normal.getZ(i)) - 1));
    expect(maxError).toBeLessThan(0.00001);
    rounded.dispose();
    plain.dispose();
  });

  it("merges rounded hardware with thin refrigerator vents without expanding the vents", () => {
    const builder = new StaticBuilder(true);
    for (let i = 0; i < 6; i++) builder.box("black", 0.68, 0.005, 0.002, 0, i * 0.014, 0);
    builder.box("black", 0.12, 0.1, 0.14, 0, 0.8, 0);
    const geometry = builder.build().get("black")!;
    expect(geometry.index!.count / 3).toBe(6 * 12 + 108);
    expect(Array.from(geometry.getAttribute("position").array).every(Number.isFinite)).toBe(true);
    expect(Array.from(geometry.getAttribute("uv").array).every(Number.isFinite)).toBe(true);
    geometry.dispose();
  });

  it.each(["wall", "metalGrey", "aluminum"] as const)("keeps %s density and UV continuity across differently sized segments", (material) => {
    const builder = new StaticBuilder();
    builder.span(material, 0, 0, 0, 1, 2, 0.1);
    builder.span(material, 1, 0, 0, 4, 2, 0.1);
    const geometry = builder.build().get(material)!;
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

  it("keeps paving stones at the same scale on long and rotated storefronts", () => {
    for (const yaw of [0, Math.PI / 2]) {
      const builder = new StaticBuilder();
      builder.setFrame(3, -2, yaw).box("pavement", 8, 0.04, 1.7, 0, 0, 0);
      const geometry = builder.build().get("pavement")!;
      const positions = geometry.getAttribute("position");
      const normals = geometry.getAttribute("normal");
      const uv = geometry.getAttribute("uv");
      const top = Array.from({ length: positions.count }, (_, i) => i).filter((i) => normals.getY(i) > 0.9);
      const first = top[0]!;
      for (const i of top.slice(1)) {
        const metresInWorld = Math.hypot(positions.getX(i) - positions.getX(first), positions.getZ(i) - positions.getZ(first));
        const uvDistance = Math.hypot(uv.getX(i) - uv.getX(first), uv.getY(i) - uv.getY(first));
        expect(uvDistance).toBeCloseTo(metresInWorld, 5);
      }
      geometry.dispose();
    }
  });

  it.each([false, true].flatMap(beveled => [0, Math.PI / 4, Math.PI / 2, Math.PI].flatMap(yaw =>
    [0.2, 1, 8].map(width => ({ beveled, yaw, width })),
  )))("preserves stone texel density for width $width, yaw $yaw, bevel $beveled", ({ beveled, yaw, width }) => {
    const builder = new StaticBuilder(beveled);
    builder.setFrame(-3, 7, yaw).box("counterTop", width, 0.04, 0.6, 0, 0.9, 0);
    const geometry = builder.build().get("counterTop")!;
    const positions = geometry.getAttribute("position"), normals = geometry.getAttribute("normal"), uv = geometry.getAttribute("uv");
    expect(Array.from(uv.array).every(Number.isFinite)).toBe(true);
    const top = Array.from({ length: positions.count }, (_, i) => i).filter(i => normals.getY(i) > 0.999);
    expect(top.length).toBeGreaterThanOrEqual(4);
    const first = top[0]!;
    for (const i of top.slice(1)) {
      const distance = Math.hypot(positions.getX(i) - positions.getX(first), positions.getZ(i) - positions.getZ(first));
      const uvDistance = Math.hypot(uv.getX(i) - uv.getX(first), uv.getY(i) - uv.getY(first));
      expect(uvDistance).toBeCloseTo(distance, 5);
    }
    geometry.dispose();
  });
});
