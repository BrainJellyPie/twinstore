import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import * as XLSX from "xlsx";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";
import { extractSkuImages } from "../extractSkuImages";

function fixture(name: string): ArrayBuffer {
  return new Uint8Array(readFileSync(new URL(`./fixtures/${name}.xlsx`, import.meta.url))).buffer;
}

it.each(["inflated-dimension", "understated-dimension"])("imports all actual cells with %s metadata", async (name) => {
  const buffer = fixture(name);
  const parsed = parseLayoutWorkbook(buffer);
  expect(parsed.slots).toEqual([{ rack_id: "rack", block: 0, face: "N", level: 1,
    sku: "tea", name: "", price: 0, regular_price: 0, promo: "", image_url: null }]);
  expect([...parsed.skuByRow]).toEqual([[2, "tea"]]);
  expect(await extractSkuImages(buffer, parsed.skuByRow)).toEqual({});
});

it("rejects actual distant products without silently truncating them", () => {
  expect(() => parseLayoutWorkbook(fixture("distant-product"))).toThrow(UserMessageError);
  expect(() => parseLayoutWorkbook(fixture("distant-product"))).toThrow(/too many cells/);
});

function workbook(rows: unknown[][], origin?: string): ArrayBuffer {
  const sheet = XLSX.utils.aoa_to_sheet([]);
  XLSX.utils.sheet_add_aoa(sheet, rows, origin ? { origin } : {});
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, sheet, "rack_layout");
  return XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

it.each(["A1", "C7", "AA99"])("preserves original rows for SKU images at %s with blank rows", (origin) => {
  const buffer = workbook([["rack_id", "face", "level", "sku"], [],
    ["rack", "North", 1, "tea"], [], ["rack", "South", 2, "coffee"]], origin);
  const parsed = parseLayoutWorkbook(buffer);
  const firstRow = XLSX.utils.decode_cell(origin).r + 3;
  expect(parsed.slots.map((row) => row.sku)).toEqual(["tea", "coffee"]);
  expect([...parsed.skuByRow]).toEqual([[firstRow, "tea"], [firstRow + 2, "coffee"]]);
});

it("accepts 50,000 placements with all supported template columns", () => {
  const headers = ["rack_id", "block", "blocked", "face", "level", "sku", "item_name",
    "price (minor units)", "regular_price (minor units)", "promo", "image_url"];
  const rows = Array.from({ length: 50_000 }, (_, index) => ["rack", 0, "", "North", 1,
    `tea-${index % 5000}`, "Tea", 250, 300, "SALE", ""]);
  const parsed = parseLayoutWorkbook(workbook([headers, ...rows]));
  expect(parsed.slots).toHaveLength(50_000);
  expect(parsed.slots[49_999]).toMatchObject({ sku: "tea-4999", price: 250, regular_price: 300 });
  expect(parsed.skuByRow.get(50_001)).toBe("tea-4999");
}, 15_000);

it.each([{ rows: [] }, { rows: [["rack_id", "face", "level"]] }])("still rejects a sheet without required columns", ({ rows }) => {
  expect(() => parseLayoutWorkbook(workbook(rows))).toThrow(/Missing required columns/);
});
