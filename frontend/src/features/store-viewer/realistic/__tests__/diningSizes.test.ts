import { expect, it } from "vitest";
import type { Rack } from "@/shared/types/domain";
import { rackDiningSeats } from "@/shared/utils/dining";
import { diningTableParts } from "../diningTable";
import { frameFor, frameToWorld, planFixture } from "../fixtureSpecs";

it.each([2, 4, 6])("shows %s chairs inside the floor obstacle at every rotation", (seats) => {
  for (const rotation of [0, 90, 180, 270] as const) {
    const rack: Rack = { id: "table", type: "table", shape: Array.from({ length: 2 }, () => Array<number>(seats / 2).fill(1)),
      position: [3, 4], rotation, levels: 1, dwell_min: 0, dwell_max: 0, rack_name: "Dining", rack_desc: "",
      rack_decoration_desc: "", locked_faces: [], slots: [] };
    expect(rackDiningSeats(rack)).toBe(seats);
    const classic = diningTableParts(seats / 2, 2);
    const plan = planFixture(rack, 12, 12);
    const ns = plan.front === "N" || plan.front === "S";
    const frame = frameFor(plan, ns ? plan.fp.d : plan.fp.w, "center");
    const realistic = diningTableParts(frame.width, frame.depth);
    for (const parts of [classic, realistic]) {
      expect(parts.filter((part) => part.material === "wood" && part.position[1] === 0.43)).toHaveLength(seats);
      expect(parts).toHaveLength(5 + 6 * seats);
    }
    for (const part of realistic) {
      expect(part.position[1] - part.size[1] / 2).toBeGreaterThanOrEqual(0);
      for (const sideX of [-1, 1]) for (const sideZ of [-1, 1]) {
        const [x, z] = frameToWorld(frame, part.position[0] + sideX * part.size[0] / 2, part.position[2] + sideZ * part.size[2] / 2);
        expect(Math.abs(x - plan.fp.cx)).toBeLessThanOrEqual(plan.fp.w / 2);
        expect(Math.abs(z - plan.fp.cz)).toBeLessThanOrEqual(plan.fp.d / 2);
      }
    }
  }
});

it("counts no seats on small legacy tables or retail fixtures", () => {
  expect(rackDiningSeats({ type: "table", shape: [[1]] })).toBe(0);
  expect(rackDiningSeats({ type: "table", shape: [[1, 1, 1]] })).toBe(0);
  expect(rackDiningSeats({ type: "shelf", shape: [[1, 1], [1, 1]] })).toBe(0);
  expect(diningTableParts(1, 1)).toHaveLength(5);
});
