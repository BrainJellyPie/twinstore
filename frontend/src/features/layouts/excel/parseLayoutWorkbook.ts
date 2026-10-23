import * as XLSX from "xlsx";
import type { SlotRow } from "@/shared/types/domain";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { parseFace } from "./faceMap";

export interface ParsedLayout {
  slots: SlotRow[];
  // One-based worksheet rows, using the same SKU decoding as the slot import.
  skuByRow: ReadonlyMap<number, string>;
}

interface RawRow {
  rack_id?: unknown;
  block?: unknown;
  blocked?: unknown;
  face?: unknown;
  level?: unknown;
  sku?: unknown;
  item_name?: unknown;
  "price (minor units)"?: unknown;
  "price (cents)"?: unknown;
  price?: unknown;
  "regular_price (minor units)"?: unknown;
  "regular_price (cents)"?: unknown;
  regular_price?: unknown;
  promo?: unknown;
  image_url?: unknown;
}

function normalizeKeys(row: Record<string, unknown>): RawRow {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) out[k.trim().toLowerCase()] = v;
  return out as RawRow;
}

function toIntPrice(raw: unknown, label = "price"): number {
  if (raw === null || raw === undefined || raw === "") return 0;
  const n = typeof raw === "number" || typeof raw === "string" ? Number(raw) : NaN;
  if (!Number.isSafeInteger(n) || n < 0) {
    throw new Error(`Invalid ${label}: ${String(raw)}. Enter a nonnegative whole number in the layout currency's minor units.`);
  }
  return n;
}

function toBlock(raw: unknown): number {
  if (raw === null || raw === undefined || raw === "") return 0; // Older one-cell workbooks have no block column.
  const block = typeof raw === "number" || typeof raw === "string" ? Number(raw) : NaN;
  if (!Number.isSafeInteger(block) || block < 0) throw new Error(`Invalid block index: ${String(raw)}.`);
  return block;
}

function toImageUrl(raw: unknown): string | null {
  if (raw === null || raw === undefined || raw === "") return null;
  if (typeof raw !== "string") throw new Error("Invalid image reference in workbook metadata.");
  return raw.trim() || null;
}

export function parseLayoutWorkbook(buffer: ArrayBuffer): ParsedLayout {
  // Keep uncached formula cells: otherwise SheetJS drops them like empty cells.
  const wb = XLSX.read(buffer, { type: "array", sheetStubs: true });
  const layoutSheet = wb.Sheets["rack_layout"];
  if (!layoutSheet) {
    throw new Error("rack_layout sheet not found");
  }
  // Excel can retain an enormous dimension after rows/columns are cleared. Do
  // not iterate that rectangle, and never truncate actual product cells.
  const range: XLSX.Range = { s: { r: Infinity, c: Infinity }, e: { r: 0, c: 0 } };
  const unreadable: Array<{ address: string; r: number; c: number }> = [];
  for (const address of Object.keys(layoutSheet)) {
    if (address.startsWith("!")) continue;
    const cell: XLSX.CellObject | undefined = layoutSheet[address];
    if (!cell) continue;
    const formula = Boolean(cell.f || cell.F);
    if (!formula && cell.t !== "e" && (cell.t === "z" || cell.v == null)) continue;
    const { r, c } = XLSX.utils.decode_cell(address);
    if (cell.t === "e" || (formula && (cell.t === "z" || cell.v == null))) {
      unreadable.push({ address, r, c });
    }
    range.s.r = Math.min(range.s.r, r);
    range.s.c = Math.min(range.s.c, c);
    range.e.r = Math.max(range.e.r, r);
    range.e.c = Math.max(range.e.c, c);
  }
  if (!Number.isFinite(range.s.r)) range.s = { r: 0, c: 0 };
  // Allows 50,000 product rows with all template columns, including metadata.
  if ((range.e.r - range.s.r + 1) * (range.e.c - range.s.c + 1) > 2_000_000) {
    throw new UserMessageError("excelSheetTooWide");
  }
  layoutSheet["!ref"] = XLSX.utils.encode_range(range);
  const unreadableHeader = unreadable.find((cell) => cell.r === range.s.r);
  if (unreadableHeader) throw new UserMessageError("excelCellNeedsValue", { cell: unreadableHeader.address });
  const header = XLSX.utils.sheet_to_json<unknown[]>(layoutSheet, {
    header: 1, range: { s: range.s, e: { r: range.s.r, c: range.e.c } },
  })[0] ?? [];
  // Array.from fills sparse header positions so spacer columns stay harmless.
  const columnNames = Array.from(header, (value) => String(value ?? "").trim().toLowerCase());
  const columns = new Set(columnNames);
  const missing = ["rack_id", "face", "level", "sku"].filter((column) => !columns.has(column));
  if (missing.length > 0) throw new Error(`Missing required columns: ${missing.join(", ")}`);
  const importedFields = new Set(["rack_id", "block", "blocked", "face", "level", "sku",
    "item_name", "price", "regular_price", "promo", "image_url"]);
  const seenFields = new Set<string>();
  const importedColumns = new Set<number>();
  for (const [index, column] of columnNames.entries()) {
    const field = column.replace(/^(regular_)?price \((?:minor units|cents)\)$/, "$1price");
    if (!importedFields.has(field)) continue;
    // SheetJS renames exact duplicates while normalizeKeys collapses case/space
    // variants. Both can silently select a different value (even an empty SKU).
    if (seenFields.has(field)) throw new UserMessageError("excelDuplicateColumn", { column: field });
    seenFields.add(field);
    importedColumns.add(range.s.c + index);
  }
  const unreadableProduct = unreadable.find((cell) => importedColumns.has(cell.c));
  if (unreadableProduct) throw new UserMessageError("excelCellNeedsValue", { cell: unreadableProduct.address });

  const skuByRow = new Map<number, string>();
  const rows = XLSX.utils
    .sheet_to_json<Record<string, unknown>>(layoutSheet, { defval: "" })
    .map((row) => {
      const normalized = normalizeKeys(row);
      const sku = String(normalized.sku ?? "").trim();
      normalized.rack_id = String(normalized.rack_id ?? "").trim();
      if (sku && !normalized.rack_id) {
        throw new UserMessageError("excelProductRackMissing", {
          row: typeof row.__rowNum__ === "number" ? row.__rowNum__ + 1 : "?",
        });
      }
      // SheetJS keeps the original zero-based row even when blank rows are omitted.
      if (typeof row.__rowNum__ === "number" && sku) skuByRow.set(row.__rowNum__ + 1, sku);
      return normalized;
    })
    .filter((r) => r.rack_id !== undefined && r.rack_id !== null && r.rack_id !== "")
    .filter((r) => String(r.blocked ?? "").trim().toLowerCase() !== "blocked" || String(r.sku ?? "").trim() !== "");

  const slots: SlotRow[] = rows.map((r) => ({
    rack_id: String(r.rack_id),
    block: toBlock(r.block),
    face: parseFace(String(r.face)),
    level: Number(r.level),
    sku: r.sku == null ? "" : String(r.sku).trim(),
    name: r.item_name == null ? "" : String(r.item_name),
    price: toIntPrice(r["price (minor units)"] ?? r["price (cents)"] ?? r.price),
    regular_price: toIntPrice(r["regular_price (minor units)"] ?? r["regular_price (cents)"] ?? r.regular_price, "regular price"),
    promo: r.promo == null ? "" : String(r.promo),
    image_url: toImageUrl(r.image_url),
  }));

  return { slots, skuByRow };
}
