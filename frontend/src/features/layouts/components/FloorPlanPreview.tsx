import { useId, useRef, useState, type Ref } from "react";
import { INTERIOR_DESIGNS } from "@/features/store-viewer/realistic/designThemes";
import type { ReservedArea } from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import type { Store } from "@/shared/types/domain";
import { rackCells } from "@/shared/utils/grid";

const RACK_COLORS: Record<string, string> = {
  fridge: "#38bdf8", shelf: "#f59e0b", counter: "#475569", entrance: "#22c55e", exit: "#22c55e", table: "#a78bfa",
};

export function FloorPlanPreview({ store, areas }: { store: Store; areas: ReservedArea[] }) {
  const [zoom, setZoom] = useState(1);
  const detailedPlan = useRef<SVGSVGElement>(null);
  const tables = store.racks.filter((rack) => rack.type === "table").length;
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
    description.textContent = `${tables} dining tables, ${tables * 4} seats, ${store.racks.filter((rack) => rack.type === "counter").length} checkout counters. Blue: cold; amber: display; green: entry / exit; slate: checkout; purple: seating. ${areas.map((area, index) => `Area ${index + 1}: ${area.label}, ${area.width}×${area.height} cells at column ${area.x + 1}, row ${area.y + 1}.`).join(" ")}`;
    exported.prepend(title, description);
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(exported)], { type: "image/svg+xml;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `twinstore-${store.grid_size.join("x")}-floor-plan.svg`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <div className="space-y-1.5">
    <FloorPlan store={store} areas={areas} />
    <Dialog onOpenChange={(open) => { if (!open) setZoom(1); }}>
      <DialogTrigger asChild><button type="button" className="w-full rounded-md border px-2 py-1 text-xs hover:bg-muted">Expand floor plan</button></DialogTrigger>
      <DialogContent className="flex max-h-[92dvh] flex-col overflow-hidden sm:max-w-[min(92vw,1000px)]" data-testid="expanded-floor-plan-dialog">
        <DialogHeader>
          <DialogTitle>Floor plan details</DialogTitle>
          <DialogDescription>{store.name} · {store.grid_size.join("×")} cells. Columns run left to right; rows run from back to front.</DialogDescription>
        </DialogHeader>
        <div role="group" aria-label="Floor plan controls" className="flex flex-wrap items-center gap-2 text-xs">
          <button type="button" aria-label="Zoom out floor plan" disabled={zoom === 1} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => setZoom((current) => Math.max(1, current - 0.5))}>−</button>
          <span className="min-w-10 text-center">{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label="Zoom in floor plan" disabled={zoom === 4} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => setZoom((current) => Math.min(4, current + 0.5))}>+</button>
          <button type="button" className="rounded border px-2 py-1" onClick={() => setZoom(1)}>Fit floor plan</button>
          <button type="button" className="rounded border px-2 py-1 sm:ml-auto" onClick={downloadPlan}>Download SVG</button>
        </div>
        <div className="h-[min(60dvh,720px)] min-h-40 shrink overflow-auto rounded-md border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          role="region" aria-label="Expanded floor grid" tabIndex={0} data-testid="expanded-floor-scroll">
          <FloorPlan store={store} areas={areas} detailed zoom={zoom} ref={detailedPlan} />
        </div>
        <div className="space-y-1.5 text-xs">
          <p>{store.racks.filter((rack) => rack.slots.length).length} displays · {tables} dining tables · {tables * 4} seats · {store.racks.filter((rack) => rack.type === "counter").length} checkout counters</p>
          <p className="text-muted-foreground">Blue: cold · Amber: display · Green: entry / exit · Slate: checkout · Purple: seating</p>
          {!!areas.length && <ol className="max-h-24 list-decimal space-y-1 overflow-y-auto pl-5" aria-label="Reserved areas in this floor plan">
            {areas.map((area, index) => <li key={index}>{area.label} · {area.width}×{area.height} cells · column {area.x + 1}, row {area.y + 1}</li>)}
          </ol>}
        </div>
      </DialogContent>
    </Dialog>
  </div>;
}

function FloorPlan({ store, areas, detailed = false, zoom = 1, ref }: { store: Store; areas: ReservedArea[]; detailed?: boolean; zoom?: number; ref?: Ref<SVGSVGElement> }) {
  const gridId = useId();
  const [w, h] = store.grid_size;
  const palette = INTERIOR_DESIGNS[store.design_theme ?? "classic"];
  return <svg ref={ref} viewBox={detailed ? `-1.2 -1.2 ${w + 1.4} ${h + 1.4}` : `-0.2 -0.2 ${w + 0.4} ${h + 0.4}`}
    className={detailed ? "h-full w-full" : "max-h-48 w-full rounded border"}
    style={{ backgroundColor: palette.floor, transform: zoom === 1 ? undefined : `scale(${zoom})`, transformOrigin: "top left" }} role="img" aria-label={detailed ? "Detailed floor plan" : "Floor plan preview"}>
    {detailed && <>
      <rect x={-1.2} y={-1.2} width={w + 1.4} height={h + 1.4} fill={palette.floor} />
      <defs><pattern id={gridId} width={1} height={1} patternUnits="userSpaceOnUse">
        <path d="M 1 0 H 0 V 1" fill="none" stroke="#64748b" strokeOpacity={0.25} strokeWidth={0.04} />
      </pattern></defs>
      <rect x={0} y={0} width={w} height={h} fill={`url(#${gridId})`} />
      {Array.from({ length: w }, (_, x) => <text key={`x-${x}`} x={x + 0.5} y={-0.35} textAnchor="middle" fontSize={0.55} fill="#475569">{x + 1}</text>)}
      {Array.from({ length: h }, (_, y) => <text key={`y-${y}`} x={-0.35} y={y + 0.7} textAnchor="end" fontSize={0.55} fill="#475569">{y + 1}</text>)}
    </>}
    <rect x={0} y={0} width={w} height={h} fill="none" stroke="#94a3b8" strokeWidth={0.12} />
    {store.racks.flatMap((rack) => rackCells(rack).map(([x, y]) => <rect key={`${rack.id}-${x}-${y}`} x={x + 0.08} y={y + 0.08} width={0.84} height={0.84} rx={0.12} fill={RACK_COLORS[rack.type] ?? "#cbd5e1"}>
      <title>{rack.rack_name || rack.type}</title>
    </rect>))}
    {areas.map((area, index) => <g key={index}>
      <rect x={area.x} y={area.y} width={area.width} height={area.height} fill="#0d948822"
        stroke="#0f766e" strokeWidth={0.12} strokeDasharray="0.35 0.2" data-testid={`${detailed ? "detailed" : "reserved"}-area-preview-${index}`}>
        <title>{area.label}: kept clear</title>
      </rect>
      <text x={area.x + 0.15} y={area.y + 0.65} fontSize={0.6} fill="#115e59">{index + 1}</text>
    </g>)}
  </svg>;
}
