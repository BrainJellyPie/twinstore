import { cloneElement, useId, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";

import { INTERIOR_DESIGNS } from "@/features/store-viewer/realistic/designThemes";
import * as api from "@/shared/api/client";
import type { Store } from "@/shared/types/domain";
import { cn } from "@/shared/utils/cn";
import { LAYOUT_STYLES, templateRequest, validTemplateChoice, type TemplateChoice } from "../templateOptions";

const RACK_COLORS: Record<string, string> = {
  fridge: "#38bdf8", shelf: "#f59e0b", counter: "#475569", entrance: "#22c55e", exit: "#22c55e",
};
const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";

export function TemplatePicker({ value, onChange }: { value: TemplateChoice; onChange: (v: TemplateChoice) => void }) {
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
            onClick={() => update({ templateId: t.id })}
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
              <FloorPlan store={preview.data} />
              <p className="text-xs text-muted-foreground">{preview.data.grid_size.join("×")} cells · {preview.data.racks.filter((r) => r.slots.length).length} displays · {new Set(preview.data.racks.flatMap((r) => r.slots.flatMap((s) => s.items.map((i) => i.sku)))).size} products</p>
              <p className="text-[10px] text-muted-foreground">Blue: cold · Amber: display · Green: entry · Slate: checkout</p>
            </> : <div className="flex min-h-24 items-center justify-center rounded border bg-muted p-3 text-xs" role="status">
              {!validTemplateChoice(value) ? "Enter a valid grid size." : preview.isError ? "Preview unavailable." : "Updating preview…"}
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
              <Field label="Width (8–40 cells)"><input type="number" className={controlClass} min={8} max={40} step={1} placeholder={String(selected?.grid[0] ?? 12)} value={value.width ?? ""} onChange={(e) => update({ width: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              <Field label="Depth (6–40 cells)"><input type="number" className={controlClass} min={6} max={40} step={1} placeholder={String(selected?.grid[1] ?? 10)} value={value.height ?? ""} onChange={(e) => update({ height: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              <Field label="Front entrance"><select className={controlClass} value={value.entrance ?? "left"} onChange={(e) => update({ entrance: e.target.value as TemplateChoice["entrance"] })}>
                <option value="left">Left</option><option value="center">Center</option><option value="right">Right</option>
              </select></Field>
              <Field label="Checkout counters"><select className={controlClass} value={value.checkouts ?? 1} onChange={(e) => update({ checkouts: Number(e.target.value) })}>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
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
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ seed: value.seed + 1 })}>Shuffle assortment (#{value.seed})</button>
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ style: null, width: null, height: null, density: "balanced", entrance: "left", checkouts: 1, fixture_design: "mixed", design_theme: null, seed: 0 })}>Reset layout options</button>
            </div>
          </div>
        </div>
        <Field label="Additional design brief"><textarea className={controlClass} rows={2} maxLength={2000} value={value.requirements ?? ""} onChange={(e) => update({ requirements: e.target.value })} placeholder="For example: reserve a quiet consultation corner or keep seasonal gifts near the entrance." /></Field>
        <p className="text-[11px] text-muted-foreground">Grid sizes use cells, not measured floor area. Your brief is saved with the layout for further editing; it does not automatically place fixtures. Café and restaurant formats simulate counter purchases.</p>
      </>}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return <div className="space-y-1 text-xs"><label htmlFor={id}>{label}</label>{cloneElement(children, { id })}</div>;
}

function FloorPlan({ store }: { store: Store }) {
  const [w, h] = store.grid_size;
  const palette = INTERIOR_DESIGNS[store.design_theme ?? "classic"];
  return <svg viewBox={`-0.2 -0.2 ${w + 0.4} ${h + 0.4}`} className="max-h-48 w-full rounded border" style={{ backgroundColor: palette.floor }} role="img" aria-label="Floor plan preview">
    <rect x={0} y={0} width={w} height={h} fill="none" stroke="#94a3b8" strokeWidth={0.12} />
    {store.racks.map((r) => <rect key={r.id} x={r.position[0] + 0.08} y={r.position[1] + 0.08} width={0.84} height={0.84} rx={0.12} fill={RACK_COLORS[r.type] ?? "#cbd5e1"}>
      <title>{r.rack_name || r.type}</title>
    </rect>)}
  </svg>;
}
