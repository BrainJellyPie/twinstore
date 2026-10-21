import { cloneElement, useId, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";

import { INTERIOR_DESIGNS } from "@/features/store-viewer/realistic/designThemes";
import * as api from "@/shared/api/client";
import type { Store } from "@/shared/types/domain";
import { rackCells } from "@/shared/utils/grid";
import { cn } from "@/shared/utils/cn";
import { LAYOUT_STYLES, templateRequest, validTemplateChoice, type TemplateChoice } from "../templateOptions";
import { ReservedAreasEditor } from "./ReservedAreasEditor";

const RACK_COLORS: Record<string, string> = {
  fridge: "#38bdf8", shelf: "#f59e0b", counter: "#475569", entrance: "#22c55e", exit: "#22c55e", table: "#a78bfa",
};
const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";

export function TemplatePicker({ value, onChange, onTemplateSelected, budgetCurrency }: {
  value: TemplateChoice;
  onChange: (v: TemplateChoice) => void;
  onTemplateSelected?: (template: api.StoreTemplate) => void;
  budgetCurrency?: string;
}) {
  const [search, setSearch] = useState("");
  const [storeType, setStoreType] = useState("");
  const templatesQuery = useQuery({
    queryKey: ["store-templates"], queryFn: ({ signal }) => api.getStoreTemplates(signal), staleTime: Infinity,
  });
  const templates = templatesQuery.data ?? [];
  const { requirements: _brief, ...previewRequest } = templateRequest(value);
  const preview = useQuery({
    queryKey: ["store-template-preview", previewRequest],
    queryFn: ({ signal }) => api.previewStoreTemplate(previewRequest, signal),
    enabled: validTemplateChoice(value), staleTime: Infinity,
  });
  const selected = templates.find((t) => t.id === value.templateId);
  const filtered = templates.filter((t) => (!storeType || t.store_type === storeType) &&
    `${t.name} ${t.description}`.toLowerCase().includes(search.trim().toLowerCase()));
  const update = (patch: Partial<TemplateChoice>) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <label className="space-y-1 text-xs">Find a store format
          <input className={controlClass} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Pharmacy, café, large store…" />
        </label>
        <label className="space-y-1 text-xs">Store category
          <select className={controlClass} value={storeType} onChange={(e) => setStoreType(e.target.value)}>
            <option value="">All categories</option>
            {[...new Set(templates.map((t) => t.store_type))].sort().map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </label>
      </div>
      {templatesQuery.isPending && <p role="status" className="text-xs">Loading store formats…</p>}
      {templatesQuery.isError && <p role="alert" className="text-xs text-destructive">Could not load store formats. <button type="button" className="underline" onClick={() => void templatesQuery.refetch()}>Retry</button></p>}
      <div className="grid max-h-48 grid-cols-1 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2" aria-label="Store formats">
        {filtered.map((t) => (
          <button key={t.id} type="button" aria-pressed={value.templateId === t.id}
            onClick={() => { update({ templateId: t.id }); onTemplateSelected?.(t); }}
            className={cn("rounded-md border p-2 text-left text-xs transition-colors", value.templateId === t.id ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
            <div className="font-medium">{t.name}</div>
            <div className="text-muted-foreground">{t.grid[0]}×{t.grid[1]} · {t.racks} displays · {t.skus} products by default</div>
          </button>
        ))}
      </div>
      {templatesQuery.isSuccess && !filtered.length && <p className="text-xs text-muted-foreground">No matching formats. Try another search or category.</p>}
      {value.templateId && <>
        <div className="grid gap-3 sm:grid-cols-[170px_1fr]">
          <div className="space-y-1.5">
            {preview.isSuccess && validTemplateChoice(value) ? <>
              <FloorPlan store={preview.data} areas={value.reserved_areas ?? []} />
              <p className="text-xs text-muted-foreground">{preview.data.grid_size.join("×")} cells · {preview.data.racks.filter((r) => r.slots.length).length} displays · {new Set(preview.data.racks.flatMap((r) => r.slots.flatMap((s) => s.items.map((i) => i.sku)))).size} products</p>
              <p className="text-xs text-muted-foreground">{preview.data.racks.filter((r) => r.type === "table").length} dining tables · {preview.data.racks.filter((r) => r.type === "table").length * 4} seats</p>
              <p className="text-[10px] text-muted-foreground">Blue: cold · Amber: display · Green: entry · Slate: checkout · Purple: seating</p>
            </> : <div className="flex min-h-24 items-center justify-center rounded border bg-muted p-3 text-xs" role="status">
              {!validTemplateChoice(value) ? "Enter a valid grid size and reserved-area values." : preview.isError ? "Preview unavailable." : "Updating preview…"}
            </div>}
            {preview.isError && <p role="alert" className="text-xs text-destructive">{preview.error.message} <button type="button" className="underline" onClick={() => void preview.refetch()}>Retry</button></p>}
          </div>
          <div className="space-y-2">
            <p className="text-xs"><strong>{selected?.name}</strong></p>
            <p className="text-xs text-muted-foreground">{selected?.description}</p>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Layout pattern"><select className={controlClass} value={value.style ?? ""} onChange={(e) => update({ style: (e.target.value || null) as TemplateChoice["style"] })}>
                <option value="">Format default{selected ? ` (${LAYOUT_STYLES.find(([id]) => id === selected.default_style)?.[1]})` : ""}</option>
                {LAYOUT_STYLES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select></Field>
              <Field label="Display density"><select className={controlClass} value={value.density ?? "balanced"} onChange={(e) => update({ density: e.target.value as TemplateChoice["density"] })}>
                <option value="spacious">Spacious aisles</option><option value="balanced">Balanced</option><option value="dense">High capacity</option>
              </select></Field>
              <div className="col-span-2"><Field label="Interior shelf direction"><select className={controlClass} value={value.shelf_direction ?? "horizontal"}
                disabled={(value.style ?? selected?.default_style) === "perimeter"}
                onChange={(e) => update({ shelf_direction: e.target.value as TemplateChoice["shelf_direction"] })}>
                <option value="horizontal">Left to right</option><option value="vertical">Front to back</option>
              </select></Field></div>
              <Field label="Width (8–40 cells)"><input type="number" className={controlClass} min={8} max={40} step={1} placeholder={String(selected?.grid[0] ?? 12)} value={value.width ?? ""} onChange={(e) => update({ width: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              <Field label="Depth (6–40 cells)"><input type="number" className={controlClass} min={6} max={40} step={1} placeholder={String(selected?.grid[1] ?? 10)} value={value.height ?? ""} onChange={(e) => update({ height: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              <Field label="Front entrance"><select className={controlClass} value={value.entrance ?? "left"} onChange={(e) => update({ entrance: e.target.value as TemplateChoice["entrance"] })}>
                <option value="left">Left</option><option value="center">Center</option><option value="right">Right</option>
              </select></Field>
              <Field label="Checkout counters"><select className={controlClass} value={value.checkouts ?? 1} onChange={(e) => update({ checkouts: Number(e.target.value) })}>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
              </select></Field>
              <Field label="Checkout placement"><select className={controlClass} value={value.checkout_placement ?? "auto"}
                onChange={(e) => update({ checkout_placement: e.target.value as TemplateChoice["checkout_placement"] })}>
                <option value="auto">Format default{selected?.default_checkout_placement === "near_entrance" ? " (near entrance)" : selected?.default_checkout_placement === "away_from_entrance" ? " (away from entrance)" : " (front counters)"}</option><option value="near_entrance">Near the entrance</option>
                <option value="away_from_entrance">Away from the entrance</option>
              </select></Field>
              <Field label="Interior design (Realistic view)"><select className={controlClass} value={value.design_theme ?? ""} onChange={(e) => update({ design_theme: (e.target.value || null) as TemplateChoice["design_theme"] })}>
                <option value="">Format default{selected ? ` (${INTERIOR_DESIGNS[selected.default_design]?.label ?? "Classic retail"})` : ""}</option>
                {Object.entries(INTERIOR_DESIGNS).map(([id, palette]) => <option key={id} value={id}>{palette.label}</option>)}
              </select></Field>
              <Field label="Shelf design"><select className={controlClass} value={value.fixture_design ?? "mixed"} onChange={(e) => update({ fixture_design: e.target.value as TemplateChoice["fixture_design"] })}>
                <option value="mixed">Mixed displays</option><option value="a">Open rack A</option><option value="b">Open rack B</option><option value="c">Wall-end rack C</option>
              </select></Field>
              <Field label="Price currency"><select className={controlClass} value={value.currency} onChange={(e) => update({ currency: e.target.value })}>
                <option value="USD">USD · $</option><option value="KRW">KRW · ₩</option><option value="JPY">JPY · ¥</option>
              </select></Field>
              <Field label="Dining tables (4 seats each)"><select className={controlClass} value={value.dining_tables ?? ""} onChange={(e) => update({ dining_tables: e.target.value === "" ? null : Number(e.target.value) })}>
                <option value="">Format default ({selected?.default_dining_tables ?? 0}, sized to fit)</option>
                {Array.from({ length: 13 }, (_, n) => <option key={n} value={n}>{n === 0 ? "No seating" : `${n} tables · ${n * 4} seats`}</option>)}
              </select></Field>
              <Field label="Seating starts near"><select className={controlClass} value={value.seating_zone ?? "auto"}
                disabled={(value.dining_tables ?? selected?.default_dining_tables ?? 0) === 0}
                onChange={(e) => update({ seating_zone: e.target.value as TemplateChoice["seating_zone"] })}>
                <option value="auto">Format default{selected?.default_seating_zone && selected.default_seating_zone !== "auto" ? ` (${selected.default_seating_zone})` : ""}</option><option value="front">Front / entrance side</option>
                <option value="back">Back wall</option><option value="left">Left side</option>
                <option value="right">Right side</option><option value="center">Center</option>
              </select></Field>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ seed: value.seed + 1 })}>Shuffle assortment (#{value.seed})</button>
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ style: null, width: null, height: null, density: "balanced", shelf_direction: "horizontal", entrance: "left", checkouts: 1, checkout_placement: "auto", fixture_design: "mixed", design_theme: null, dining_tables: null, seating_zone: "auto", reserved_areas: [], seed: 0 })}>Reset layout options</button>
            </div>
          </div>
        </div>
        <ReservedAreasEditor areas={value.reserved_areas ?? []} onChange={(reserved_areas) => update({ reserved_areas })} />
        <Field label="Additional design brief"><textarea className={controlClass} rows={2} maxLength={2000} value={value.requirements ?? ""} onChange={(e) => update({ requirements: e.target.value })} placeholder="For example: use warm task lighting in the consultation corner or seasonal signs near the entrance." /></Field>
        {budgetCurrency && value.currency !== budgetCurrency && <p role="status" className="text-xs text-amber-700 dark:text-amber-300">This project uses {budgetCurrency} shopper budgets. You can preview and save this {value.currency} layout; to simulate it, create a new {value.currency} project or use {budgetCurrency} here. Existing budgets are not converted.</p>}
        <p className="text-[11px] text-muted-foreground">Grid sizes use cells, not measured floor area. Shelf direction applies to interior rows; perimeter fixtures stay on the walls. Your brief is saved with the layout for further editing; it does not automatically place fixtures. Seating starts in the chosen area and extends into neighboring space as the count increases. Dining tables reserve floor space and show seating; table service and dining time are not simulated.</p>
      </>}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return <div className="space-y-1 text-xs"><label htmlFor={id}>{label}</label>{cloneElement(children, { id })}</div>;
}

function FloorPlan({ store, areas }: { store: Store; areas: api.ReservedArea[] }) {
  const [w, h] = store.grid_size;
  const palette = INTERIOR_DESIGNS[store.design_theme ?? "classic"];
  return <svg viewBox={`-0.2 -0.2 ${w + 0.4} ${h + 0.4}`} className="max-h-48 w-full rounded border" style={{ backgroundColor: palette.floor }} role="img" aria-label="Floor plan preview">
    <rect x={0} y={0} width={w} height={h} fill="none" stroke="#94a3b8" strokeWidth={0.12} />
    {store.racks.flatMap((r) => rackCells(r).map(([x, y]) => <rect key={`${r.id}-${x}-${y}`} x={x + 0.08} y={y + 0.08} width={0.84} height={0.84} rx={0.12} fill={RACK_COLORS[r.type] ?? "#cbd5e1"}>
      <title>{r.rack_name || r.type}</title>
    </rect>))}
    {areas.map((area, index) => <g key={index}>
      <rect x={area.x} y={area.y} width={area.width} height={area.height} fill="#0d948822"
        stroke="#0f766e" strokeWidth={0.12} strokeDasharray="0.35 0.2" data-testid={`reserved-area-preview-${index}`}>
        <title>{area.label}: kept clear</title>
      </rect>
      <text x={area.x + 0.15} y={area.y + 0.65} fontSize={0.6} fill="#115e59">{index + 1}</text>
    </g>)}
  </svg>;
}
