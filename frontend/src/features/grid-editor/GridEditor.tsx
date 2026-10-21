// Visual grid editor — renders a width × height grid of GridCells.
//
// Pure display + onCellClick passthrough. Row iteration is outer (y), column
// iteration inner (x) — y=0 row sits at the top of the visual grid.

import { useMemo } from "react";
import type { Position, Rack, BlockedFaceDetail } from "@/shared/types/domain";
import { Card } from "@/shared/components/ui/card";
import { GridCell } from "./GridCell";
import { rackCells } from "@/shared/utils/grid";

interface GridEditorProps {
  racks: Rack[];
  gridSize: [number, number]; // [width, height]
  blockedFaces: BlockedFaceDetail[];
  onCellClick: (position: Position) => void;
  selectedCell?: Position | null;
}

export function GridEditor({
  racks,
  gridSize,
  blockedFaces,
  onCellClick,
  selectedCell,
}: GridEditorProps) {
  const [width, height] = gridSize;

  // Position-keyed lookup: `${x},${y}` → rack[]. A cell may hold two racks (entrance + exit).
  const racksByCell = useMemo(() => {
    const map = new Map<string, Rack[]>();
    for (const rack of racks) {
      for (const [x, y] of rackCells(rack)) {
        const key = `${x},${y}`;
        const existing = map.get(key) ?? [];
        existing.push(rack);
        map.set(key, existing);
      }
    }
    return map;
  }, [racks]);

  // rack_id → BlockedFaceDetail[] for cheap per-cell filtering.
  const blockedByRack = useMemo(() => {
    const map = new Map<string, BlockedFaceDetail[]>();
    for (const detail of blockedFaces) {
      const existing = map.get(detail.rack_id) ?? [];
      existing.push(detail);
      map.set(detail.rack_id, existing);
    }
    return map;
  }, [blockedFaces]);

  const selectedKey = selectedCell ? `${selectedCell[0]},${selectedCell[1]}` : null;

  const cells: React.ReactNode[] = [];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const key = `${x},${y}`;
      const cellRacks = racksByCell.get(key) ?? [];
      const cellBlocked = cellRacks.flatMap(
        (r) => blockedByRack.get(r.id) ?? [],
      );
      cells.push(
        <GridCell
          key={key}
          position={[x, y]}
          racks={cellRacks}
          blockedFaces={cellBlocked}
          selected={selectedKey === key}
          onClick={() => onCellClick([x, y])}
        />,
      );
    }
  }

  return (
    <Card data-testid="grid-editor" className="p-3">
      <div
        className="grid w-full gap-1"
        style={{
          gridTemplateColumns: `repeat(${width}, minmax(0, 1fr))`,
        }}
      >
        {cells}
      </div>
    </Card>
  );
}
