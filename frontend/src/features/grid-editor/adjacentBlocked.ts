// Grid editor: frontend-side blocked-face derivation.
//
// Backend (engine/validate_layout) emits four reasons:
//   locked / out_of_bounds / occupied / unreachable
// plus `occluded` (blocked by an adjacent cell) over the wire.
//
// This module only computes the two reasons derivable from frontend state alone:
// `out_of_bounds` and `occluded`. `unreachable` requires BFS and comes from the
// backend response (mergeBlockedFaces unions both sources).
//
// The grid editor only creates 1×1 racks, so the face → adjacent-cell mapping
// mirrors `_FACE_OFFSETS` in backend domain/rack.py:
//   N=(0,-1) / S=(0,1) / W=(-1,0) / E=(1,0)
// Since racks are 1×1, every face has block index 0.

import type { Face, Position, Rack, BlockReason, BlockedFaceDetail } from "@/shared/types/domain";

import { rackCells } from "@/shared/utils/grid";

const FACES: Face[] = ["N", "S", "W", "E"];

const FACE_OFFSETS: Record<Face, [number, number]> = {
  N: [0, -1],
  S: [0, 1],
  W: [-1, 0],
  E: [1, 0],
};

// entrance / exit racks have no slotted faces, so exclude them from blocked-face calc.
function isFacelessRack(rack: Rack): boolean {
  return rack.type === "entrance" || rack.type === "exit";
}

function isInBounds([x, y]: Position, [w, h]: [number, number]): boolean {
  return x >= 0 && x < w && y >= 0 && y < h;
}

function buildOccupancy(racks: Rack[]): Map<string, string> {
  const occ = new Map<string, string>();
  for (const rack of racks) {
    if (isFacelessRack(rack)) continue;
    for (const [x, y] of rackCells(rack)) {
      occ.set(`${x},${y}`, rack.id);
    }
  }
  return occ;
}

// out_of_bounds and occluded are mutually exclusive — out-of-bounds cells can't be occupied.
export function computeAdjacentBlocked(
  racks: Rack[],
  gridSize: [number, number],
): BlockedFaceDetail[] {
  const occupancy = buildOccupancy(racks);
  const out: BlockedFaceDetail[] = [];

  for (const rack of racks) {
    if (isFacelessRack(rack) || rack.type === "table") continue;
    // 1×1 assumption — if shape is larger, conservatively check only the (0,0) block
    // (the editor doesn't author multi-cell, so this is regression defense).
    const cells = rackCells(rack);
    if (cells.length === 0) continue;
    const [cx, cy] = cells[0]!;

    for (const face of FACES) {
      const [dx, dy] = FACE_OFFSETS[face];
      const adj: Position = [cx + dx, cy + dy];
      const reasons: BlockReason[] = [];

      if (!isInBounds(adj, gridSize)) {
        reasons.push("out_of_bounds");
      } else {
        const occupant = occupancy.get(`${adj[0]},${adj[1]}`);
        if (occupant !== undefined && occupant !== rack.id) {
          reasons.push("occluded");
        }
      }

      if (reasons.length > 0) {
        out.push({ rack_id: rack.id, block: 0, face, reasons });
      }
    }
  }

  return out;
}

// Output is sorted lexicographically by (rack_id, block, face) so tests are deterministic.
export function mergeBlockedFaces(
  fromBackend: BlockedFaceDetail[],
  fromFrontend: BlockedFaceDetail[],
): BlockedFaceDetail[] {
  const byKey = new Map<string, BlockedFaceDetail>();

  const merge = (entry: BlockedFaceDetail) => {
    const key = `${entry.rack_id}|${entry.block}|${entry.face}`;
    const existing = byKey.get(key);
    if (existing === undefined) {
      byKey.set(key, {
        rack_id: entry.rack_id,
        block: entry.block,
        face: entry.face,
        reasons: [...entry.reasons],
      });
      return;
    }
    for (const reason of entry.reasons) {
      if (!existing.reasons.includes(reason)) {
        existing.reasons.push(reason);
      }
    }
  };

  for (const e of fromBackend) merge(e);
  for (const e of fromFrontend) merge(e);

  return Array.from(byKey.values()).sort((a, b) => {
    if (a.rack_id !== b.rack_id) return a.rack_id < b.rack_id ? -1 : 1;
    if (a.block !== b.block) return a.block - b.block;
    if (a.face !== b.face) return a.face < b.face ? -1 : 1;
    return 0;
  });
}
