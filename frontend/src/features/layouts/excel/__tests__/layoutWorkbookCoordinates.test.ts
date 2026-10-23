import { expect, it } from "vitest";
import * as XLSX from "xlsx";

import type { Rack, Store } from "@/shared/types/domain";
import { buildLayoutWorkbook } from "../buildLayoutWorkbook";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

function rack(id: string, type: Rack["type"] = "shelf"): Rack {
  return { id, type, shape: [[1]], position: [2, 2], rotation: 0, levels: 4,
    dwell_min: 2, dwell_max: 30, rack_name: id, rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [] };
}

function store(racks: Rack[]): Store {
  return { id: "s", name: "Store", type: "cafe", currency: "USD", grid_size: [12, 12], weekly_schedule: [], racks };
}

it("does not export furniture or passthrough cells as product slots", async () => {
  const racks = [rack("shelf"), rack("fridge", "fridge"), rack("counter", "counter"),
    rack("table", "table"), rack("entrance", "entrance"), rack("exit", "exit")];
  const parsed = parseLayoutWorkbook(await buildLayoutWorkbook({ store: store(racks), blocked: [] }));
  expect(new Set(parsed.slots.map((row) => row.rack_id))).toEqual(new Set(["shelf", "fridge", "counter"]));
});

it.each([0, 90, 180, 270] as const)("retains both blocks and only exposed faces at rotation %s", async (rotation) => {
  const shelf = rack("long");
  shelf.shape = [[1, 1]];
  shelf.rotation = rotation;
  const expected = rotation % 180 === 0 ? [["N", "S", "W"], ["N", "S", "E"]] : [["N", "E", "W"], ["S", "E", "W"]];
  shelf.slots = [0, 1].map((block) => ({ block, face: "W", level: 2,
    items: [{ sku: `tea${block}`, name: `Tea ${block}`, price: 250, regular_price: 500, promo: "SALE" }] }));
  // Give each block a valid outward face independent of the rack's rotation.
  shelf.slots[1]!.face = rotation % 180 === 0 ? "E" : "W";
  const parsed = parseLayoutWorkbook(await buildLayoutWorkbook({ store: store([shelf]), blocked: [] }));
  expect(parsed.slots).toHaveLength(24);
  for (const block of [0, 1]) {
    expect(new Set(parsed.slots.filter((row) => row.block === block).map((row) => row.face))).toEqual(new Set(expected[block]));
    expect(parsed.slots.find((row) => row.sku === `tea${block}`)).toMatchObject({ block, price: 250, regular_price: 500 });
  }
});

it("keeps blocked cells visible in the workbook but omits their empty upload rows", async () => {
  const buffer = await buildLayoutWorkbook({ store: store([rack("shelf")]),
    blocked: [{ rack_id: "shelf", block: 0, face: "S", reason: "blocked" }] });
  const book = XLSX.read(buffer, { type: "array" });
  const rows = XLSX.utils.sheet_to_json<{ blocked: string }>(book.Sheets.rack_layout!);
  expect(rows.filter((row) => row.blocked === "blocked")).toHaveLength(4);
  const parsed = parseLayoutWorkbook(buffer);
  expect(parsed.slots).toHaveLength(12);
  expect(parsed.slots.every((row) => row.face !== "S")).toBe(true);
});

it("keeps user-entered products on a blocked row for explicit server validation", () => {
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
    ["rack_id", "block", "face", "blocked", "level", "sku"],
    ["rack", 1, "North", "blocked", 1, "tea"],
    ["rack", 1, "South", " BLOCKED ", 1, ""],
  ]), "rack_layout");
  const parsed = parseLayoutWorkbook(XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer);
  expect(parsed.slots).toHaveLength(1);
  expect(parsed.slots[0]).toMatchObject({ block: 1, sku: "tea" });
});

it.each([-1, 0.5, "invalid", "Infinity", true, Number.MAX_SAFE_INTEGER + 1])("rejects invalid block %s instead of moving products", (block) => {
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
    ["rack_id", "block", "face", "level", "sku"], ["rack", block, "North", 1, "tea"],
  ]), "rack_layout");
  expect(() => parseLayoutWorkbook(XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer)).toThrow(/block/i);
});
