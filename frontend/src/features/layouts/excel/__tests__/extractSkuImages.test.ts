import ExcelJS from "exceljs";
import { expect, it } from "vitest";
import { extractSkuImages } from "../extractSkuImages";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aN1EAAAAASUVORK5CYII=";

async function workbook(value: ExcelJS.CellValue, header: ExcelJS.CellValue = "sku") {
  const book = new ExcelJS.Workbook();
  const sheet = book.addWorksheet("rack_layout");
  sheet.addRow(["rack_id", "face", "level", header, "item_name", "price"]);
  sheet.addRow(["rack", "North", 1, value, "Tea", 100]);
  const id = book.addImage({ base64: png, extension: "png" });
  sheet.addImage(id, { tl: { col: 6, row: 1 }, ext: { width: 20, height: 20 } });
  return new Uint8Array(await book.xlsx.writeBuffer()).buffer;
}

it.each<ExcelJS.CellValue>([
  "tea", " tea ", "00123", 0, 12, true, "__proto__", "constructor", "toString",
  { formula: '"00123"', result: "00123" },
  { formula: "1+2", result: 3 },
  { richText: [{ text: "茶" }, { text: "_한글" }] },
  { text: "tea", hyperlink: "https://example.test/tea" },
  new Date("2025-01-01T00:00:00.000Z"),
])("matches the product importer for SKU cell %j", async (value) => {
  const buffer = await workbook(value);
  const parsed = parseLayoutWorkbook(buffer);
  const images = await extractSkuImages(buffer, parsed.skuByRow);
  expect(Object.keys(images)).toEqual([parsed.slots[0]?.sku.trim()]);
  expect(Object.values(images)[0]?.bytes).toEqual(new Uint8Array(Buffer.from(png, "base64")));
});

it.each<ExcelJS.CellValue>([" SKU ", "Sku", { richText: [{ text: " SKU " }] }])(
  "accepts the same normalized header as the product importer: %j", async (header) => {
    const buffer = await workbook("tea", header);
    const parsed = parseLayoutWorkbook(buffer);
    expect(Object.keys(await extractSkuImages(buffer, parsed.skuByRow))).toEqual(["tea"]);
  },
);

it.each([1, 3, 7])("keeps photos on their products across sparse rows spaced %i apart", async (gap) => {
  const book = new ExcelJS.Workbook();
  const sheet = book.addWorksheet("rack_layout");
  // Leading blank rows and gaps must not renumber the image anchors.
  sheet.getRow(3).values = ["rack_id", "face", "level", " SKU ", "item_name", "price"];
  const expected = new Map<string, Uint8Array>();
  for (let i = 0; i < 32; i += 1) {
    const sku = `茶_${String(i).padStart(4, "0")}`;
    const value: ExcelJS.CellValue = i % 3 === 0 ? { formula: `"${sku}"`, result: sku }
      : i % 3 === 1 ? { richText: [{ text: "茶_" }, { text: String(i).padStart(4, "0") }] }
      : { text: sku, hyperlink: `https://example.test/${i}` };
    const row = 4 + i * gap;
    sheet.getRow(row).values = ["rack", "North", 1, value, "Tea", 100];
    const bytes = Buffer.concat([Buffer.from(png, "base64"), Buffer.from([i])]);
    const id = book.addImage({ base64: bytes.toString("base64"), extension: "png" });
    sheet.addImage(id, { tl: { col: 6, row: row - 1 }, ext: { width: 20, height: 20 } });
    expected.set(sku, new Uint8Array(bytes));
  }
  const buffer = new Uint8Array(await book.xlsx.writeBuffer()).buffer;
  const parsed = parseLayoutWorkbook(buffer);
  expect(parsed.slots.map((slot) => slot.sku)).toEqual([...expected.keys()]);
  const images = await extractSkuImages(buffer, parsed.skuByRow);
  expect(Object.keys(images)).toEqual([...expected.keys()]);
  for (const [sku, bytes] of expected) expect(images[sku]?.bytes).toEqual(bytes);
});

it("retains the first image for repeated SKUs and the empty-row anchor fallback", async () => {
  const book = new ExcelJS.Workbook();
  const sheet = book.addWorksheet("rack_layout");
  sheet.addRow(["rack_id", "face", "level", "sku", "item_name", "price"]);
  sheet.getRow(3).values = ["rack", "North", 1, "tea", "Tea", 100];
  sheet.getRow(5).values = ["rack", "South", 1, { formula: '"tea"', result: "tea" }, "Tea", 100];
  for (const row of [5, 2]) {
    const bytes = Buffer.concat([Buffer.from(png, "base64"), Buffer.from([row])]);
    const id = book.addImage({ base64: bytes.toString("base64"), extension: "png" });
    sheet.addImage(id, { tl: { col: 6, row: row - 1 }, ext: { width: 20, height: 20 } });
  }
  const buffer = new Uint8Array(await book.xlsx.writeBuffer()).buffer;
  const parsed = parseLayoutWorkbook(buffer);
  const images = await extractSkuImages(buffer, parsed.skuByRow);
  expect(Object.keys(images)).toEqual(["tea"]);
  expect(images.tea?.bytes).toEqual(new Uint8Array(Buffer.concat([Buffer.from(png, "base64"), Buffer.from([2])])));
});

it.each<ExcelJS.CellValue>([null, "", "   ", { formula: '""', result: "" }])(
  "does not invent a SKU for an empty cell %j", async (value) => {
    const buffer = await workbook(value);
    const parsed = parseLayoutWorkbook(buffer);
    expect(Object.keys(await extractSkuImages(buffer, parsed.skuByRow))).toEqual([]);
  },
);
