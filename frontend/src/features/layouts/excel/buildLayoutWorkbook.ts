import ExcelJS from "exceljs";
import type { Store, BlockedFaceInfo, SlotItem } from "@/shared/types/domain";
import { formatFace } from "./faceMap";

export interface BuildLayoutWorkbookInput {
  store: Store;
  // Response from POST /util/blocked-faces. Each (rack_id, block, face) × level 1..levels
  // row is emitted with a "blocked" marker in the blocked column (rows aren't dropped).
  // We only need (rack_id, block, face) for marker matching, so BlockedFaceInfo
  // (singular reason) is sufficient — no need to migrate to BlockedFaceDetail here.
  blocked: BlockedFaceInfo[];
}

// Column order:
//   - "blocked" sits right after "face" — face-level blockage is conceptually above
//     level/slot.
//   - Values are the text "blocked" / "" (more readable than the earlier "1" marker).
//   - The trailing "image" column is an empty placeholder for user-inserted cell images.
// parseLayoutWorkbook reads by header name (normalizeKeys → toLowerCase), so column
// reorderings and blocked-marker text are round-trip compatible.
const HEADERS = [
  "rack_id",
  "rack_name",
  "face",
  "blocked",
  "level",
  "sku",
  "item_name",
  "price (minor units)",
  "regular_price (minor units)",
  "promo",
  "image",
] as const;

interface SheetRow {
  rack_id: string;
  rack_name: string;
  face: string;
  blocked: "blocked" | "";
  level: number;
  sku: string;
  item_name: string;
  "price (minor units)": number;
  "regular_price (minor units)": number;
  promo: string;
  image: "";
}

const COL_WIDTHS: Record<typeof HEADERS[number], number> = {
  rack_id: 12,
  rack_name: 16,
  face: 8,
  blocked: 10,
  level: 7,
  sku: 14,
  item_name: 18,
  "price (minor units)": 22,
  "regular_price (minor units)": 28,
  promo: 12,
  image: 12,
};

// ARGB 8-char colors. ExcelJS ignores the leading alpha pair ("FF") but the spec requires it.
const BLOCKED_FILL = {
  type: "pattern" as const,
  pattern: "solid" as const,
  fgColor: { argb: "FFEFEFEF" },
};
const BLOCKED_FONT = { color: { argb: "FF808080" } };

export async function buildLayoutWorkbook(
  { store, blocked }: BuildLayoutWorkbookInput,
): Promise<ArrayBuffer> {
  const blockedSet = new Set(
    blocked.map((b) => `${b.rack_id}|${b.block}|${b.face}`),
  );
  const slotByCoord = new Map<string, SlotItem[]>();
  for (const r of store.racks) {
    for (const s of r.slots) {
      slotByCoord.set(`${r.id}|${s.block}|${s.face}|${s.level}`, s.items);
    }
  }

  const rows: SheetRow[] = [];
  for (const r of store.racks) {
    if (r.type === "entrance" || r.type === "exit") continue;
    // The grid editor only creates 1×1 racks, so block index is always 0.
    // Legacy multi-cell racks are pre-filtered by LegacyDetectModal upstream.
    const block = 0;
    for (const face of ["N", "S", "E", "W"] as const) {
      const isBlocked = blockedSet.has(`${r.id}|${block}|${face}`);
      for (let level = 1; level <= r.levels; level += 1) {
        if (isBlocked) {
          // Preserve coordinates only; clear SKU/metadata and stamp the "blocked" marker.
          rows.push({
            rack_id: r.id,
            rack_name: r.rack_name,
            face: formatFace(face),
            blocked: "blocked",
            level,
            sku: "",
            item_name: "",
            "price (minor units)": 0,
            "regular_price (minor units)": 0,
            promo: "",
            image: "",
          });
          continue;
        }
        const existing = slotByCoord.get(`${r.id}|${block}|${face}|${level}`);
        // One row per SlotItem; an empty slot yields exactly one row with sku="".
        const items: SlotItem[] = existing && existing.length > 0
          ? existing
          : [{ sku: "", name: "", price: 0, promo: "" }];
        for (const item of items) {
          rows.push({
            rack_id: r.id,
            rack_name: r.rack_name,
            face: formatFace(face),
            blocked: "",
            level,
            sku: item.sku,
            item_name: item.name,
            "price (minor units)": item.price,
            "regular_price (minor units)": item.regular_price ?? 0,
            promo: item.promo,
            image: "",
          });
        }
      }
    }
  }

  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("rack_layout");
  ws.columns = HEADERS.map((h) => ({
    header: h,
    key: h,
    width: COL_WIDTHS[h],
  }));

  for (const row of rows) {
    const added = ws.addRow(row);
    if (row.blocked === "blocked") {
      added.eachCell({ includeEmpty: true }, (cell) => {
        cell.fill = BLOCKED_FILL;
        cell.font = BLOCKED_FONT;
      });
    }
  }

  return (await wb.xlsx.writeBuffer()) as ArrayBuffer;
}
