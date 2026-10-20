// A store in the home gallery: its footprint drawn to scale as an isometric slab, then its name.

import { CalendarDays, Ruler } from "lucide-react";

import type { ProjectListItem } from "@/shared/api/client";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { cn } from "@/shared/utils/cn";

const STATUS_STYLE: Record<string, { dot: string; label: string }> = {
  "Setting up": { dot: "bg-heat-3", label: "Setting up" },
  Ready: { dot: "bg-heat-1", label: "Ready to simulate" },
  Simulated: { dot: "bg-positive", label: "Simulated" },
};

const STORE_TYPE_LABELS: Record<string, string> = {
  convenience: "Convenience store",
  cafe: "Café",
  bakery: "Bakery",
  supermarket: "Supermarket",
  cosmetics: "Cosmetics",
  clothing: "Clothing",
  electronics: "Electronics",
  pharmacy: "Pharmacy",
};

function Footprint({ grid }: { grid: [number, number] | null }) {
  const [gw, gh] = grid ?? [10, 8];
  const s = 46 / Math.max(gw, gh);
  const w = gw * s;
  const d = gh * s;
  const iso = (x: number, y: number, z = 0) => `${((x - y) * 0.87).toFixed(1)},${((x + y) * 0.5 - z).toFixed(1)}`;
  const h = 7;
  return (
    <svg viewBox="-50 -14 100 66" className="h-24 w-full" aria-hidden>
      <polygon points={[iso(0, d), iso(w, d), iso(w, d, -h), iso(0, d, -h)].join(" ")} transform={`translate(0 ${h})`} fill="var(--hero-shelf-left)" />
      <polygon points={[iso(w, 0), iso(w, d), iso(w, d, -h), iso(w, 0, -h)].join(" ")} transform={`translate(0 ${h})`} fill="var(--hero-shelf-right)" />
      <polygon points={[iso(0, 0), iso(w, 0), iso(w, d), iso(0, d)].join(" ")} fill="var(--hero-floor)" stroke="var(--hero-line)" />
      {/* aisles */}
      {Array.from({ length: Math.max(1, Math.floor(gh / 3)) }, (_, i) => {
        const y = ((i + 1) * d) / (Math.floor(gh / 3) + 1);
        return <line key={i} x1={iso(w * 0.18, y).split(",")[0]} y1={iso(w * 0.18, y).split(",")[1]} x2={iso(w * 0.82, y).split(",")[0]} y2={iso(w * 0.82, y).split(",")[1]} stroke="var(--hero-shelf-left)" strokeWidth={3.2} strokeLinecap="round" />;
      })}
      <line x1={iso(w * 0.1, 0.6).split(",")[0]} y1={iso(w * 0.1, 0.6).split(",")[1]} x2={iso(w * 0.9, 0.6).split(",")[0]} y2={iso(w * 0.9, 0.6).split(",")[1]} stroke="var(--hero-fridge-glow)" strokeWidth={2.4} strokeLinecap="round" />
    </svg>
  );
}

export function StoreTile({ project, onOpen }: { project: ProjectListItem; onOpen: () => void }) {
  const status = STATUS_STYLE[project.status] ?? { dot: "bg-muted-foreground", label: project.status };
  const typeLabel = STORE_TYPE_LABELS[project.store_type] ?? project.store_type;
  const openDays = project.weekly_schedule?.filter((d) => d.is_open).length ?? 0;

  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex flex-col overflow-hidden rounded-2xl border bg-card text-left transition-[transform,box-shadow,border-color] hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-float focus-visible:border-primary"
    >
      <div className="relative bg-muted/50 px-4 pt-3 dark:bg-muted/30">
        <Footprint grid={project.grid_size} />
        <span className="heat-gradient absolute inset-x-0 bottom-0 h-[3px] origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100" aria-hidden />
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <h3 className="font-display text-lg leading-snug font-semibold">{project.name || "Untitled store"}</h3>
        <p className="text-sm text-muted-foreground">{typeLabel}</p>
        {project.description && <p className="line-clamp-2 text-sm text-muted-foreground/90">{project.description}</p>}
        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-2 text-sm">
          <span className="flex items-center gap-1.5">
            <span className={cn("size-2 rounded-full", status.dot)} aria-hidden />
            {status.label}
          </span>
          {project.grid_size && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <Ruler className="size-3.5" aria-hidden />
              {project.grid_size[0]}×{project.grid_size[1]} m
            </span>
          )}
          {openDays > 0 && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <CalendarDays className="size-3.5" aria-hidden />
              {openDays} days open
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

export function StoreTileSkeleton() {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border bg-card p-4">
      <Skeleton className="h-24 w-full rounded-xl" />
      <Skeleton className="h-5 w-2/3" />
      <Skeleton className="h-4 w-1/3" />
    </div>
  );
}
