// Visual grid editor — renders a width × height grid of GridCells.
//
// Row iteration is outer (y), column
// iteration inner (x) — y=0 row sits at the top of the visual grid.

import { useMemo, useState } from "react";
import { Minus, Plus } from "lucide-react";
import type { Position, Rack, BlockedFaceDetail } from "@/shared/types/domain";
import { Card } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
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
  const [cellSize, setCellSize] = useState(64);

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
    <Card data-testid="grid-editor" className="min-w-0 gap-2 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="text-muted-foreground">{width} × {height} cells · Scroll to explore</span>
        <div className="flex items-center gap-1">
          <Button type="button" variant="outline" size="icon-sm" aria-label="Zoom out grid"
            disabled={cellSize <= 40} onClick={() => setCellSize((size) => size - 8)}>
            <Minus className="size-3" />
          </Button>
          <output aria-label="Grid zoom" className="w-12 text-center">{Math.round(cellSize / 64 * 100)}%</output>
          <Button type="button" variant="outline" size="icon-sm" aria-label="Zoom in grid"
            disabled={cellSize >= 96} onClick={() => setCellSize((size) => size + 8)}>
            <Plus className="size-3" />
          </Button>
        </div>
      </div>
      <div
        role="region"
        aria-label="Floor grid"
        tabIndex={0}
        data-testid="grid-scroll-area"
        className="max-h-[55vh] min-h-40 overflow-auto rounded-md border p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="grid w-max gap-1" data-testid="grid-canvas"
          style={{ gridTemplateColumns: `repeat(${width}, ${cellSize}px)`, gridAutoRows: `${cellSize}px` }}>
          {cells}
        </div>
      </div>
      <span className="text-xs text-muted-foreground" aria-live="polite">
        {selectedCell ? `Selected cell: column ${selectedCell[0] + 1}, row ${selectedCell[1] + 1}` : "Select a cell to edit its fixture."}
      </span>
    </Card>
  );
}
