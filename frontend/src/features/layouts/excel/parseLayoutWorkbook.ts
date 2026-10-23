import * as XLSX from "xlsx";
import type { SlotRow } from "@/shared/types/domain";
import { parseFace } from "./faceMap";

export interface ParsedLayout {
  slots: SlotRow[];
}

interface RawRow {
  rack_id?: unknown;
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

export function parseLayoutWorkbook(buffer: ArrayBuffer): ParsedLayout {
  const wb = XLSX.read(buffer, { type: "array" });
  const layoutSheet = wb.Sheets["rack_layout"];
  if (!layoutSheet) {
    throw new Error("rack_layout sheet not found");
  }
  const header = XLSX.utils.sheet_to_json<unknown[]>(layoutSheet, { header: 1 })[0] ?? [];
  const columns = new Set(header.map((value) => String(value).trim().toLowerCase()));
  const missing = ["rack_id", "face", "level", "sku"].filter((column) => !columns.has(column));
  if (missing.length > 0) throw new Error(`Missing required columns: ${missing.join(", ")}`);

  const rows = XLSX.utils
    .sheet_to_json<Record<string, unknown>>(layoutSheet, { defval: "" })
    .map(normalizeKeys)
    .filter((r) => r.rack_id !== undefined && r.rack_id !== null && r.rack_id !== "");

  const slots: SlotRow[] = rows.map((r) => ({
    rack_id: String(r.rack_id),
    // The grid editor only creates 1×1 racks, so block index is always 0.
    block: 0,
    face: parseFace(String(r.face)),
    level: Number(r.level),
    sku: r.sku == null ? "" : String(r.sku),
    name: r.item_name == null ? "" : String(r.item_name),
    price: toIntPrice(r["price (minor units)"] ?? r["price (cents)"] ?? r.price),
    regular_price: toIntPrice(r["regular_price (minor units)"] ?? r["regular_price (cents)"] ?? r.regular_price, "regular price"),
    promo: r.promo == null ? "" : String(r.promo),
  }));

  return { slots };
}
