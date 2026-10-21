// A store in the home gallery: its footprint drawn to scale as a glowing isometric slab, then its
// name, format and status. The card follows the pointer with a soft spotlight.

import { Link } from "@tanstack/react-router";
import { ArrowUpRight, CalendarDays, Camera, Clock, Map, Megaphone, Plus, Ruler, Store } from "lucide-react";

import { translate, useI18n } from "@/shared/i18n/i18n";
import type { Locale, MessageKey } from "@/shared/i18n/messages";
import { storeTypeLabel } from "@/shared/i18n/storeLabels";
import type { LayoutFootprint, ProjectListItem } from "@/shared/api/client";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { spotlightHandler } from "@/shared/utils/spotlight";
import { cn } from "@/shared/utils/cn";

const STATUS_STYLE: Record<string, { dot: string; label: MessageKey; tone: string }> = {
  "Setting up": { dot: "bg-warn", label: "settingUp", tone: "tone-warn" },
  Ready: { dot: "bg-heat-1", label: "readyToSimulate", tone: "border-heat-1/40 bg-heat-1/10 text-foreground" },
  Simulated: { dot: "bg-positive", label: "simulated", tone: "tone-good" },
};

const QUICK_LINKS = [
  { to: "/projects/$pid", label: "floor", icon: Store },
  { to: "/marketing/$pid", label: "market", icon: Megaphone },
  { to: "/capture/$pid", label: "capture", icon: Camera },
  { to: "/town/$pid", label: "area", icon: Map },
] as const;

function relativeTime(iso: string, locale: Locale): string | null {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return null;
  const seconds = (time - Date.now()) / 1000;
  const absolute = Math.abs(seconds);
  if (absolute < 60) return translate(locale, "justNow");
  const relative = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (absolute < 3600) return relative.format(Math.round(seconds / 60), "minute");
  if (absolute < 86400) return relative.format(Math.round(seconds / 3600), "hour");
  if (absolute < 30 * 86400) return relative.format(Math.round(seconds / 86400), "day");
  return new Date(time).toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric" });
}

const FIXTURE: Record<LayoutFootprint["racks"][number][4], { h: number; top: string; left: string; right: string }> = {
  shelf: { h: 5, top: "var(--hero-shelf-top)", left: "var(--hero-shelf-left)", right: "var(--hero-shelf-right)" },
  fridge: { h: 8, top: "var(--hero-fridge-top)", left: "var(--hero-fridge-left)", right: "var(--hero-fridge-right)" },
  counter: { h: 4, top: "var(--hero-counter-top)", left: "var(--hero-counter-left)", right: "var(--hero-counter-right)" },
  table: { h: 2.5, top: "var(--hero-shelf-top)", left: "var(--hero-shelf-left)", right: "var(--hero-shelf-right)" },
};

/** The store's real layout: its floor and every fixture as a small isometric block, drawn back to front. */
function LayoutFootprintSvg({ layout }: { layout: LayoutFootprint }) {
  const [gw, gh] = layout.grid;
  const s = 46 / Math.max(gw, gh, 1);
  const iso = (x: number, y: number, z = 0) => `${((x - y) * 0.87).toFixed(1)},${((x + y) * 0.5 - z).toFixed(1)}`;
  const w = gw * s;
  const d = gh * s;
  const slab = 7;
  const racks = [...layout.racks].sort((a, b) => a[0] + a[1] + a[2] + a[3] - (b[0] + b[1] + b[2] + b[3]));
  return (
    <svg viewBox="-50 -16 100 68" className="h-28 w-full drop-shadow-[0_18px_22px_rgb(0_0_0/0.25)] transition-transform duration-500 ease-out group-hover:-translate-y-1 group-hover:scale-[1.04]" aria-hidden>
      <polygon points={[iso(0, d), iso(w, d), iso(w, d, -slab), iso(0, d, -slab)].join(" ")} fill="var(--hero-shelf-left)" />
      <polygon points={[iso(w, 0), iso(w, d), iso(w, d, -slab), iso(w, 0, -slab)].join(" ")} fill="var(--hero-shelf-right)" />
      <polygon points={[iso(0, 0), iso(w, 0), iso(w, d), iso(0, d)].join(" ")} fill="var(--hero-floor)" stroke="var(--hero-line)" />
      {racks.map(([x, y, rw, rd, kind], i) => {
        const f = FIXTURE[kind] ?? FIXTURE.shelf;
        const inset = Math.min(0.12, rw / 4, rd / 4);
        const x0 = (x + inset) * s, y0 = (y + inset) * s, x1 = (x + rw - inset) * s, y1 = (y + rd - inset) * s;
        return (
          <g key={i}>
            <polygon points={[iso(x0, y1), iso(x1, y1), iso(x1, y1, f.h), iso(x0, y1, f.h)].join(" ")} fill={f.left} />
            <polygon points={[iso(x1, y0), iso(x1, y1), iso(x1, y1, f.h), iso(x1, y0, f.h)].join(" ")} fill={f.right} />
            <polygon points={[iso(x0, y0, f.h), iso(x1, y0, f.h), iso(x1, y1, f.h), iso(x0, y1, f.h)].join(" ")} fill={f.top} />
            {kind === "fridge" && (
              <polygon points={[iso(x0 + 0.6, y1, 1.6), iso(x1 - 0.6, y1, 1.6), iso(x1 - 0.6, y1, f.h - 1.4), iso(x0 + 0.6, y1, f.h - 1.4)].join(" ")}
                fill="var(--hero-fridge-glow)" opacity={0.85} />
            )}
          </g>
        );
      })}
    </svg>
  );
}

function Footprint({ grid, layout }: { grid: [number, number] | null; layout?: LayoutFootprint | null }) {
  if (layout && layout.racks.length > 0) return <LayoutFootprintSvg layout={layout} />;
  const [gw, gh] = grid ?? [10, 8];
  const s = 46 / Math.max(gw, gh);
  const w = gw * s;
  const d = gh * s;
  const iso = (x: number, y: number, z = 0) => `${((x - y) * 0.87).toFixed(1)},${((x + y) * 0.5 - z).toFixed(1)}`;
  const xy = (x: number, y: number) => iso(x, y).split(",");
  const h = 7;
  const aisles = Math.max(1, Math.floor(gh / 3));
  return (
    <svg viewBox="-50 -14 100 66" className="h-28 w-full drop-shadow-[0_18px_22px_rgb(0_0_0/0.25)] transition-transform duration-500 ease-out group-hover:-translate-y-1 group-hover:scale-[1.04]" aria-hidden>
      <polygon points={[iso(0, d), iso(w, d), iso(w, d, -h), iso(0, d, -h)].join(" ")} transform={`translate(0 ${h})`} fill="var(--hero-shelf-left)" />
      <polygon points={[iso(w, 0), iso(w, d), iso(w, d, -h), iso(w, 0, -h)].join(" ")} transform={`translate(0 ${h})`} fill="var(--hero-shelf-right)" />
      <polygon points={[iso(0, 0), iso(w, 0), iso(w, d), iso(0, d)].join(" ")} fill="var(--hero-floor)" stroke="var(--hero-line)" />
      {Array.from({ length: aisles }, (_, i) => {
        const y = ((i + 1) * d) / (aisles + 1);
        const [x1, y1] = xy(w * 0.18, y);
        const [x2, y2] = xy(w * 0.82, y);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--hero-shelf-left)" strokeWidth={3.2} strokeLinecap="round" />;
      })}
      {(() => {
        const [x1, y1] = xy(w * 0.1, 0.6);
        const [x2, y2] = xy(w * 0.9, 0.6);
        return <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--hero-fridge-glow)" strokeWidth={2.4} strokeLinecap="round" />;
      })()}
      {(() => {
        const [cx, cy] = xy(w * 0.15, d * 0.85);
        return <circle cx={cx} cy={cy} r={2.6} fill="var(--volt)" />;
      })()}
    </svg>
  );
}

export function StoreTile({ project, onOpen, index = 0 }: { project: ProjectListItem; onOpen: () => void; index?: number }) {
  const { locale, t } = useI18n();
  const knownStatus = Object.prototype.hasOwnProperty.call(STATUS_STYLE, project.status) ? STATUS_STYLE[project.status] : undefined;
  const status = knownStatus ? { ...knownStatus, label: t(knownStatus.label) } : { dot: "bg-muted-foreground", label: project.status, tone: "border-border bg-card/60" };
  const typeLabel = storeTypeLabel(project.store_type, locale);
  const openDays = project.weekly_schedule?.filter((d) => d.is_open).length ?? 0;
  const updated = relativeTime(project.updated_at, locale);

  return (
    <div
      onMouseMove={spotlightHandler}
      style={{ animationDelay: `${80 + index * 60}ms` }}
      className="spotlight group flex animate-rise flex-col overflow-hidden rounded-[1.6rem] border border-glass-border bg-card/70 shadow-[inset_0_1px_0_var(--highlight),var(--shadow-float)] backdrop-blur-xl transition-[transform,box-shadow,border-color] duration-300 hover:-translate-y-1 hover:border-foreground/15 hover:shadow-[inset_0_1px_0_var(--highlight),var(--shadow-lift)] focus-within:border-ring"
    >
    <button type="button" onClick={onOpen} className="flex flex-1 flex-col text-left outline-none">
      <div className="dot-grid relative overflow-hidden px-5 pt-5 pb-2">
        <div
          className="pointer-events-none absolute inset-x-6 top-10 h-24 rounded-full opacity-60 blur-3xl transition-opacity duration-500 group-hover:opacity-100"
          style={{ background: "radial-gradient(closest-side, color-mix(in oklab, var(--heat-2) 45%, transparent), transparent)" }}
          aria-hidden
        />
        <div className="relative flex items-start justify-between">
          <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium backdrop-blur", status.tone)}>
            <span className={cn("size-1.5 rounded-full", status.dot)} aria-hidden />
            {status.label}
          </span>
          <span className="grid size-8 place-items-center rounded-full border border-glass-border bg-card/70 text-muted-foreground opacity-0 transition-all duration-300 group-hover:rotate-0 group-hover:opacity-100 group-hover:text-foreground -rotate-45">
            <ArrowUpRight className="size-4" aria-hidden />
          </span>
        </div>
        <Footprint grid={project.grid_size} layout={project.footprint} />
      </div>
      <div className="flex flex-1 flex-col gap-1.5 border-t border-glass-border px-5 pt-4 pb-5">
        <span className="eyebrow">{typeLabel}</span>
        <h3 className="font-display text-[1.35rem] leading-tight">{project.name || t("untitledStore")}</h3>
        {project.description && <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">{project.description}</p>}
        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-3 text-[0.8rem] text-muted-foreground">
          {project.grid_size && (
            <span className="num flex items-center gap-1.5">
              <Ruler className="size-3.5" aria-hidden />
              {project.grid_size[0]}×{project.grid_size[1]} m
            </span>
          )}
          {openDays > 0 && (
            <span className="flex items-center gap-1.5">
              <CalendarDays className="size-3.5" aria-hidden />
              {t("daysOpen", { count: openDays })}
            </span>
          )}
          {updated && (
            <span className="flex items-center gap-1.5">
              <Clock className="size-3.5" aria-hidden />
              {updated}
            </span>
          )}
        </div>
      </div>
    </button>
      <nav className="flex border-t border-glass-border" aria-label={t("openStoreIn", { name: project.name || t("store") })}>
        {QUICK_LINKS.map(({ to, label, icon: Icon }) => (
          <Link key={label} to={to} params={{ pid: project.project_id }}
            className="flex flex-1 items-center justify-center gap-1.5 py-2.5 text-[0.75rem] text-muted-foreground transition-colors hover:bg-foreground/[0.04] hover:text-foreground">
            <Icon className="size-3.5" aria-hidden /> {t(label)}
          </Link>
        ))}
      </nav>
    </div>
  );
}

export function NewStoreTile({ onClick }: { onClick: () => void }) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseMove={spotlightHandler}
      className="spotlight group flex min-h-72 flex-col items-center justify-center gap-4 rounded-[1.6rem] border border-dashed border-foreground/15 bg-card/30 text-muted-foreground backdrop-blur-xl transition-[border-color,color,background-color] duration-300 hover:border-primary/60 hover:bg-card/50 hover:text-foreground"
    >
      <span className="relative grid size-16 place-items-center">
        <span className="absolute inset-0 animate-spin-slow rounded-full bg-[conic-gradient(from_0deg,var(--heat-1),var(--heat-2),var(--heat-3),var(--volt),var(--heat-1))] opacity-60 blur-md transition-opacity group-hover:opacity-100" aria-hidden />
        <span className="relative grid size-14 place-items-center rounded-full bg-background">
          <Plus className="size-6 transition-transform duration-300 group-hover:rotate-90" aria-hidden />
        </span>
      </span>
      <span className="text-center">
        <span className="block font-display text-lg text-foreground">{t("newStore")}</span>
        <span className="text-sm">{t("templateTagline")}</span>
      </span>
    </button>
  );
}

export function StoreTileSkeleton() {
  return (
    <div className="flex flex-col gap-3 rounded-[1.6rem] border border-glass-border bg-card/50 p-5">
      <Skeleton className="h-32 w-full rounded-2xl" />
      <Skeleton className="h-4 w-1/4" />
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}
