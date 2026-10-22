import { expect, it } from "vitest";
import type { EmptySpell } from "@/shared/api/client";
import { emptyAt } from "../emptyShelves";

const spell = (rack_id: string, name: string, start: number, end: number, day = 1): EmptySpell =>
  ({ day, rack_id, face: "S", sku: name.toLowerCase(), name, start, end });

it("names the products gone from each shelf at a moment of a day", () => {
  const spells = [spell("A", "Chips", 100, 200), spell("A", "Nuts", 150, 400), spell("B", "Milk", 300, 500),
    spell("A", "Chips", 100, 200, 2), spell("A", "Chips", 350, 360)];
  expect(emptyAt(spells, 1, 99)).toEqual(new Map());
  expect(emptyAt(spells, 1, 160)).toEqual(new Map([["A", ["Chips", "Nuts"]]]));
  expect(emptyAt(spells, 1, 200)).toEqual(new Map([["A", ["Nuts"]]]));   // refilled at 200
  expect(emptyAt(spells, 1, 355)).toEqual(new Map([["A", ["Nuts", "Chips"]], ["B", ["Milk"]]]));
  expect(emptyAt(spells, 2, 160)).toEqual(new Map([["A", ["Chips"]]]));
});
