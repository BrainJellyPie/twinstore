import { expect, it } from "vitest";
import * as XLSX from "xlsx";
import type { Store } from "@/shared/types/domain";
import { buildLayoutWorkbook } from "../buildLayoutWorkbook";
import { parseLayoutWorkbook } from "../parseLayoutWorkbook";

it.each([null, undefined, "/api/projects/p/product-photo-files/" + "a".repeat(64),
  "/api/projects/p/images?sku=%EC%B0%A8%2Ftea&v=abc", "/api/projects/p/lab/packages/pkg_tea"])(
  "retains saved image reference %s in hidden workbook metadata", async (image_url) => {
    const store: Store = { id: "s", name: "Store", type: "cafe", grid_size: [8, 8], weekly_schedule: [], racks: [
      { id: "shelf", type: "shelf", shape: [[1]], position: [2, 2], rotation: 0, levels: 4, dwell_min: 2, dwell_max: 30,
        rack_name: "Tea", rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [
          { block: 0, face: "N", level: 1, items: [{ sku: "tea", name: "Tea", price: 100, promo: "", image_url }] }] },
    ] };
    const buffer = await buildLayoutWorkbook({ store, blocked: [] });
    const book = XLSX.read(buffer, { type: "array", cellStyles: true });
    const sheet = book.Sheets.rack_layout!;
    const header = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1 })[0]!;
    expect(header).toContain("image_url");
    expect(sheet["!cols"]?.[header.indexOf("image_url")]?.hidden).toBe(true);
    expect(parseLayoutWorkbook(buffer).slots.find((row) => row.sku === "tea")).toMatchObject({ image_url: image_url ?? null });
  },
);

it.each([true, 123])("rejects malformed image metadata (%s)", (image_url) => {
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet([
    ["rack_id", "face", "level", "sku", "image_url"], ["shelf", "North", 1, "tea", image_url],
  ]), "rack_layout");
  expect(() => parseLayoutWorkbook(XLSX.write(book, { type: "array", bookType: "xlsx" }) as ArrayBuffer)).toThrow(/image/i);
});
