import { useMemo } from "react";
import type { Rack, Slot, Face, Store } from "@/shared/types/domain";
import { resolveImageUrl } from "@/shared/api/images";
import { formatMoney } from "@/shared/utils/money";
import { useSimulationStore } from "@/stores/simulationStore";

const FACE_LABELS: Record<Face, string> = { N: "North", S: "South", E: "East", W: "West" };
const FACE_ORDER: Face[] = ["N", "E", "S", "W"];
const EXCLUDED_TYPES = new Set(["entrance", "exit"]);

interface ItemRow {
  name: string;
  sku: string;
  blocks: number[];
  price: number;
  image_url: string | null;
}

interface LevelGroup {
  level: number;
  items: ItemRow[];
}

interface FaceGroup {
  face: Face;
  blocked: boolean;
  totalSlots: number;
  levels: LevelGroup[];
}

function countTotalBlocks(rack: Rack): number {
  let count = 0;
  for (const row of rack.shape) {
    for (const cell of row) {
      if (cell) count++;
    }
  }
  return count;
}

function groupRackSlots(rack: Rack): FaceGroup[] {
  const totalBlocks = countTotalBlocks(rack);
  const lockedByFace = new Map<string, number>();
  for (const lf of rack.locked_faces) {
    lockedByFace.set(lf.face, (lockedByFace.get(lf.face) ?? 0) + 1);
  }

  const faceSlots = new Map<Face, Slot[]>();
  const faceBlockSet = new Map<Face, Set<number>>();

  for (const slot of rack.slots) {
    const list = faceSlots.get(slot.face) ?? [];
    list.push(slot);
    faceSlots.set(slot.face, list);

    const blocks = faceBlockSet.get(slot.face) ?? new Set();
    blocks.add(slot.block);
    faceBlockSet.set(slot.face, blocks);
  }

  const facesWithData = new Set<Face>([...faceSlots.keys()]);
  for (const lf of rack.locked_faces) {
    facesWithData.add(lf.face as Face);
  }

  return FACE_ORDER
    .filter((f) => facesWithData.has(f))
    .map((face) => {
      const blocked = (lockedByFace.get(face) ?? 0) >= totalBlocks;
      const slots = faceSlots.get(face) ?? [];

      const byLevel = new Map<number, Slot[]>();
      for (const s of slots) {
        const list = byLevel.get(s.level) ?? [];
        list.push(s);
        byLevel.set(s.level, list);
      }

      const maxLevel = rack.levels || 4;
      const levels: LevelGroup[] = [];
      for (let level = maxLevel; level >= 1; level--) {
        const levelSlots = byLevel.get(level) ?? [];
        if (levelSlots.length === 0) continue;

        // Group by SKU: within a level/face, the same SKU spread across multiple blocks
        // collapses into one row with a blocks[] list. A slot with multiple SlotItems
        // produces one row per SKU, so the same (block, level, face) coordinate may
        // appear in multiple rows (each SlotItem carries its own name/price/promo).
        const bySku = new Map<string, ItemRow>();
        for (const s of levelSlots) {
          if (!s.items || s.items.length === 0) continue;
          for (const slotItem of s.items) {
            const existing = bySku.get(slotItem.sku);
            if (existing) {
              if (!existing.blocks.includes(s.block)) existing.blocks.push(s.block);
            } else {
              bySku.set(slotItem.sku, {
                name: slotItem.name,
                sku: slotItem.sku,
                blocks: [s.block],
                price: slotItem.price,
                image_url: slotItem.image_url ?? null,
              });
            }
          }
        }
        for (const item of bySku.values()) {
          item.blocks.sort((a, b) => a - b);
        }

        levels.push({ level, items: [...bySku.values()] });
      }

      return {
        face,
        blocked,
        totalSlots: faceBlockSet.get(face)?.size ?? 0,
        levels,
      };
    });
}

interface Props {
  store: Store;
}

export function RackDetailView({ store }: Props) {
  const currency = useSimulationStore((s) => s.currency);
  const racks = useMemo(
    () => store.racks.filter((r) => !EXCLUDED_TYPES.has(r.type)),
    [store],
  );

  if (racks.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-xs text-muted-foreground">
        No items assigned
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 z-10 bg-muted/90 backdrop-blur-sm">
          <tr className="border-b text-left text-muted-foreground">
            <th className="w-[140px] pl-6 pr-2 py-2 font-medium">Rack</th>
            <th className="w-[80px] px-2 py-2 font-medium">Face</th>
            <th className="w-[80px] px-2 py-2 font-medium">Total slots</th>
            <th className="w-[60px] px-2 py-2 font-medium">Level</th>
            <th className="px-2 py-2 font-medium">Items</th>
            <th className="w-[80px] px-2 py-2 font-medium">Slots</th>
            <th className="w-[70px] pl-2 pr-6 py-2 text-right font-medium">Price</th>
          </tr>
        </thead>
        <tbody>
          {racks.map((rack) => {
            const groups = groupRackSlots(rack);

            if (groups.length === 0) {
              return (
                <tr key={rack.id} className="border-b">
                  <td className="pl-6 pr-2 py-1.5">{rack.rack_name}</td>
                  <td colSpan={6} className="px-2 py-1.5 italic text-muted-foreground">
                    No items assigned
                  </td>
                </tr>
              );
            }

            let rackFirstRow = true;

            return groups.flatMap((fg) => {
              if (fg.blocked) {
                const showRack = rackFirstRow;
                rackFirstRow = false;
                return [(
                  <tr key={`${rack.id}-${fg.face}-blocked`} className="border-b">
                    <td className="px-4 py-1.5">{showRack ? rack.rack_name : ""}</td>
                    <td className="px-2 py-1.5">{FACE_LABELS[fg.face]}</td>
                    <td className="px-2 py-1.5 italic text-muted-foreground">blocked</td>
                    <td colSpan={4} className="px-2 py-1.5 italic text-muted-foreground">
                      This section is blocked
                    </td>
                  </tr>
                )];
              }

              const rows: React.ReactElement[] = [];
              let faceFirstRow = true;

              for (const lg of fg.levels) {
                lg.items.forEach((item, si) => {
                  const showRack = rackFirstRow;
                  const showFace = faceFirstRow;
                  const showLevel = si === 0;

                  if (rackFirstRow) rackFirstRow = false;
                  if (faceFirstRow) faceFirstRow = false;

                  rows.push(
                    <tr key={`${rack.id}-${fg.face}-${lg.level}-${item.sku}`} className="border-b">
                      <td className="pl-6 pr-2 py-1">{showRack ? rack.rack_name : ""}</td>
                      <td className="px-2 py-1">{showFace ? FACE_LABELS[fg.face] : ""}</td>
                      <td className="px-2 py-1 tabular-nums">{showFace ? fg.totalSlots : ""}</td>
                      <td className="px-2 py-1 tabular-nums">{showLevel ? lg.level : ""}</td>
                      <td className="px-2 py-1">
                        <div className="flex items-center gap-2">
                          {item.image_url ? (
                            <img
                              src={resolveImageUrl(item.image_url)}
                              alt={item.name}
                              className="size-8 shrink-0 rounded border bg-muted object-contain"
                            />
                          ) : (
                            <div className="flex size-8 shrink-0 items-center justify-center rounded border bg-muted text-[9px] text-muted-foreground">
                              no img
                            </div>
                          )}
                          <span className="truncate">{item.name}</span>
                        </div>
                      </td>
                      <td className="px-2 py-1 tabular-nums">{item.blocks.map((b) => b + 1).join(",")}</td>
                      <td className="pl-2 pr-6 py-1 text-right tabular-nums">{formatMoney(item.price, currency)}</td>
                    </tr>,
                  );
                });
              }

              return rows;
            });
          })}
        </tbody>
      </table>
    </div>
  );
}
