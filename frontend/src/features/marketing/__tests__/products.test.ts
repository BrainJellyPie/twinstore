import { describe, expect, it } from "vitest";

import type { Store } from "@/shared/types/domain";

import { storeCategories, storeFixtures, storeProducts, toMinor } from "../products";

const rack = (id: string, name: string, items: [string, string, number][]) => ({
  id, type: "shelf", shape: [[0, 0]], position: [0, 0], rotation: 0, levels: 4, dwell_min: 1, dwell_max: 2,
  rack_name: name, rack_desc: "", rack_decoration_desc: "", locked_faces: [],
  slots: items.map(([sku, n, price], i) => ({ block: 0, face: "N", level: 1 + (i % 4), items: [{ sku, name: n, price, promo: "" }] })),
});

const store = {
  id: "s", name: "s", type: "cvs", grid_size: [10, 10], weekly_schedule: [],
  racks: [
    rack("r1", "Drink 1", [["A1", "Cola", 249], ["A2", "Lime", 199]]),
    rack("r2", "Drink 2", [["A1", "Cola", 249]]),
    rack("r3", "Snacks 1", [["B1", "Chips", 399]]),
  ],
} as unknown as Store;

describe("marketing products", () => {
  it("merges facings of one SKU across fixtures", () => {
    const cola = storeProducts(store).find((p) => p.sku === "A1")!;
    expect(cola.facings).toBe(2);
    expect(cola.racks).toEqual(["Drink 1", "Drink 2"]);
    expect(storeProducts(store).map((p) => p.name)).toEqual(["Chips", "Cola", "Lime"]);
  });

  it("derives categories from rack names without their number", () => {
    expect(storeCategories(store)).toEqual(["Drink", "Snacks"]);
    expect(storeFixtures(store).map((f) => f.levels)).toEqual([4, 4, 4]);
  });

  it("parses prices into minor units", () => {
    expect(toMinor("1.99", 100)).toBe(199);
    expect(toMinor("$2", 100)).toBe(200);
    expect(toMinor("1,500", 1)).toBe(1500);
    expect(toMinor("", 100)).toBeNull();
  });
});
