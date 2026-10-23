import { expect, it } from "vitest";
import * as XLSX from "xlsx";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

function workbook(headers: string[], values: unknown[]): ArrayBuffer {
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([headers, values]), "rack_layout");
  return XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
}

const headers = ["rack_id", "block", "blocked", "face", "level", "sku", "item_name",
  "price", "regular_price", "promo", "image_url"];
const values = ["rack", 0, "", "North", 1, "tea", "Tea", 250, 300, "SALE", "/tea.png"];

it.each(headers.flatMap((column) => [column, column.toUpperCase(), ` ${column} `]))(
  "rejects duplicated semantic column %s before it can overwrite or clear a product", (column) => {
    expect(() => parseLayoutWorkbook(workbook([...headers, column], [...values, ""])))
      .toThrow(/defined more than once/);
  },
);

const priceAliases = ["price", "price (cents)", "price (minor units)"];
it.each(["", "regular_"].flatMap((prefix) => priceAliases.flatMap((first) => priceAliases
  .filter((second) => second !== first).map((second) => [prefix + first, prefix + second] as const))))(
  "rejects competing aliases %s / %s regardless of priority or column order", (first, second) => {
    expect(() => parseLayoutWorkbook(workbook(["rack_id", "face", "level", "sku", first, second],
      ["rack", "North", 1, "tea", 0, 999])))
      .toThrow(/defined more than once/);
  },
);

it("ignores repeated unknown notes columns without changing product values", () => {
  const parsed = parseLayoutWorkbook(workbook([...headers, "notes", " NOTES ", "notes"], [...values, "a", "b", "c"]));
  expect(parsed.slots[0]).toMatchObject({ sku: "tea", price: 250, regular_price: 300, image_url: "/tea.png" });
});

it.each(priceAliases)("accepts a single %s alias alongside its separate reference price", (price) => {
  const parsed = parseLayoutWorkbook(workbook([" RACK_ID ", "face", "LEVEL", "SKU", price, `regular_${price}`],
    ["rack", "North", 1, 0, 0, 100]));
  expect(parsed.slots[0]).toMatchObject({ sku: "0", price: 0, regular_price: 100 });
});

it("rejects ambiguous headers even when no product rows remain", () => {
  expect(() => parseLayoutWorkbook(workbook([...headers, "SKU"], []))).toThrow(/defined more than once/);
});
