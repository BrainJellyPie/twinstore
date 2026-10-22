import { describe, expect, it } from "vitest";
import * as THREE from "three";
import type { Rack, Slot } from "@/shared/types/domain";
import { planFixture } from "../fixtureSpecs";
import { layoutProducts } from "../productLayout";
import { faceCamera, isolate, productBoxes, SNAPSHOT_HEIGHT, SNAPSHOT_WIDTH } from "../shelfSnapshots";

function rack(partial: Partial<Rack> & Pick<Rack, "id" | "type">): Rack {
  return {
    shape: [[1, 1]], position: [7, 3], rotation: 0, levels: 4, dwell_min: 5, dwell_max: 30, rack_name: partial.id,
    rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [], ...partial,
  };
}
const item = (name: string) => ({ sku: name, name, price: 199, regular_price: 0, promo: "", image_url: null });
const slot = (face: Slot["face"], level: number, block: number, names: string[]): Slot => ({ block, face, level, items: names.map(item) });

describe("shelf snapshots", () => {
  const shelf = rack({
    id: "snacks", type: "shelf",
    slots: [slot("S", 4, 0, ["Crunchy Chips 8oz", "Cheese Puffs 8oz"]), slot("S", 2, 1, ["Pretzel Twists 10oz"]), slot("N", 3, 0, ["Trail Mix Nuts 6oz"])],
  });

  it("tags every package with its slot reference, on shelves and in chest bins", () => {
    const placed = isolate(shelf);
    const out = layoutProducts([planFixture(placed.rack, placed.width, placed.depth)], { maxRows: 3 });
    expect(new Set(out.products.map((p) => p.ref))).toEqual(new Set(["S:4:0:0", "S:4:0:1", "S:2:1:0", "N:3:0:0"]));
    const chest = rack({ id: "freezer", type: "fridge", design_variant: "b", slots: [slot("S", 1, 0, ["Vanilla Ice Cream Pint", "Mango Bar"])] });
    const bins = layoutProducts([planFixture(chest, 12, 12)], { maxRows: 3 });
    expect(new Set(bins.products.map((p) => p.ref))).toEqual(new Set(["S:1:0:0", "S:1:0:1"]));
  });

  it("stands the rack alone in the middle of an empty store", () => {
    const placed = isolate(shelf);
    expect(placed.rack.position).toEqual([4, 4]);
    expect(placed.width).toBe(10);
    expect(placed.depth).toBe(9);
    expect(shelf.position).toEqual([7, 3]);
  });

  it("puts the camera at eye height in front of the face and sees every product of that face only", () => {
    const placed = isolate(shelf);
    const plan = planFixture(placed.rack, placed.width, placed.depth);
    const aspect = SNAPSHOT_WIDTH / SNAPSHOT_HEIGHT;
    for (const face of ["S", "N"] as const) {
      const { position, target } = faceCamera(plan, face, aspect);
      // In front of the face: along its outward normal from the target.
      const dz = position.z - target.z;
      expect(face === "S" ? dz > 0.8 : dz < -0.8).toBe(true);
      expect(Math.abs(position.x - target.x)).toBeLessThan(1e-6);
      const camera = new THREE.PerspectiveCamera(50, aspect, 0.05, 60);
      camera.position.copy(position);
      camera.lookAt(target);
      camera.updateMatrixWorld();
      const layout = layoutProducts([plan], { maxRows: 3 });
      const boxes = productBoxes(layout.products, face, camera, SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT);
      const expected = face === "S" ? ["S:2:1:0", "S:4:0:0", "S:4:0:1"] : ["N:3:0:0"];
      expect(Object.keys(boxes).sort()).toEqual(expected);
      for (const [x1, y1, x2, y2] of Object.values(boxes).map((list) => list[0]!)) {
        expect(x1).toBeGreaterThanOrEqual(0);
        expect(y1).toBeGreaterThanOrEqual(0);
        expect(x2).toBeLessThanOrEqual(SNAPSHOT_WIDTH);
        expect(y2).toBeLessThanOrEqual(SNAPSHOT_HEIGHT);
        expect(x2 - x1).toBeGreaterThan(8);
      }
      if (face === "S") {
        // The top shelf's products sit above the second shelf's in the picture; left to right as on the shelf.
        expect(boxes["S:4:0:0"]![0]![3]).toBeLessThan(boxes["S:2:1:0"]![0]![1] + 1);
        expect(boxes["S:4:0:0"]![0]![0]).toBeLessThan(boxes["S:4:0:1"]![0]![0]);
      }
    }
  });
});

describe("snapshot crop", () => {
  it("keeps the fixture with a margin, at an aspect between 1.0 and 1.8, inside the frame", async () => {
    const { cropRegion } = await import("../shelfSnapshots");
    // A tall, narrow fridge in the middle of a 1024×768 frame: widened to a square.
    const [x1, y1, x2, y2] = cropRegion([[400, 100, 620, 700]], 1024, 768);
    expect((x2 - x1) / (y2 - y1)).toBeCloseTo(1, 1);
    expect(x1).toBeLessThan(400);
    expect(x2).toBeGreaterThan(620);
    expect(y1).toBeLessThan(100);
    // A long, low shelf: heightened to 1.8.
    const wide = cropRegion([[50, 300, 950, 420]], 1024, 768);
    expect((wide[2] - wide[0]) / (wide[3] - wide[1])).toBeCloseTo(1.8, 1);
    // Never outside the frame; nothing to keep keeps the frame.
    const edge = cropRegion([[0, 0, 1024, 768]], 1024, 768);
    expect(edge).toEqual([0, 0, 1024, 768]);
    expect(cropRegion([], 1024, 768)).toEqual([0, 0, 1024, 768]);
  });
});
