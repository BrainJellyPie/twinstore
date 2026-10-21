// A cell can host two racks only in the entrance+exit pair case; all other types
// are single-rack. Dining groups occupy four cells, each selecting the same fixture.

import {
  Boxes,
  Coins,
  DoorClosed,
  DoorOpen,
  Refrigerator,
  Armchair,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Position, Rack, RackType, BlockedFaceDetail } from "@/shared/types/domain";
import { cn } from "@/shared/utils/cn";
import { BlockedFaceOverlay } from "./BlockedFaceOverlay";

interface GridCellProps {
  position: Position;
  racks: Rack[];
  blockedFaces: BlockedFaceDetail[]; // already filtered to this cell's racks
  selected: boolean;
  onClick: () => void;
}

interface RackVisual {
  icon: LucideIcon;
  label: string;
  bgClass: string;
  iconClass: string;
}

const RACK_VISUALS: Record<RackType, RackVisual | null> = {
  entrance: {
    icon: DoorOpen,
    label: "In",
    bgClass: "bg-emerald-100 dark:bg-emerald-950/40",
    iconClass: "text-positive dark:text-emerald-300",
  },
  exit: {
    icon: DoorClosed,
    label: "Out",
    bgClass: "bg-violet-100 dark:bg-violet-950/40",
    iconClass: "text-violet-700 dark:text-violet-300",
  },
  shelf: {
    icon: Boxes,
    label: "Open",
    bgClass: "bg-stone-100 dark:bg-stone-900/50",
    iconClass: "text-stone-700 dark:text-stone-300",
  },
  fridge: {
    icon: Refrigerator,
    label: "Door",
    bgClass: "bg-sky-100 dark:bg-sky-950/40",
    iconClass: "text-sky-700 dark:text-sky-300",
  },
  counter: {
    icon: Coins,
    label: "Counter",
    bgClass: "bg-yellow-100 dark:bg-yellow-950/40",
    iconClass: "text-yellow-700 dark:text-yellow-300",
  },
  // Other domain rack types are not produced by the grid editor; render as plain rack.
  display: null,
  table: { icon: Armchair, label: "Dining", bgClass: "bg-violet-100 dark:bg-violet-950/40", iconClass: "text-violet-700 dark:text-violet-300" },
  wall: null,
};

const FACE_OVERLAY_TYPES: ReadonlySet<RackType> = new Set(["shelf", "fridge", "counter"]);

// rotation 0 ⇒ front=S. shelf/fridge/counter share the same face mapping.
// 90° steps: 0:S, 90:W, 180:N, 270:E.
const ROTATION_FRONT_FACE: Record<0 | 90 | 180 | 270, string> = {
  0: "absolute inset-x-0 bottom-0 h-1",
  90: "absolute inset-y-0 left-0 w-1",
  180: "absolute inset-x-0 top-0 h-1",
  270: "absolute inset-y-0 right-0 w-1",
};

export function GridCell({
  position,
  racks,
  blockedFaces,
  selected,
  onClick,
}: GridCellProps) {
  const [x, y] = position;

  if (racks.length === 0) {
    return (
      <button
        type="button"
        data-testid={`grid-cell-${x}-${y}`}
        data-empty="true"
        aria-pressed={selected}
        onClick={onClick}
        className={cn(
          "relative aspect-square w-full rounded-md border border-border bg-card text-card-foreground",
          "transition-colors hover:bg-accent hover:text-accent-foreground",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
          selected && "ring-2 ring-primary",
        )}
        aria-label={`empty cell ${x},${y}`}
      />
    );
  }

  // Multi-rack cell: side-by-side split. Domain only allows entrance+exit pairs here.
  if (racks.length > 1) {
    return (
      <button
        type="button"
        data-testid={`grid-cell-${x}-${y}`}
        data-rack-ids={racks.map((r) => r.id).join(",")}
        data-rack-type="entrance_exit"
        aria-pressed={selected}
        onClick={onClick}
        className={cn(
          "relative grid aspect-square w-full grid-cols-2 overflow-hidden rounded-md border border-border text-card-foreground",
          "transition-colors hover:opacity-90",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
          selected && "ring-2 ring-primary",
        )}
        aria-label={`gate ${racks.map((r) => r.type).join("+")} at ${x},${y}`}
      >
        {racks.map((rack) => {
          const visual = RACK_VISUALS[rack.type];
          const Icon = visual?.icon;
          return (
            <div
              key={rack.id}
              className={cn(
                "flex h-full flex-col items-center justify-center gap-0.5",
                visual?.bgClass ?? "bg-muted",
              )}
            >
              {Icon ? (
                <Icon
                  className={cn("h-4 w-4", visual?.iconClass)}
                  aria-hidden="true"
                />
              ) : null}
              {visual?.label ? (
                <span className="text-[0.68rem] leading-none font-medium">
                  {visual.label}
                </span>
              ) : null}
            </div>
          );
        })}
      </button>
    );
  }

  const rack = racks[0]!;
  const visual = RACK_VISUALS[rack.type];
  const Icon = visual?.icon;
  const showOverlay = FACE_OVERLAY_TYPES.has(rack.type) && blockedFaces.length > 0;
  // Only racks/counters show a rotation front-face indicator — rotation is weakly
  // meaningful for entrance/exit.
  const showFrontFace = FACE_OVERLAY_TYPES.has(rack.type);
  const frontFaceClass =
    ROTATION_FRONT_FACE[rack.rotation as 0 | 90 | 180 | 270] ?? ROTATION_FRONT_FACE[0];

  return (
    <button
      type="button"
      data-testid={`grid-cell-${x}-${y}`}
      data-rack-id={rack.id}
      data-rack-type={rack.type}
      aria-pressed={selected}
      onClick={onClick}
      className={cn(
        "relative aspect-square w-full rounded-md border border-border text-card-foreground",
        "flex flex-col items-center justify-center gap-1 overflow-hidden",
        "transition-colors hover:opacity-90",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
        visual?.bgClass ?? "bg-muted",
        selected && "ring-2 ring-primary",
      )}
      aria-label={`${rack.type} ${rack.rack_name || rack.id} at ${x},${y}`}
    >
      {Icon ? (
        <Icon
          className={cn("h-4 w-4 sm:h-5 sm:w-5", visual?.iconClass)}
          style={
            rack.rotation !== 0
              ? { transform: `rotate(${rack.rotation}deg)` }
              : undefined
          }
          aria-hidden="true"
        />
      ) : null}
      {visual?.label ? (
        <span className="text-[0.72rem] leading-none font-medium">{visual.label}</span>
      ) : null}
      {rack.rack_name ? (
        <span className="max-w-full truncate text-[0.68rem] leading-none text-muted-foreground">
          {rack.rack_name}
        </span>
      ) : null}
      {showFrontFace ? (
        <div
          data-testid={`rotation-front-${rack.rotation}`}
          aria-hidden
          className={cn(frontFaceClass, "pointer-events-none bg-primary/70")}
        />
      ) : null}
      {showOverlay ? <BlockedFaceOverlay blockedFaces={blockedFaces} /> : null}
    </button>
  );
}
