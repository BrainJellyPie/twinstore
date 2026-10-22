import { rackDiningSeats } from "@/shared/utils/dining";
import { useId, useRef, useState, type Ref } from "react";
import { resolveInteriorPalette } from "@/features/store-viewer/realistic/designThemes";
import type { ReservedArea } from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import type { Store } from "@/shared/types/domain";
import { rackCells } from "@/shared/utils/grid";
import { formatWeeklyHours } from "../weeklyHours";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const RACK_COLORS: Record<string, string> = {
  fridge: "#38bdf8", shelf: "#f59e0b", counter: "#475569", entrance: "#22c55e", exit: "#fb7185", table: "#a78bfa",
};
// The downloaded SVG is an export and keeps English, like the app's other exported files.
const FLOOR_LEGEND = "Blue: cold · Amber: display · Green IN: entrance · Rose OUT: exit · Split IN/OUT: shared gate · Slate: checkout · Purple: seating";
const RACK_TYPES: Record<string, MessageKey> = {
  shelf: "gridType_shelf", fridge: "gridType_fridge", counter: "gridType_counter", table: "gridType_table",
  entrance: "gridType_entrance", exit: "gridType_exit",
};

/** `name` is how the plan is titled in the details dialog (the store's name unless given, e.g. a translated format name). */
export function FloorPlanPreview({ store, areas, previewFrame, name = store.name }: { store: Store; areas: ReservedArea[]; previewFrame?: [number, number]; name?: string }) {
  const { locale, t } = useI18n();
  const [zoom, setZoom] = useState(1);
  const detailedPlan = useRef<SVGSVGElement>(null);
  const tables = store.racks.filter((rack) => rack.type === "table").length;
  const seats = store.racks.reduce((sum, rack) => sum + rackDiningSeats(rack), 0);
  function downloadPlan() {
    if (!detailedPlan.current) return;
    const exported = detailedPlan.current.cloneNode(true) as SVGSVGElement;
    const width = store.grid_size[0] + 1.4;
    const height = store.grid_size[1] + 1.4;
    const scale = 1600 / Math.max(width, height);
    exported.setAttribute("width", String(Math.round(width * scale)));
    exported.setAttribute("height", String(Math.round(height * scale)));
    exported.removeAttribute("class");
    exported.removeAttribute("style");
    exported.setAttribute("font-family", "Arial, sans-serif");
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${store.name} — ${store.grid_size.join("×")} cells`;
    const description = document.createElementNS("http://www.w3.org/2000/svg", "desc");
    description.textContent = `${tables} dining tables, ${seats} seats, ${store.racks.filter((rack) => rack.type === "counter").length} checkout counters. Operating hours: ${formatWeeklyHours(store.weekly_schedule)}. ${FLOOR_LEGEND}. ${areas.map((area, index) => `Area ${index + 1}: ${area.label}, ${area.width}×${area.height} cells at column ${area.x + 1}, row ${area.y + 1}.`).join(" ")}`;
    exported.prepend(title, description);
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(exported)], { type: "image/svg+xml;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `twinstore-${store.grid_size.join("x")}-floor-plan.svg`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <div className="space-y-1.5">
    <FloorPlan store={store} areas={areas} previewFrame={previewFrame} />
    <Dialog onOpenChange={(open) => { if (!open) setZoom(1); }}>
      <DialogTrigger asChild><button type="button" className="w-full rounded-md border px-2 py-1 text-xs hover:bg-muted">{t("layExpandFloorPlan")}</button></DialogTrigger>
      <DialogContent className="flex max-h-[92dvh] flex-col overflow-hidden sm:max-w-[min(92vw,1000px)]" data-testid="expanded-floor-plan-dialog">
        <DialogHeader className="shrink-0">
          <DialogTitle>{t("layFloorPlanDetails")}</DialogTitle>
          <DialogDescription>{t("layFloorPlanDetailsHint", { name, size: store.grid_size.join("×") })}</DialogDescription>
        </DialogHeader>
        <div role="group" aria-label={t("layFloorPlanControls")} className="flex shrink-0 flex-wrap items-center gap-2 text-xs">
          <button type="button" aria-label={t("layZoomOutPlan")} disabled={zoom === 1} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => setZoom((current) => Math.max(1, current - 0.5))}>−</button>
          <span className="min-w-10 text-center">{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label={t("layZoomInPlan")} disabled={zoom === 4} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => setZoom((current) => Math.min(4, current + 0.5))}>+</button>
          <button type="button" className="rounded border px-2 py-1" onClick={() => setZoom(1)}>{t("layFitFloorPlan")}</button>
          <button type="button" className="rounded border px-2 py-1 sm:ml-auto" onClick={downloadPlan}>{t("layDownloadSvg")}</button>
        </div>
        <div className="min-h-0 space-y-3 overflow-y-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          role="region" aria-label={t("layFloorPlanContent")} tabIndex={0}>
          <div className="h-[min(60dvh,720px)] min-h-40 overflow-auto rounded-md border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            role="region" aria-label={t("layExpandedFloorGrid")} tabIndex={0} data-testid="expanded-floor-scroll">
            <FloorPlan store={store} areas={areas} detailed zoom={zoom} ref={detailedPlan} />
          </div>
          <div className="space-y-1.5 text-xs">
            <p>{t("layFloorStats", { displays: store.racks.filter((rack) => rack.slots.length).length, tables, seats, counters: store.racks.filter((rack) => rack.type === "counter").length })}</p>
            <p className="break-words text-muted-foreground">{t("layOperatingHoursLine", { hours: formatWeeklyHours(store.weekly_schedule, locale) })}</p>
            <p className="text-muted-foreground">{t("floorPlanLegend")}</p>
            {!!areas.length && <ol className="max-h-24 list-decimal space-y-1 overflow-y-auto pl-5" aria-label={t("layReservedAreasInPlan")}>
              {areas.map((area, index) => <li key={index}>{t("layReservedAreaLine", { label: area.label, size: `${area.width}×${area.height}`, column: area.x + 1, row: area.y + 1 })}</li>)}
            </ol>}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>;
}

function FloorPlan({ store, areas, detailed = false, zoom = 1, ref, previewFrame }: { store: Store; areas: ReservedArea[]; detailed?: boolean; zoom?: number; ref?: Ref<SVGSVGElement>; previewFrame?: [number, number] }) {
  const { t } = useI18n();
  const typeLabel = (type: string) => Object.prototype.hasOwnProperty.call(RACK_TYPES, type) ? t(RACK_TYPES[type]!) : type;
  const gridId = useId();
  const [w, h] = store.grid_size;
  const [frameWidth, frameHeight] = previewFrame ?? store.grid_size;
  const palette = resolveInteriorPalette(store.design_theme, store.design_colors);
  const customFloor = store.design_colors?.floor != null;
  const channels = [1, 3, 5].map((offset) => parseInt(palette.floor.slice(offset, offset + 2), 16) / 255)
    .map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  const luminance = channels[0]! * 0.2126 + channels[1]! * 0.7152 + channels[2]! * 0.0722;
  const floorInk = luminance > 0.179 ? "#000000" : "#ffffff";
  const gates = new Map<string, { x: number; y: number; entrances: string[]; exits: string[] }>();
  for (const rack of store.racks) {
    if (rack.type !== "entrance" && rack.type !== "exit") continue;
    for (const [x, y] of rackCells(rack)) {
      const key = `${x},${y}`;
      const gate = gates.get(key) ?? { x, y, entrances: [], exits: [] };
      (rack.type === "entrance" ? gate.entrances : gate.exits).push(rack.rack_name || typeLabel(rack.type));
      gates.set(key, gate);
    }
  }
  return <svg ref={ref} viewBox={detailed ? `-1.2 -1.2 ${w + 1.4} ${h + 1.4}` : `-0.2 -0.2 ${frameWidth + 0.4} ${frameHeight + 0.4}`}
    className={detailed ? "h-full w-full" : "max-h-48 w-full rounded border"}
    style={{ backgroundColor: palette.floor, transform: zoom === 1 ? undefined : `scale(${zoom})`, transformOrigin: "top left" }} role="img" aria-label={t(detailed ? "layDetailedFloorPlan" : "layFloorPlanPreview")}>
    {detailed && <>
      <rect x={-1.2} y={-1.2} width={w + 1.4} height={h + 1.4} fill={palette.floor} />
      <defs><pattern id={gridId} width={1} height={1} patternUnits="userSpaceOnUse">
        <path d="M 1 0 H 0 V 1" fill="none" stroke={customFloor ? floorInk : "#64748b"} strokeOpacity={0.25} strokeWidth={0.04} />
      </pattern></defs>
      <rect x={0} y={0} width={w} height={h} fill={`url(#${gridId})`} />
      {Array.from({ length: w }, (_, x) => <text key={`x-${x}`} x={x + 0.5} y={-0.35} textAnchor="middle" fontSize={0.55} fill={customFloor ? floorInk : "#475569"}>{x + 1}</text>)}
      {Array.from({ length: h }, (_, y) => <text key={`y-${y}`} x={-0.35} y={y + 0.7} textAnchor="end" fontSize={0.55} fill={customFloor ? floorInk : "#475569"}>{y + 1}</text>)}
    </>}
    <rect x={0} y={0} width={w} height={h} fill="none" stroke={customFloor ? floorInk : "#94a3b8"} strokeWidth={0.12} />
    {store.racks.filter((rack) => rack.type !== "entrance" && rack.type !== "exit").flatMap((rack) => rackCells(rack).map(([x, y]) => <rect key={`${rack.id}-${x}-${y}`} x={x + 0.08} y={y + 0.08} width={0.84} height={0.84} rx={0.12} fill={RACK_COLORS[rack.type] ?? "#cbd5e1"} stroke={customFloor ? floorInk : undefined} strokeWidth={0.04}>
      <title>{rack.rack_name || typeLabel(rack.type)}</title>
    </rect>))}
    {areas.map((area, index) => <g key={index}>
      <rect x={area.x} y={area.y} width={area.width} height={area.height} fill={customFloor ? "none" : "#0d948822"}
        stroke={customFloor ? floorInk : "#0f766e"} strokeWidth={0.12} strokeDasharray="0.35 0.2" data-testid={`${detailed ? "detailed" : "reserved"}-area-preview-${index}`}>
        <title>{t("layAreaKeptClear", { area: area.label })}</title>
      </rect>
      <text x={area.x + 0.15} y={area.y + 0.65} fontSize={0.6} fill={customFloor ? floorInk : "#115e59"}>{index + 1}</text>
    </g>)}
    {[...gates.entries()].map(([key, gate]) => {
      const shared = gate.entrances.length > 0 && gate.exits.length > 0;
      const kind = shared ? "shared" : gate.entrances.length ? "entrance" : "exit";
      const label = t(shared ? "layEntranceAndExit" : kind === "entrance" ? "layEntrance" : "layExit");
      return <g key={key} data-gate-kind={kind}>
        <title>{t("layGateTitle", { kind: label, names: [...gate.entrances, ...gate.exits].join(" / "), column: gate.x + 1, row: gate.y + 1 })}</title>
        {shared ? <>
          <rect x={gate.x + 0.08} y={gate.y + 0.08} width={0.84} height={0.42} rx={0.08} fill={RACK_COLORS.entrance} />
          <rect x={gate.x + 0.08} y={gate.y + 0.5} width={0.84} height={0.42} rx={0.08} fill={RACK_COLORS.exit} />
          <text x={gate.x + 0.5} y={gate.y + 0.38} textAnchor="middle" fontSize={0.28} fontWeight="bold" fill="#0f172a">IN</text>
          <text x={gate.x + 0.5} y={gate.y + 0.8} textAnchor="middle" fontSize={0.28} fontWeight="bold" fill="#0f172a">OUT</text>
        </> : <>
          <rect x={gate.x + 0.08} y={gate.y + 0.08} width={0.84} height={0.84} rx={0.12} fill={RACK_COLORS[kind]} />
          <text x={gate.x + 0.5} y={gate.y + 0.61} textAnchor="middle" fontSize={kind === "entrance" ? 0.34 : 0.29} fontWeight="bold" fill="#0f172a">{kind === "entrance" ? "IN" : "OUT"}</text>
        </>}
      </g>;
    })}
  </svg>;
}
