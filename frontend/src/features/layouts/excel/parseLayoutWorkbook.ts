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
  promo?: unknown;
}

function normalizeKeys(row: Record<string, unknown>): RawRow {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) out[k.toLowerCase()] = v;
  return out as RawRow;
}

function toIntPrice(raw: unknown): number {
  if (raw === null || raw === undefined || raw === "") return 0;
  const n = typeof raw === "number" || typeof raw === "string" ? Number(raw) : NaN;
  if (!Number.isSafeInteger(n) || n < 0) {
    throw new Error(`Invalid price: ${String(raw)}. Enter a nonnegative whole number in the layout currency's minor units.`);
  }
  return n;
}

export function parseLayoutWorkbook(buffer: ArrayBuffer): ParsedLayout {
  const wb = XLSX.read(buffer, { type: "array" });
  const layoutSheet = wb.Sheets["rack_layout"];
  if (!layoutSheet) {
    throw new Error("rack_layout sheet not found");
  }

  const rows = XLSX.utils
    .sheet_to_json<Record<string, unknown>>(layoutSheet, { defval: "" })
    .map(normalizeKeys)
    .filter((r) => r.rack_id);

  const slots: SlotRow[] = rows.map((r) => ({
    rack_id: String(r.rack_id),
    // The grid editor only creates 1×1 racks, so block index is always 0.
    block: 0,
    face: parseFace(String(r.face)),
    level: Number(r.level),
    sku: r.sku ? String(r.sku) : "",
    name: r.item_name ? String(r.item_name) : "",
    price: toIntPrice(r["price (minor units)"] ?? r["price (cents)"] ?? r.price),
    promo: r.promo ? String(r.promo) : "",
  }));

  return { slots };
}
