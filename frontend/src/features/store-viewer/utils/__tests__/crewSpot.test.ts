import { expect, it } from "vitest";
import type { CustomerResult, Rack } from "@/shared/types/domain";
import { crewSpot, shopperSides } from "../crewSpot";

const rack = (id: string, type: string, position: [number, number], shape = [[1]]): Rack =>
  ({ id, type, position, shape, rotation: 0, levels: 1, slots: [] } as unknown as Rack);
const shelf = rack("A", "shelf", [2, 2], [[1, 1]]);   // two tiles wide: centre (3, 2.5)
const till = rack("C0", "counter", [6, 6]);            // centre (6.5, 6.5)
const racks = new Map([shelf, till].map((r) => [r.id, r]));
const payer = (x: number, y: number) => ({ persona_id: "p", timeline: [{ action: "pay", target_rack: "C0", x, y }] } as unknown as CustomerResult);

it("stands at the shelf face being refilled, looking at it", () => {
  const east = crewSpot({ member: 1, kind: "refill", rackId: "A", face: "E", name: "Chips" }, racks, [till], new Map())!;
  expect(east.x).toBeCloseTo(3 + 1 + 0.45);
  expect(east.z).toBeCloseTo(2.5);
  const south = crewSpot({ member: 1, kind: "refill", rackId: "A", face: "S", name: "Chips" }, racks, [till], new Map())!;
  expect(south.x).toBeCloseTo(3);
  expect(south.z).toBeCloseTo(2.5 + 0.5 + 0.45);
  expect(crewSpot({ member: 1, kind: "refill", rackId: "gone", face: "E", name: "" }, racks, [till], new Map())).toBeNull();
});

it("puts the cashier behind the till, across from where shoppers pay", () => {
  const sides = shopperSides([till], [payer(6, 8), payer(6, 8)]);   // shoppers pay south of it (z 8.5)
  expect(sides.get("C0")![0]).toBeCloseTo(0);
  expect(sides.get("C0")![1]).toBeCloseTo(1);
  const cashier = crewSpot({ member: 0, kind: "till", rackId: "C0" }, racks, [till], sides)!;
  expect(cashier.x).toBeCloseTo(6.5);
  expect(cashier.z).toBeCloseTo(6.5 - 0.5 - 0.45);
  expect(cashier.facing).toBeCloseTo(0);   // looking +z, at the shoppers
  // Waiting for work: the cashier at their till, the others beside them.
  expect(crewSpot({ member: 0, kind: "idle" }, racks, [till], sides)).toEqual(cashier);
  const helper = crewSpot({ member: 1, kind: "idle" }, racks, [till], sides)!;
  expect(helper.x).toBeCloseTo(6.5 - 0.6);
  expect(helper.z).toBeCloseTo(cashier.z);
  expect(crewSpot({ member: 0, kind: "idle" }, racks, [], new Map())).toBeNull();
});

it("assumes shoppers pay south of a till nobody paid at", () => {
  expect(shopperSides([till], [])).toEqual(new Map([["C0", [0, 1]]]));
});
