import { expect, it } from "vitest";
import * as XLSX from "xlsx";

import type { Store } from "@/shared/types/domain";
import { buildLayoutWorkbook } from "../buildLayoutWorkbook";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

function workbook(price: unknown) {
  const book = XLSX.utils.book_new();
  const sheet = XLSX.utils.aoa_to_sheet([
    ["rack_id", "face", "level", "sku", "item_name", "price (cents)"],
    ["rack", "North", 1, "tea", "Tea", price],
  ]);
  XLSX.utils.book_append_sheet(book, sheet, "rack_layout");
  return XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

it.each(["free", "NaN", "Infinity", "1,500", -1, 1.5, true, Number.MAX_SAFE_INTEGER + 1])(
  "rejects invalid minor-unit prices (%s) instead of saving zero or rounding", (price) => {
    expect(() => parseLayoutWorkbook(workbook(price))).toThrow(/price/i);
  },
);

it.each([[0, 0], ["0", 0], [1500, 1500], ["1500", 1500], ["", 0]])(
  "keeps valid integer prices and blank template rows (%s)", (input, expected) => {
    expect(parseLayoutWorkbook(workbook(input)).slots[0]).toMatchObject({ price: expected, regular_price: 0 });
  },
);

it.each(["regular_price (minor units)", "regular_price (cents)", " Regular_Price "])(
  "reads %s without changing zero or reference prices", (column) => {
    const book = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
      ["rack_id", "face", "level", "sku", "price", column],
      ...[0, "", 5000, "5000", Number.MAX_SAFE_INTEGER].map((price, i) => ["rack", "North", 1, `tea${i}`, 100, price]),
    ]), "rack_layout");
    const buffer = XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
    expect(parseLayoutWorkbook(buffer).slots.map((slot) => slot.regular_price)).toEqual([0, 0, 5000, 5000, Number.MAX_SAFE_INTEGER]);
  },
);

it.each(["USD", "KRW", "JPY"])("exports %s prices with an accurate unit header and preserves values on import", async (currency) => {
  const store: Store = {
    id: "store", name: "Store", type: "cafe", currency, grid_size: [8, 6], weekly_schedule: [],
    racks: [{ id: "rack", type: "shelf", shape: [[1]], position: [2, 2], rotation: 0, levels: 1,
      dwell_min: 2, dwell_max: 30, rack_name: "Tea", rack_desc: "", rack_decoration_desc: "", locked_faces: [],
      slots: [{ block: 0, face: "N", level: 1, items: [{ sku: "tea", name: "Tea", price: 2500, regular_price: 5000, promo: "" }] }] }],
  };
  const buffer = await buildLayoutWorkbook({ store, blocked: [] });
  const book = XLSX.read(buffer, { type: "array" });
  const rows = XLSX.utils.sheet_to_json<unknown[]>(book.Sheets.rack_layout!, { header: 1 });
  expect(rows[0]).toContain("price (minor units)");
  expect(rows[0]).not.toContain("price (cents)");
  expect(parseLayoutWorkbook(buffer).slots.find((slot) => slot.sku === "tea")?.price).toBe(2500);
  expect(parseLayoutWorkbook(buffer).slots.find((slot) => slot.sku === "tea")).toMatchObject({ regular_price: 5000 });
});

it.each(["free", "NaN", "Infinity", -1, 1.5, true, Number.MAX_SAFE_INTEGER + 1])(
  "rejects invalid reference prices (%s)", (price) => {
    const book = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
      ["rack_id", "face", "level", "sku", "price", "regular_price (minor units)"],
      ["rack", "North", 1, "tea", 100, price],
    ]), "rack_layout");
    const buffer = XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
    expect(() => parseLayoutWorkbook(buffer)).toThrow(/price/i);
  },
);
