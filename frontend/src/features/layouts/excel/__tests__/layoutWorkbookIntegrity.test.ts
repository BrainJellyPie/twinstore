import { expect, it } from "vitest";
import * as XLSX from "xlsx";

import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

function workbook(rows: unknown[][]) {
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet(rows), "rack_layout");
  return XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

const headers = ["rack_id", "face", "level", "sku", "item_name", "price", "promo"];

it("preserves numeric zero product identifiers instead of treating the item as deleted", () => {
  const parsed = parseLayoutWorkbook(workbook([headers, ["rack", "North", 1, 0, 0, 0, 0]]));
  expect(parsed.slots[0]).toMatchObject({ sku: "0", name: "0", price: 0, promo: "0" });
});

it.each(["rack_id", "sku"])("rejects a missing %s column before it can clear saved products", (missing) => {
  const column = headers.indexOf(missing);
  const rows = [headers, ["rack", "North", 1, "tea", "Tea", 250, ""]].map((row) => row.filter((_, i) => i !== column));
  expect(() => parseLayoutWorkbook(workbook(rows))).toThrow(new RegExp(`Missing.*${missing}`));
});

it("reads column names with surrounding spaces and mixed case", () => {
  const parsed = parseLayoutWorkbook(workbook([
    [" Rack_ID ", "FACE", "level", " SKU ", "item_name", "price"],
    ["rack", "North", 1, "tea", "Tea", 250],
  ]));
  expect(parsed.slots).toHaveLength(1);
  expect(parsed.slots[0]).toMatchObject({ rack_id: "rack", sku: "tea", price: 250 });
});

it("allows an intentionally empty template with the required columns", () => {
  expect(parseLayoutWorkbook(workbook([headers])).slots).toEqual([]);
});
