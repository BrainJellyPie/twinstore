// Extract worksheet image drawings from the rack_layout sheet, keyed by SKU.
// If a SKU appears in multiple rows, only the topmost (lowest row number) image is used.

import ExcelJS from "exceljs";

export interface ExtractedSkuImage {
  bytes: Uint8Array;
  // Backend (images.py::_ALLOWED_FORMATS) accepts PNG / JPEG / WEBP. ExcelJS's
  // `wb.model.media[].extension` may report "png" | "jpeg" | "gif", and Excel does
  // not store WEBP natively in xlsx — so effectively only png/jpeg pass through.
  extension: "png" | "jpeg";
}

export type ExtractedSkuImages = Record<string, ExtractedSkuImage>;

export async function extractSkuImages(
  buffer: ArrayBuffer, rowToSku: ReadonlyMap<number, string>,
): Promise<ExtractedSkuImages> {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.load(buffer);

  const ws = wb.getWorksheet("rack_layout");
  if (!ws) return {};

  const images = ws.getImages();

  const result = new Map<string, ExtractedSkuImage>();

  const sortedSkuRows = [...rowToSku.keys()].sort((a, b) => a - b);
  function findSkuForRow(row: number): string | undefined {
    if (rowToSku.has(row)) return rowToSku.get(row);
    // Images can drift across empty filler rows during round-trips. If no exact
    // match exists, fall back to the nearest SKU row at or below this one.
    for (const r of sortedSkuRows) {
      if (r >= row) return rowToSku.get(r);
    }
    return undefined;
  }

  const sortedImages = [...images]
    .filter((i) => i.range?.tl !== undefined)
    .sort((a, b) => (a.range!.tl.nativeRow - b.range!.tl.nativeRow));
  for (const img of sortedImages) {
    const row = img.range!.tl.nativeRow + 1;
    const sku = findSkuForRow(row);
    if (!sku) continue;
    if (result.has(sku)) continue;
    // ExcelJS's typed model.media has no `index` field but it exists at runtime.
    // `imageId` is typed string but may be a number at runtime — normalize with String().
    const media = wb.model.media.find(
      (m) => String((m as unknown as { index?: number | string }).index) === String(img.imageId),
    );
    if (!media) continue;
    // Backend allows PNG/JPEG/WEBP, but ExcelJS may surface GIF as well. To prevent
    // a regression where a GIF is mis-uploaded as image/png (422), skip anything
    // that isn't png/jpeg. Missing extension falls back to png — covers an older
    // ExcelJS media-format edge case.
    const rawExt = (media as { extension?: string }).extension;
    const ext: ExtractedSkuImage["extension"] | null =
      rawExt === undefined ? "png"
      : rawExt === "png" || rawExt === "jpeg" ? rawExt
      : null;
    if (ext === null) continue;
    // media.buffer is a Node Buffer at runtime — safely coerce to Uint8Array.
    const rawBuffer = (media as unknown as { buffer: ArrayBufferLike | Uint8Array }).buffer;
    const bytes =
      rawBuffer instanceof Uint8Array
        ? new Uint8Array(rawBuffer)
        : new Uint8Array(rawBuffer);
    result.set(sku, {
      bytes,
      extension: ext,
    });
  }

  return Object.fromEntries(result);
}
