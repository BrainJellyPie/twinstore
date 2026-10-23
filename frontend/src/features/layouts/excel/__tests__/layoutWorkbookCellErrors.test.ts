import { expect, it } from "vitest";
import * as XLSX from "xlsx";
import ExcelJS from "exceljs";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

const headers = ["rack_id", "block", "blocked", "face", "level", "sku", "item_name",
  "price (minor units)", "regular_price (minor units)", "promo", "image_url", "notes"];
const values = ["rack", 0, "", "North", 1, "tea", "Tea", 250, 300, "SALE", "/tea.png", ""];

function workbook(cells: Record<string, XLSX.CellObject>, origin = "A1"): ArrayBuffer {
  const sheet = XLSX.utils.aoa_to_sheet([]);
  XLSX.utils.sheet_add_aoa(sheet, [headers, values], { origin });
  Object.assign(sheet, cells);
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, sheet, "rack_layout");
  return XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

const importedColumns = headers.slice(0, -1);
it.each(importedColumns.flatMap((column, index) => [0, 7, 15, 23, 29, 36, 42, 43]
  .map((error) => ({ column, error, address: XLSX.utils.encode_cell({ r: 1, c: index }) }))))(
  "rejects spreadsheet error $error in $column instead of importing a blank", ({ error, address }) => {
    expect(() => parseLayoutWorkbook(workbook({ [address]: { t: "e", v: error } })))
      .toThrow(new RegExp(`Cell ${address} needs a valid value`));
  },
);

it.each(importedColumns.map((column, index) => ({ column, address: XLSX.utils.encode_cell({ r: 1, c: index }) })))(
  "rejects an uncached formula in $column instead of assuming its value", ({ address }) => {
    expect(() => parseLayoutWorkbook(workbook({ [address]: { t: "n", f: "1+2" } })))
      .toThrow(new RegExp(`Cell ${address} needs a valid value`));
  },
);

it.each([{ t: "e", v: 23 }, { t: "s", f: '"price"' }] satisfies XLSX.CellObject[])(
  "rejects unreadable optional headers before defaulting product prices to zero", (cell) => {
    expect(() => parseLayoutWorkbook(workbook({ H1: cell }))).toThrow(/Cell H1 needs a valid value/);
  },
);

it.each([{ t: "e", v: 23 }, { t: "n", f: "1+2" }] satisfies XLSX.CellObject[])(
  "ignores broken formulas in unrelated notes columns", (cell) => {
    expect(parseLayoutWorkbook(workbook({ L2: cell })).slots[0]).toMatchObject({ sku: "tea", price: 250 });
  },
);

it("accepts cached formulas including numeric zero and deliberately empty text", () => {
  const parsed = parseLayoutWorkbook(workbook({ F2: { t: "n", f: "0", v: 0 },
    H2: { t: "n", f: "0", v: 0 }, J2: { t: "s", f: '""', v: "" } }));
  expect(parsed.slots[0]).toMatchObject({ sku: "0", price: 0, promo: "" });
});

it.each(["A1", "C7", "AA99"])("reports the original error coordinate with headers at %s", (origin) => {
  const start = XLSX.utils.decode_cell(origin);
  const address = XLSX.utils.encode_cell({ r: start.r + 1, c: start.c + 5 });
  expect(() => parseLayoutWorkbook(workbook({ [address]: { t: "e", v: 23 } }, origin)))
    .toThrow(new RegExp(`Cell ${address} needs a valid value`));
});

it.each([null, "", " ", "\t\n"])("rejects a product with missing rack id %j instead of dropping its row", (rack) => {
  const cell: XLSX.CellObject = rack === null ? { t: "z" } : { t: "s", v: rack };
  expect(() => parseLayoutWorkbook(workbook({ A2: cell }))).toThrow(/Row 2 has a product but no rack_id/);
});

it("trims a valid rack id", () => {
  const parsed = parseLayoutWorkbook(workbook({ A2: { t: "s", v: " rack " } }));
  expect(parsed.slots[0]).toMatchObject({ rack_id: "rack", sku: "tea" });
});

it("still ignores rows with neither a rack id nor a SKU", () => {
  expect(parseLayoutWorkbook(workbook({ A2: { t: "z" }, F2: { t: "z" } })).slots).toEqual([]);
});

it.each(["B1", "C1", "J1"])("accepts an unused blank header at %s", (address) => {
  const parsed = parseLayoutWorkbook(workbook({ [address]: { t: "z" } }));
  expect(parsed.slots[0]).toMatchObject({ sku: "tea", price: 250 });
});

it.each(["#SPILL!", "#CALC!", "#BLOCKED!", "#UNKNOWN!"].flatMap((error) =>
  ["F2", "H2", "H1"].map((address) => ({ error, address }))))(
  "rejects newer spreadsheet error $error at $address without a SheetJS numeric error code", async ({ error, address }) => {
    const book = new ExcelJS.Workbook();
    const sheet = book.addWorksheet("rack_layout");
    sheet.addRows([headers, values]);
    // ExcelJS can serialize newer Excel errors not yet listed in its type union.
    sheet.getCell(address).value = { error: error as ExcelJS.CellErrorValue["error"] };
    const buffer = new Uint8Array(await book.xlsx.writeBuffer()).buffer;
    expect(() => parseLayoutWorkbook(buffer)).toThrow(new RegExp(`Cell ${address} needs a valid value`));
  },
);
