// Visual grid editor — renders a width × height grid of GridCells.
//
// Row iteration is outer (y), column
// iteration inner (x) — y=0 row sits at the top of the visual grid.

import { useMemo, useRef, useState } from "react";
import { Minus, Plus } from "lucide-react";
import type { Position, Rack, BlockedFaceDetail } from "@/shared/types/domain";
import { Card } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { GridCell } from "./GridCell";
import { rackCells } from "@/shared/utils/grid";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import { formatPercent } from "@/shared/utils/money";

interface GridEditorProps {
  racks: Rack[];
  gridSize: [number, number]; // [width, height]
  blockedFaces: BlockedFaceDetail[];
  onCellClick: (position: Position) => void;
  selectedCell?: Position | null;
  placing?: boolean;
  /** A fixture dragged from one cell and dropped on another (a press and release on one cell stays a click). */
  onDragMove?: (from: Position, to: Position) => void;
}

function cellOf(element: Element | null): Position | null {
  const at = element?.closest<HTMLElement>("[data-testid^='grid-cell-']")?.dataset.testid?.split("-").slice(2).map(Number);
  return at && at.length === 2 ? [at[0]!, at[1]!] : null;
}

// Cells are 64 px at 100 %; zoom steps by 8 px between 40 and 96.
/** The largest zoom step, at most 100 %, whose rows all fit the grid area (55 % of the window), so the floor opens
 *  whole instead of cutting its last row; a floor too deep for that opens at the smallest step and scrolls. */
function fittingCellSize(rows: number): number {
  const room = typeof window === "undefined" ? Infinity : window.innerHeight * 0.55 - 10;
  for (let size = 64; size > 40; size -= 8) if (rows * size + (rows - 1) * 4 <= room) return size;
  return 40;
}

export function GridEditor({
  racks,
  gridSize,
  blockedFaces,
  onCellClick,
  selectedCell,
  placing = false,
  onDragMove,
}: GridEditorProps) {
  const { t } = useI18n();
  const dragFrom = useRef<Position | null>(null);
  const suppressDragClick = useRef(false);
  const [width, height] = gridSize;
  const [cellSize, setCellSize] = useState(() => fittingCellSize(height));
  // One Tab stop for the whole grid (the cell last moved to, else the selected one); the arrow keys move from there.
  const [current, setCurrent] = useState<string | null>(null);
  const stop = [current, selectedCell ? `${selectedCell[0]},${selectedCell[1]}` : null].find((key) => {
    if (!key) return false;
    const [x = -1, y = -1] = key.split(",").map(Number);
    return Number.isInteger(x) && Number.isInteger(y) && x >= 0 && y >= 0 && x < width && y < height;
  }) ?? "0,0";

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
          onClick={() => { setCurrent(key); onCellClick([x, y]); }}
          tabIndex={stop === key ? 0 : -1}
        />,
      );
    }
  }

  return (
    <Card data-testid="grid-editor" className="min-w-0 gap-2 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="text-muted-foreground">{t("gridSizeHint", { width, height })}</span>
        <div className="flex items-center gap-1">
          <Button type="button" variant="outline" size="icon-sm" aria-label={t("gridZoomOut")}
            disabled={cellSize <= 40} onClick={() => setCellSize((size) => size - 8)}>
            <Minus className="size-3" />
          </Button>
          <output aria-label={t("gridZoom")} className="w-12 text-center">{formatPercent(cellSize / 64, 0)}</output>
          <Button type="button" variant="outline" size="icon-sm" aria-label={t("gridZoomIn")}
            disabled={cellSize >= 96} onClick={() => setCellSize((size) => size + 8)}>
            <Plus className="size-3" />
          </Button>
        </div>
      </div>
      <div
        role="region"
        aria-label={t("gridRegion")}
        tabIndex={0}
        data-testid="grid-scroll-area"
        className={cn("max-h-[55vh] min-h-40 overflow-auto rounded-md border p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", placing && "[&_button]:cursor-crosshair")}
      >
        <div className="grid w-max gap-1" data-testid="grid-canvas" onKeyDown={(event) => {
          const cell = (event.target as HTMLElement).closest<HTMLElement>("[data-testid^='grid-cell-']");
          const at = cell?.dataset.testid?.split("-").slice(2).map(Number);
          if (!at || at.length !== 2) return;
          const [x, y] = at as [number, number];
          const next: [number, number] | null = event.key === "ArrowRight" ? [Math.min(width - 1, x + 1), y]
            : event.key === "ArrowLeft" ? [Math.max(0, x - 1), y]
              : event.key === "ArrowDown" ? [x, Math.min(height - 1, y + 1)]
                : event.key === "ArrowUp" ? [x, Math.max(0, y - 1)]
                  : event.key === "Home" ? [0, y] : event.key === "End" ? [width - 1, y] : null;
          if (!next) return;
          event.preventDefault();
          setCurrent(`${next[0]},${next[1]}`);
          event.currentTarget.querySelector<HTMLElement>(`[data-testid='grid-cell-${next[0]}-${next[1]}']`)?.focus();
        }}
          onPointerDown={(event) => {
            suppressDragClick.current = false;
            const target = event.target as HTMLElement;
            dragFrom.current = onDragMove && event.button === 0 && !placing && !target.closest("[data-empty='true']") ? cellOf(target) : null;
          }}
          onPointerCancel={() => { dragFrom.current = null; suppressDragClick.current = false; }}
          onPointerUp={(event) => {
            const from = dragFrom.current;
            dragFrom.current = null;
            // Touch keeps the press's target, so the cell under the pointer is looked up where it was released.
            const to = cellOf(document.elementFromPoint(event.clientX, event.clientY));
            if (!from || !to || (from[0] === to[0] && from[1] === to[1])) return;
            suppressDragClick.current = true;
            onDragMove?.(from, to);
            // Focus follows the fixture instead of staying on the cell it left.
            setCurrent(`${to[0]},${to[1]}`);
            event.currentTarget.querySelector<HTMLElement>(`[data-testid='grid-cell-${to[0]}-${to[1]}']`)?.focus();
          }}
          onClickCapture={(event) => {
            const dragged = suppressDragClick.current;
            suppressDragClick.current = false;
            // Touch can click the press cell after the drop; keyboard activation has detail=0.
            if (dragged && event.detail > 0) { event.preventDefault(); event.stopPropagation(); }
          }}
          style={{ gridTemplateColumns: `repeat(${width}, ${cellSize}px)`, gridAutoRows: `${cellSize}px` }}>
          {cells}
        </div>
      </div>
      <span className="text-xs text-muted-foreground" aria-live="polite">
        {selectedCell ? t("gridSelectedCell", { column: selectedCell[0] + 1, row: selectedCell[1] + 1 }) : t("gridSelectCell")}
      </span>
    </Card>
  );
}
