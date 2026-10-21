import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import type { Rack } from "@/shared/types/domain";
import { buildStore } from "../buildStore";
import { COUNTER_DIMS, frameFor, planFixture } from "../fixtureSpecs";

// These tests inspect real merged geometry; no canvas or GPU is needed.
vi.mock("../canvasArt", async (importOriginal) => ({
  ...await importOriginal<typeof import("../canvasArt")>(),
  createSignAtlas: () => ({ index: new Map() }),
}));

const cases = [false, true].flatMap(beveled => ([0, 90, 180, 270] as const).flatMap(rotation =>
  [1, 2, 3].map(width => ({ beveled, rotation, width })),
));
const rackFor = (rotation: Rack["rotation"], width: number): Rack => ({
  id: "checkout", type: "counter", position: [3, 4], shape: [Array<number>(width).fill(1)],
  rotation, levels: 1, dwell_min: 0, dwell_max: 0, rack_name: "Checkout", rack_desc: "",
  rack_decoration_desc: "", locked_faces: [], slots: [],
});

function dispose(built: ReturnType<typeof buildStore>) {
  for (const geometries of [built.geometries, built.upperGeometries]) {
    for (const geometry of geometries.values()) geometry.dispose();
  }
}

describe("checkout screen mounting", () => {
  it.each(cases)("keeps every screen just outside its housing: bevel $beveled, rotation $rotation, width $width", ({ beveled, rotation, width }) => {
    const built = buildStore(12, 12, [rackFor(rotation, width)], beveled);
    const material = new THREE.MeshBasicMaterial();
    try {
      const body = new THREE.Mesh(built.geometries.get("black")!, material);
      const screen = built.geometries.get("screen")!;
      const positions = screen.getAttribute("position"), normals = screen.getAttribute("normal");
      expect(positions.count).toBe(12);
      const ray = new THREE.Raycaster();
      for (let start = 0; start < positions.count; start += 4) {
        const vertices = Array.from({ length: 4 }, (_, i) => new THREE.Vector3().fromBufferAttribute(positions, start + i));
        const normal = new THREE.Vector3().fromBufferAttribute(normals, start);
        expect(normal.length()).toBeCloseTo(1, 6);
        // Sample the face and all four near-corners, including the regions that
        // disappeared inside the housing when screen and body tilts disagreed.
        for (const u of [0.1, 0.3, 0.5, 0.7, 0.9]) for (const v of [0.1, 0.3, 0.5, 0.7, 0.9]) {
          const point = vertices[0]!.clone().lerp(vertices[1]!, u)
            .lerp(vertices[2]!.clone().lerp(vertices[3]!, u), v);
          ray.set(point.clone().addScaledVector(normal, 0.05), normal.clone().negate());
          const hit = ray.intersectObject(body, false)[0];
          expect(hit, `screen ${start / 4}, u=${u}, v=${v}`).toBeDefined();
          expect(hit!.distance, `screen ${start / 4}, u=${u}, v=${v}`).toBeCloseTo(0.051, 5);
        }
      }
    } finally {
      material.dispose();
      dispose(built);
    }
  });

  it.each(cases)("rests the tilted card reader above the countertop: bevel $beveled, rotation $rotation, width $width", ({ beveled, rotation, width }) => {
    const rack = rackFor(rotation, width);
    const built = buildStore(12, 12, [rack], beveled);
    try {
      const frame = frameFor(planFixture(rack, 12, 12), COUNTER_DIMS.depth, "center");
      const inverse = new THREE.Matrix4().makeRotationY(frame.yaw).setPosition(frame.ox, 0, frame.oz).invert();
      const positions = built.geometries.get("black")!.getAttribute("position");
      const heights: number[] = [];
      for (let i = 0; i < positions.count; i++) {
        const p = new THREE.Vector3().fromBufferAttribute(positions, i).applyMatrix4(inverse);
        if (p.x > 0.099 && p.x < 0.181 && p.z > 0.04 && p.z < 0.24 && p.y > COUNTER_DIMS.height - 0.05) heights.push(p.y);
      }
      expect(heights.length).toBeGreaterThanOrEqual(24);
      expect(Math.min(...heights)).toBeGreaterThanOrEqual(COUNTER_DIMS.height - 0.000001);
      // A bevel may lift the extreme corner slightly; the device must not float.
      expect(Math.min(...heights)).toBeLessThan(COUNTER_DIMS.height + 0.004);
    } finally {
      dispose(built);
    }
  });
});
