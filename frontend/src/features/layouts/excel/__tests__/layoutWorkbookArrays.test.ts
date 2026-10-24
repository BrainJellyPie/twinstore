import { expect, it } from "vitest";
import * as XLSX from "xlsx";
import ExcelJS from "exceljs";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

const headers = ["rack_id", "face", "level", "sku", "price", "notes"];

function workbook(column: number, child: "absent" | "cached" | "zero" | "empty" = "absent", range?: string): ArrayBuffer {
  const sheet = XLSX.utils.aoa_to_sheet([
    headers, ["rack", "North", 1, "tea", 250, "note"], ["rack", "North", 2, "coffee", 300, "note"],
  ]);
  const anchor = XLSX.utils.encode_cell({ r: 1, c: column });
  const address = XLSX.utils.encode_cell({ r: 2, c: column });
  sheet[anchor] = { ...sheet[anchor], f: "A1:A2", F: range ?? `${anchor}:${address}` };
  if (child === "absent") delete sheet[address];
  if (child === "zero") sheet[address] = { t: "n", v: 0 };
  if (child === "empty") sheet[address] = { t: "s", v: "" };
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, sheet, "rack_layout");
  return XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

it.each([0, 1, 2, 3, 4])("rejects an absent array output in imported column %s", column => {
  const address = XLSX.utils.encode_cell({ r: 2, c: column });
  expect(() => parseLayoutWorkbook(workbook(column))).toThrow(`Cell ${address} needs a valid value`);
});

it.each([0, 1, 2, 3, 4])("preserves fully cached array results in column %s", column => {
  const result = parseLayoutWorkbook(workbook(column, "cached"));
  expect(result.slots.map(row => [row.sku, row.price])).toEqual([["tea", 250], ["coffee", 300]]);
  expect([...result.skuByRow]).toEqual([[2, "tea"], [3, "coffee"]]);
});

it.each(["zero", "empty"] as const)("preserves a saved %s price result", child => {
  expect(parseLayoutWorkbook(workbook(4, child)).slots[1]?.price).toBe(0);
});

it("allows an explicitly empty cached SKU result", () => {
  const result = parseLayoutWorkbook(workbook(3, "empty"));
  expect(result.slots[1]?.sku).toBe("");
  expect([...result.skuByRow]).toEqual([[2, "tea"]]);
});

it("ignores missing array output in unused notes", () => {
  expect(parseLayoutWorkbook(workbook(5)).slots).toHaveLength(2);
});

it("rejects an array tail beyond existing rows", () => {
  expect(() => parseLayoutWorkbook(workbook(3, "cached", "D2:D4"))).toThrow("Cell D4 needs a valid value");
});

it("checks a two-dimensional array beyond its anchor column", () => {
  const sheet = XLSX.read(workbook(3, "cached", "D2:E3"), { type: "array" });
  delete sheet.Sheets.rack_layout!.E3;
  const bytes = XLSX.write(sheet, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
  expect(() => parseLayoutWorkbook(bytes)).toThrow("Cell E3 needs a valid value");
});

it("bounds oversized declared array ranges before scanning them", () => {
  expect(() => parseLayoutWorkbook(workbook(3, "cached", "D2:XFD1048576"))).toThrow(/too many cells/i);
});

it.each(["D3:D2", "D3:D4", "D2:D0", "invalid"])("rejects invalid array reference %s", async ref => {
  // SheetJS's writer discards malformed array metadata, so use an independent writer.
  const book = new ExcelJS.Workbook();
  const sheet = book.addWorksheet("rack_layout");
  sheet.addRows([headers, ["rack", "North", 1, "tea", 250, "note"]]);
  // ExcelJS supports array metadata at runtime but omits it from CellFormulaValue.
  const formula = { formula: "A1:A2", result: "tea", shareType: "array", ref };
  sheet.getCell("D2").value = formula;
  const buffer = new Uint8Array(await book.xlsx.writeBuffer()).buffer;
  expect(() => parseLayoutWorkbook(buffer)).toThrow("Cell D2 needs a valid value");
});

it.each([{ t: "e", v: 23 }, { t: "z" }] as XLSX.CellObject[])("rejects unreadable array children: %o", cell => {
  const book = XLSX.read(workbook(4, "cached"), { type: "array" });
  book.Sheets.rack_layout!.E3 = cell;
  expect(() => parseLayoutWorkbook(XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer))
    .toThrow("Cell E3 needs a valid value");
});

it("rejects an uncached header array output before reading column names", () => {
  const book = XLSX.read(workbook(3, "cached"), { type: "array" });
  const sheet = book.Sheets.rack_layout!;
  sheet.A1 = { ...sheet.A1, f: "A1:F1", F: "A1:F1" };
  delete sheet.D1;
  expect(() => parseLayoutWorkbook(XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer))
    .toThrow("Cell D1 needs a valid value");
});

it.each(["A1", "C7", "AA99"])("checks absolute array references with headers at %s", async origin => {
  const start = XLSX.utils.decode_cell(origin);
  const book = new ExcelJS.Workbook();
  const sheet = book.addWorksheet("rack_layout");
  for (const [row, values] of [headers, ["rack", "North", 1, "tea", 250, "note"],
    ["rack", "North", 2, "coffee", 300, "note"]].entries()) {
    values.forEach((value, column) => { sheet.getCell(start.r + row + 1, start.c + column + 1).value = value; });
  }
  const anchor = XLSX.utils.encode_cell({ r: start.r + 1, c: start.c + 3 });
  const child = XLSX.utils.encode_cell({ r: start.r + 2, c: start.c + 3 });
  const ref = `${anchor}:${child}`.replace(/([A-Z]+)(\d+)/g, "$$$1$$$2");
  const formula = { formula: "A1:A2", result: "tea", shareType: "array", ref };
  sheet.getCell(anchor).value = formula;
  sheet.getCell(child).value = null;
  const buffer = new Uint8Array(await book.xlsx.writeBuffer()).buffer;
  expect(() => parseLayoutWorkbook(buffer)).toThrow(`Cell ${child} needs a valid value`);
});
