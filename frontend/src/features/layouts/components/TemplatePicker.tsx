import { ChevronDown } from "lucide-react";
import { useI18n } from "@/shared/i18n/i18n";
import { rackDiningSeats } from "@/shared/utils/dining";
import { cloneElement, useId, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";

import { INTERIOR_DESIGNS } from "@/features/store-viewer/realistic/designThemes";
import * as api from "@/shared/api/client";
import { cn } from "@/shared/utils/cn";
import { LAYOUT_PRIORITIES, LAYOUT_STYLES, resolveFloorSize, resolveOperatingHours, templateRequest, validTemplateChoice, type FloorSize, type OperatingHours, type TemplateChoice } from "../templateOptions";
import { ReservedAreasEditor } from "./ReservedAreasEditor";
import { FloorPlanPreview } from "./FloorPlanPreview";
import { GenerationOptionsFile } from "./GenerationOptionsFile";
import { CompareFloorPlans } from "./CompareFloorPlans";

const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function TemplatePicker({ value, onChange, onTemplateSelected, budgetCurrency, onApplyDesignToAll, onApplyCurrencyToAll, onApplyHoursToAll, onApplySizeToAll, sharedDesign, sharedCurrency, sharedHours = false, sharedSize = false, showOperatingHours = true, defaultCustomizationOpen = true }: {
  value: TemplateChoice;
  onChange: (v: TemplateChoice) => void;
  onTemplateSelected?: (template: api.StoreTemplate) => void;
  budgetCurrency?: string;
  onApplyDesignToAll?: (design: NonNullable<TemplateChoice["design_theme"]>) => void;
  onApplyCurrencyToAll?: (currency: string) => void;
  onApplyHoursToAll?: (hours: OperatingHours) => void;
  onApplySizeToAll?: (size: FloorSize) => void;
  sharedDesign?: NonNullable<TemplateChoice["design_theme"]>;
  sharedCurrency?: string;
  sharedHours?: boolean;
  sharedSize?: boolean;
  showOperatingHours?: boolean;
  defaultCustomizationOpen?: boolean;
}) {
  const { t } = useI18n();
  const customizationId = useId();
  const [customizationOpen, setCustomizationOpen] = useState(defaultCustomizationOpen);
  const [search, setSearch] = useState("");
  const [storeType, setStoreType] = useState("");
  const [size, setSize] = useState("all");
  const [seating, setSeating] = useState("all");
  const [sort, setSort] = useState("default");
  const [priorityId, setPriorityId] = useState(LAYOUT_PRIORITIES[0]!.id);
  const priority = LAYOUT_PRIORITIES.find((choice) => choice.id === priorityId) ?? LAYOUT_PRIORITIES[0]!;
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
  const tableMix = value.table_mix;
  const tableCount = tableMix ? tableMix.two_seat + tableMix.four_seat + tableMix.six_seat : value.dining_tables ?? selected?.default_dining_tables ?? 0;
  const mixStartingCount = value.dining_tables ?? (preview.isSuccess ? preview.data.racks.filter((rack) => rack.type === "table").length : tableCount);
  const closedDays = value.closed_days ?? selected?.closed_days ?? [];
  const operatingHours = resolveOperatingHours(value, selected);
  const floorSize = resolveFloorSize(value, selected);
  const activeDesign = value.design_theme ?? selected?.default_design;
  const categories = selected?.categories ?? [];
  const excluded = new Set(value.excluded_categories ?? []);
  const includedCount = categories.filter((category) => !excluded.has(category.id)).length;
  const densityGap = { spacious: 3, balanced: 2, dense: 1 }[value.density ?? "balanced"];
  const densityRun = { spacious: 3, balanced: 4, dense: 6 }[value.density ?? "balanced"];
  const sideGates = value.gate_wall === "left" || value.gate_wall === "right";
  const sharedExit = (value.exit_position ?? "shared") === "shared";
  const exitWall = sharedExit ? value.gate_wall : value.exit_wall ?? value.gate_wall;
  const sideExit = exitWall === "left" || exitWall === "right";
  const terms = search.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim().split(/\s+/).filter(Boolean);
  const filtered = templates.filter((t) => {
    if (storeType && t.store_type !== storeType) return false;
    const cells = t.grid[0] * t.grid[1];
    if (size === "compact" && cells > 144) return false;
    if (size === "medium" && (cells <= 144 || cells > 480)) return false;
    if (size === "large" && cells <= 480) return false;
    if (seating === "with" && t.default_dining_tables === 0) return false;
    if (seating === "without" && t.default_dining_tables > 0) return false;
    const text = `${t.name} ${t.description} ${t.store_type} ${t.id.replace(/_/g, " ")}`.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
    return terms.every((term) => text.includes(term));
  }).sort((a, b) => {
    if (sort === "name") return a.name.localeCompare(b.name);
    if (sort === "smallest") return a.grid[0] * a.grid[1] - b.grid[0] * b.grid[1] || a.name.localeCompare(b.name);
    if (sort === "largest") return b.grid[0] * b.grid[1] - a.grid[0] * a.grid[1] || a.name.localeCompare(b.name);
    if (sort === "seats") return b.default_dining_tables - a.default_dining_tables || a.name.localeCompare(b.name);
    return 0;
  });
  const update = (patch: Partial<TemplateChoice>) => onChange({ ...value, ...patch });
  function updateTableMix(patch: Partial<api.DiningTableMix>) {
    const mix = { two_seat: 0, four_seat: 0, six_seat: 0, ...tableMix, ...patch };
    update({ table_mix: mix, dining_tables: mix.two_seat + mix.four_seat + mix.six_seat });
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
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
      <details className="space-y-2 rounded border px-2 py-1.5 text-xs">
        <summary className="cursor-pointer">More format filters</summary>
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label="Default floor size"><select className={controlClass} value={size} onChange={(e) => setSize(e.target.value)}>
            <option value="all">Any size</option><option value="compact">Compact · up to 144 cells</option>
            <option value="medium">Medium · 145–480 cells</option><option value="large">Large · over 480 cells</option>
          </select></Field>
          <Field label="Default seating"><select className={controlClass} value={seating} onChange={(e) => setSeating(e.target.value)}>
            <option value="all">Any seating</option><option value="with">With dining tables</option><option value="without">Without dining tables</option>
          </select></Field>
          <Field label="Sort formats"><select className={controlClass} value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="default">Format order</option><option value="name">Name · A–Z</option>
            <option value="smallest">Smallest floor first</option><option value="largest">Largest floor first</option><option value="seats">Most seats first</option>
          </select></Field>
        </div>
        <p className="text-muted-foreground">Size and seating describe each starting layout. You can customize them after selecting a format.</p>
      </details>
      {templatesQuery.isSuccess && <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <p className="text-muted-foreground" aria-live="polite">{filtered.length} of {templates.length} formats</p>
        {(search || storeType || size !== "all" || seating !== "all" || sort !== "default") && <button type="button" className="underline"
          onClick={() => { setSearch(""); setStoreType(""); setSize("all"); setSeating("all"); setSort("default"); }}>Clear format filters</button>}
      </div>}
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
        <div className="grid gap-3 sm:grid-cols-[170px_minmax(0,1fr)]">
          <div className="space-y-1.5">
            {preview.isSuccess && validTemplateChoice(value) ? <>
              <FloorPlanPreview store={preview.data} areas={value.reserved_areas ?? []} />
              <CompareFloorPlans store={preview.data} areas={value.reserved_areas ?? []} templateId={value.templateId} currency={value.currency} />
              <p className="text-xs text-muted-foreground">{preview.data.grid_size.join("×")} cells · {preview.data.racks.filter((r) => r.slots.length).length} displays · {new Set(preview.data.racks.flatMap((r) => r.slots.flatMap((s) => s.items.map((i) => i.sku)))).size} products</p>
              <p className="text-xs text-muted-foreground">{preview.data.racks.filter((r) => r.type === "table").length} dining tables · {preview.data.racks.reduce((sum, rack) => sum + rackDiningSeats(rack), 0)} seats</p>
              <p className="text-xs text-muted-foreground">{preview.data.racks.filter((r) => r.type === "counter").length} checkout counters</p>
              <p className="text-[10px] text-muted-foreground">Blue: cold · Amber: display · Green IN: entrance · Rose OUT: exit · Split IN/OUT: shared gate · Slate: checkout · Purple: seating</p>
            </> : <div className="flex min-h-24 items-center justify-center rounded border bg-muted p-3 text-xs" role="status">
              {!validTemplateChoice(value) ? "Enter valid grid dimensions, product and table counts, operating hours and reserved-area values. Keep at least one open weekday." : preview.isError ? "Preview unavailable." : "Updating preview…"}
            </div>}
            {preview.isError && <p role="alert" className="text-xs text-destructive">{preview.error.message} <button type="button" className="underline" onClick={() => void preview.refetch()}>Retry</button></p>}
          </div>
          <div className="space-y-2">
            <p className="text-xs"><strong>{selected?.name}</strong></p>
            <p className="text-xs text-muted-foreground">{selected?.description}</p>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Width (8–40 cells)"><input type="number" className={controlClass} min={8} max={40} step={1} placeholder={String(selected?.grid[0] ?? 12)} value={value.width ?? ""} onChange={(e) => update({ width: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              <Field label="Depth (6–40 cells)"><input type="number" className={controlClass} min={6} max={40} step={1} placeholder={String(selected?.grid[1] ?? 10)} value={value.height ?? ""} onChange={(e) => update({ height: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              {onApplySizeToAll && <div className="col-span-2 space-y-1 text-xs">
                <button type="button" className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-50" disabled={!floorSize || sharedSize}
                  onClick={() => { if (floorSize) onApplySizeToAll(floorSize); }}>{floorSize && sharedSize ? "Size used on all floors" : "Apply size to all floors"}</button>
                <p className="text-muted-foreground">{floorSize
                  ? `Applies ${floorSize.width}×${floorSize.height} cells to every floor and opens the floor review. Check that seating, counters and reserved areas still fit.`
                  : "Enter a valid width and depth before applying the size to every floor."}</p>
              </div>}
              <div className="col-span-2 space-y-1"><Field label="Price currency"><select className={controlClass} value={value.currency} onChange={(e) => update({ currency: e.target.value })}>
                <option value="USD">USD · $</option><option value="KRW">KRW · ₩</option><option value="JPY">JPY · ¥</option>
              </select></Field>
                {onApplyCurrencyToAll && <button type="button" className="text-left text-[10px] underline disabled:opacity-50" disabled={sharedCurrency === value.currency}
                  onClick={() => onApplyCurrencyToAll(value.currency)}>{sharedCurrency === value.currency ? "Currency used on all floors" : "Apply currency to all floors"}</button>}
              </div>
            </div>
            <button type="button" className="flex w-full items-center justify-between gap-2 rounded-md border p-2 text-left text-xs font-medium hover:bg-muted"
              aria-expanded={customizationOpen} aria-controls={`${customizationId}-main ${customizationId}-more`}
              onClick={() => setCustomizationOpen((open) => !open)}>
              {t(customizationOpen ? "hideLayoutCustomization" : "customizeLayout")}
              <ChevronDown className={cn("size-3.5 shrink-0 transition-transform", customizationOpen && "rotate-180")} aria-hidden />
            </button>
            {!customizationOpen && <p className="text-[11px] text-muted-foreground">{t("layoutCustomizationHint")}</p>}
            {!customizationOpen && !validTemplateChoice(value) && <p role="alert" className="text-xs text-destructive">{t("layoutCustomizationError")}</p>}
            <div id={`${customizationId}-main`} hidden={!customizationOpen} className="space-y-2">
              <GenerationOptionsFile kind="layout" value={value} canExport={validTemplateChoice(value) && preview.isSuccess} onChange={(choice) => {
                onChange(choice);
                setSearch(""); setStoreType(""); setSize("all"); setSeating("all"); setSort("default");
                const imported = templates.find((template) => template.id === choice.templateId);
                if (imported) onTemplateSelected?.(imported);
              }} />
            <details className="space-y-2 rounded border p-2 text-xs">
              <summary className="cursor-pointer">Apply a layout priority</summary>
              <Field label="Layout priority"><select className={controlClass} value={priority.id} onChange={(event) => setPriorityId(event.target.value)}>
                {LAYOUT_PRIORITIES.map((choice) => <option key={choice.id} value={choice.id}>{choice.name}</option>)}
              </select></Field>
              <p>{priority.description}</p>
              <p className="text-muted-foreground">Apply these settings to this floor, then review the preview. Dimensions, product settings, design, operating hours and reserved areas stay as set. Space limits still apply.</p>
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ ...priority.options,
                ...(priority.options.dining_tables === 0 && tableMix ? { table_mix: { two_seat: 0, four_seat: 0, six_seat: 0 } } : {}),
                ...(priority.checkoutAtEntrance ? { checkout_wall: value.gate_wall ?? "front" } : {}) })}>Apply priority</button>
            </details>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Layout pattern"><select className={controlClass} value={value.style ?? ""} onChange={(e) => update({ style: (e.target.value || null) as TemplateChoice["style"] })}>
                <option value="">Format default{selected ? ` (${LAYOUT_STYLES.find(([id]) => id === selected.default_style)?.[1]})` : ""}</option>
                {LAYOUT_STYLES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select></Field>
              <Field label="Display density"><select className={controlClass} value={value.density ?? "balanced"} onChange={(e) => update({ density: e.target.value as TemplateChoice["density"] })}>
                <option value="spacious">Spacious aisles</option><option value="balanced">Balanced</option><option value="dense">High capacity</option>
              </select></Field>
              <Field label="Interior shelf direction"><select className={controlClass} value={value.shelf_direction ?? "horizontal"}
                disabled={(value.style ?? selected?.default_style) === "perimeter"}
                onChange={(e) => update({ shelf_direction: e.target.value as TemplateChoice["shelf_direction"] })}>
                <option value="horizontal">Left to right</option><option value="vertical">Front to back</option>
              </select></Field>
              <Field label="Interior aisle gap"><select className={controlClass} value={value.aisle_width ?? ""}
                disabled={(value.style ?? selected?.default_style) === "perimeter"}
                onChange={(e) => update({ aisle_width: e.target.value === "" ? null : Number(e.target.value) })}>
                <option value="">Density default ({densityGap} {densityGap === 1 ? "cell" : "cells"})</option>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} {n === 1 ? "cell" : "cells"}</option>)}
              </select></Field>
              {(value.style ?? selected?.default_style) === "cross" && <p className="col-span-2 text-[11px] text-muted-foreground">Central cross aisles stay clear of shelves and tables. The aisle gap sets both path widths and can reduce seating capacity.</p>}
              <div className="col-span-2 space-y-1"><Field label="Maximum shelf run"><select className={controlClass} value={value.max_shelf_run ?? ""}
                disabled={(value.style ?? selected?.default_style) === "perimeter"}
                onChange={(e) => update({ max_shelf_run: e.target.value === "" ? null : Number(e.target.value) })}>
                <option value="">Density default ({densityRun} cells)</option>
                {Array.from({ length: 8 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n} display {n === 1 ? "cell" : "cells"}</option>)}
              </select></Field>
                <p className="text-[10px] text-muted-foreground">Maximum adjacent display cells before a cross aisle. Patterns and reserved areas may shorten each run.</p>
              </div>
              <Field label="Entrance wall"><select className={controlClass} value={value.gate_wall ?? "front"} onChange={(e) => update({ gate_wall: e.target.value as TemplateChoice["gate_wall"] })}>
                <option value="front">Front wall</option><option value="back">Back wall</option><option value="left">Left wall</option><option value="right">Right wall</option>
              </select></Field>
              <Field label="Entrance position"><select className={controlClass} value={value.entrance ?? "left"} onChange={(e) => update({ entrance: e.target.value as TemplateChoice["entrance"] })}>
                <option value="left">{sideGates ? "Near back" : "Left"}</option><option value="center">Center</option><option value="right">{sideGates ? "Near front" : "Right"}</option>
              </select></Field>
              <Field label="Exit position"><select className={controlClass} value={value.exit_position ?? "shared"} onChange={(e) => update({ exit_position: e.target.value as TemplateChoice["exit_position"], ...(e.target.value === "shared" ? { exit_wall: null } : {}) })}>
                <option value="shared">Share entrance</option><option value="left">{sideExit ? "Near back" : "Left"}</option><option value="center">Center</option><option value="right">{sideExit ? "Near front" : "Right"}</option>
              </select></Field>
              <Field label="Exit wall"><select className={controlClass} value={sharedExit ? "" : value.exit_wall ?? ""} disabled={sharedExit}
                onChange={(e) => update({ exit_wall: e.target.value === "" ? null : e.target.value as TemplateChoice["exit_wall"] })}>
                <option value="">Entrance wall</option><option value="front">Front wall</option><option value="back">Back wall</option><option value="left">Left wall</option><option value="right">Right wall</option>
              </select></Field>
              <p className="col-span-2 text-[10px] text-muted-foreground">Choose a separate exit position to place it on another wall. Shared gates follow the entrance. Back and side gates stay one cell away from corners; center uses the wall midpoint.</p>
              <div className="col-span-2 sm:col-span-1"><Field label="Checkout counters"><select className={controlClass} value={value.checkouts ?? ""} onChange={(e) => update({ checkouts: e.target.value === "" ? null : Number(e.target.value) })}>
                <option value="">Format default ({selected?.default_checkouts ?? 1}, sized to fit)</option>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
              </select></Field></div>
              <Field label="Checkout wall"><select className={controlClass} value={value.checkout_wall ?? "front"}
                onChange={(e) => update({ checkout_wall: e.target.value as TemplateChoice["checkout_wall"] })}>
                <option value="front">Front wall</option><option value="back">Back wall</option>
                <option value="left">Left wall</option><option value="right">Right wall</option>
              </select></Field>
              <div className="col-span-2 sm:col-span-1"><Field label="Checkout placement"><select className={controlClass} value={value.checkout_placement ?? "auto"}
                onChange={(e) => update({ checkout_placement: e.target.value as TemplateChoice["checkout_placement"] })}>
                <option value="auto">Format default{selected?.default_checkout_placement === "near_entrance" ? " (near entrance)" : selected?.default_checkout_placement === "away_from_entrance" ? " (away from entrance)" : " (wall order)"}</option><option value="near_entrance">Near the entrance</option>
                <option value="away_from_entrance">Away from the entrance</option>
              </select></Field></div>
              <Field label="Space beside counters"><select className={controlClass} value={value.checkout_clearance ?? 0}
                onChange={(event) => update({ checkout_clearance: Number(event.target.value) })}>
                <option value={0}>0 · Adjacent</option><option value={1}>1 cell</option><option value={2}>2 cells</option><option value={3}>3 cells</option>
              </select></Field>
              <p className="col-span-2 text-[10px] text-muted-foreground">Leave 0–3 cells beside each counter along its wall. These cells stay clear of stock; other wall displays use the remaining space. Format-default counter counts adapt to fit; explicit counts must fit.</p>
              <div className="col-span-2 space-y-1 sm:col-span-1"><Field label="Interior design (Realistic view)"><select className={controlClass} value={value.design_theme ?? ""} onChange={(e) => update({ design_theme: (e.target.value || null) as TemplateChoice["design_theme"] })}>
                <option value="">Format default{selected ? ` (${INTERIOR_DESIGNS[selected.default_design]?.label ?? "Classic retail"})` : ""}</option>
                {Object.entries(INTERIOR_DESIGNS).map(([id, palette]) => <option key={id} value={id}>{palette.label}</option>)}
              </select></Field>
                {onApplyDesignToAll && <button type="button" className="text-left text-[10px] underline disabled:opacity-50" disabled={!activeDesign || sharedDesign === activeDesign}
                  onClick={() => { if (activeDesign) onApplyDesignToAll(activeDesign); }}>{activeDesign && sharedDesign === activeDesign ? "Design used on all floors" : "Apply design to all floors"}</button>}
              </div>
              <Field label="Shelf design"><select className={controlClass} value={value.fixture_design ?? "mixed"} onChange={(e) => update({ fixture_design: e.target.value as TemplateChoice["fixture_design"] })}>
                <option value="mixed">Mixed displays</option><option value="a">Open rack A</option><option value="b">Open rack B</option><option value="c">Wall-end rack C</option>
              </select></Field>
              <div className="space-y-1"><Field label={tableMix ? "Dining tables (mixed sizes)" : `Dining tables (${value.dining_seats ?? 4} seats each)`}><input type="number" min={0} max={48} step={1} className={controlClass}
                disabled={!!tableMix} placeholder={`Format default (${selected?.default_dining_tables ?? 0})`} value={tableMix ? tableCount : value.dining_tables ?? ""}
                onChange={(e) => update({ dining_tables: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
                <p className="text-[10px] text-muted-foreground">{tableMix ? "Total from the mixed table counts below." : "0–48 tables; blank uses the format default, sized to fit."}</p>
              </div>
              <div className="space-y-1"><Field label="Seats per table"><select className={controlClass} value={value.dining_seats ?? 4}
                disabled={!!tableMix || tableCount === 0}
                onChange={(e) => update({ dining_seats: Number(e.target.value) as 2 | 4 | 6 })}>
                <option value={2}>2 seats</option><option value={4}>4 seats</option><option value={6}>6 seats</option>
              </select></Field><p className="text-[10px] text-muted-foreground">{tableMix ? "Choose each size in Mixed table sizes below." : `${value.table_rotation === 90 ? `2×${(value.dining_seats ?? 4) / 2}` : `${(value.dining_seats ?? 4) / 2}×2`} cells, including chairs.`}</p></div>
              <Field label="Table rotation"><select className={controlClass} value={value.table_rotation ?? 0}
                disabled={tableCount === 0}
                onChange={(e) => update({ table_rotation: Number(e.target.value) as 0 | 90 })}>
                <option value={0}>0°</option><option value={90}>90°</option>
              </select></Field>
              <div className="col-span-2 sm:col-span-1"><Field label="Seating starts near"><select className={controlClass} value={value.seating_zone ?? "auto"}
                disabled={tableCount === 0}
                onChange={(e) => update({ seating_zone: e.target.value as TemplateChoice["seating_zone"] })}>
                <option value="auto">Format default{selected?.default_seating_zone && selected.default_seating_zone !== "auto" ? ` (${selected.default_seating_zone})` : ""}</option><option value="front">Front edge</option>
                <option value="back">Back wall</option><option value="left">Left side</option>
                <option value="right">Right side</option><option value="center">Center</option>
              </select></Field></div>
              <div className="col-span-2 sm:col-span-1"><Field label="Space around dining tables"><select className={controlClass} value={value.table_clearance ?? 1}
                disabled={tableCount === 0}
                onChange={(e) => update({ table_clearance: Number(e.target.value) })}>
                <option value={1}>1 cell · Standard</option><option value={2}>2 cells · More room</option><option value={3}>3 cells · Open seating</option>
              </select></Field></div>
            </div>
            <details className="space-y-2 rounded border p-2 text-xs">
              <summary className="cursor-pointer">Mixed table sizes{tableMix ? ` · ${tableCount} tables` : ""}</summary>
              <label className="flex items-center gap-2"><input type="checkbox" checked={!!tableMix}
                onChange={(event) => event.target.checked
                  ? updateTableMix({ [value.dining_seats === 2 ? "two_seat" : value.dining_seats === 6 ? "six_seat" : "four_seat"]: mixStartingCount })
                  : update({ table_mix: null, dining_tables: tableCount })} />Use mixed table sizes</label>
              {tableMix && <div className="grid grid-cols-3 gap-2">
                {([["two_seat", "2-seat tables"], ["four_seat", "4-seat tables"], ["six_seat", "6-seat tables"]] as const).map(([key, label]) => <Field key={key} label={label}>
                  <input type="number" min={0} max={48} step={1} className={controlClass} value={tableMix[key]}
                    onChange={(event) => updateTableMix({ [key]: Number(event.target.value) })} />
                </Field>)}
              </div>}
              <p className="text-muted-foreground">Set up to 48 tables in total. Larger groups are placed first, then smaller groups fill available space. Rotation, seating area and clearance apply to every size. If the mix cannot fit, adjust the counts or layout.</p>
            </details>
            <div className="flex flex-wrap gap-2 text-xs">
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ seed: value.seed + 1 })}>Shuffle assortment (#{value.seed})</button>
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ style: null, width: null, height: null, density: "balanced", aisle_width: null, max_shelf_run: null, shelf_direction: "horizontal", entrance: "left", gate_wall: "front", exit_position: "shared", exit_wall: null, checkouts: null, checkout_placement: "auto", checkout_wall: "front", checkout_clearance: 0, fixture_design: "mixed", design_theme: null, dining_tables: null, dining_seats: 4, table_mix: null, table_rotation: 0, table_clearance: 1, seating_zone: "auto", reserved_areas: [], excluded_categories: [], products_per_category: null, open_hour: null, close_hour: null, closed_days: null, seed: 0 })}>Reset layout options</button>
            </div>
            </div>
          </div>
        </div>
        <div id={`${customizationId}-more`} hidden={!customizationOpen} className="space-y-3">
        {showOperatingHours && <details className="space-y-2 rounded border p-2 text-xs">
          <summary className="cursor-pointer">Operating hours · {7 - closedDays.length} open days</summary>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Opening hour (0–23)"><input type="number" min={0} max={23} step={1} className={controlClass}
              placeholder={String(selected?.open_hours[0] ?? 0)} value={value.open_hour ?? ""}
              onChange={(event) => update({ open_hour: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
            <Field label="Closing hour (1–24)"><input type="number" min={1} max={24} step={1} className={controlClass}
              placeholder={String(selected?.open_hours[1] ?? 24)} value={value.close_hour ?? ""}
              onChange={(event) => update({ close_hour: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
          </div>
          <p className="text-muted-foreground">Blank hours use the format default. Use 0–24 for all-day opening. Closing must be later than opening; overnight hours are not supported.</p>
          <fieldset className="space-y-2">
            <legend>Open weekdays</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {WEEKDAYS.map((day, index) => <label key={day} className="flex items-center gap-1.5">
                <input type="checkbox" checked={!closedDays.includes(index + 1)} disabled={closedDays.length === 6 && !closedDays.includes(index + 1)}
                  onChange={(event) => update({ closed_days: event.target.checked
                    ? closedDays.filter((value) => value !== index + 1)
                    : [...closedDays, index + 1].sort((a, b) => a - b) })} />{day}
              </label>)}
            </div>
          </fieldset>
          <p className="text-muted-foreground">Keep at least one open weekday. These hours apply to every open day of this floor.</p>
          <button type="button" className="underline" onClick={() => update({ open_hour: null, close_hour: null, closed_days: null })}>Use format operating hours</button>
          {onApplyHoursToAll && <div className="space-y-1 border-t pt-2">
            <button type="button" className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-50"
              disabled={!operatingHours || sharedHours} onClick={() => { if (operatingHours) onApplyHoursToAll(operatingHours); }}>
              {operatingHours && sharedHours ? "Operating hours used on all floors" : "Apply operating hours to all floors"}
            </button>
            <p className="text-muted-foreground">{operatingHours
              ? `Applies ${String(operatingHours.open_hour).padStart(2, "0")}:00–${String(operatingHours.close_hour).padStart(2, "0")}:00 and ${7 - operatingHours.closed_days.length} open days to every floor. Each floor can be changed afterward.`
              : "Choose valid hours with at least one open weekday before applying them to every floor."}</p>
          </div>}
        </details>}
        {categories.length > 0 && <details className="space-y-2 rounded border p-2 text-xs">
          <summary className="cursor-pointer">Product categories · {includedCount} of {categories.length} included</summary>
          <p className="text-muted-foreground">Choose which categories this format should stock. Excluded categories remove their generated displays. Keep at least one category.</p>
          <Field label="Products per category"><input type="number" min={1} max={16} step={1} className={controlClass}
            placeholder="Full assortment" value={value.products_per_category ?? ""}
            onChange={(event) => update({ products_per_category: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
          <p className="text-muted-foreground">Set a maximum of 1–16 distinct products per included category, or leave blank for the full assortment. Displays stay in place and may repeat products. Shuffle selects another reproducible mix.</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {categories.map((category) => <label key={category.id} className="flex items-center gap-2">
              <input type="checkbox" checked={!excluded.has(category.id)} disabled={!excluded.has(category.id) && includedCount === 1}
                onChange={(event) => update({ excluded_categories: event.target.checked
                  ? (value.excluded_categories ?? []).filter((id) => id !== category.id)
                  : [...(value.excluded_categories ?? []), category.id] })} />{category.label}
            </label>)}
          </div>
          {(value.excluded_categories?.length ?? 0) > 0 && <button type="button" className="underline" onClick={() => update({ excluded_categories: [] })}>Restore all product categories</button>}
        </details>}
        <ReservedAreasEditor areas={value.reserved_areas ?? []} onChange={(reserved_areas) => update({ reserved_areas })}
          grid={[value.width ?? selected?.grid[0] ?? 12, value.height ?? selected?.grid[1] ?? 10]} entrance={value.entrance} gateWall={value.gate_wall} />
        <Field label="Additional design brief"><textarea className={controlClass} rows={2} maxLength={2000} value={value.requirements ?? ""} onChange={(e) => update({ requirements: e.target.value })} placeholder="For example: use warm task lighting in the consultation corner or seasonal signs near the entrance." /></Field>
        </div>
        {budgetCurrency && value.currency !== budgetCurrency && <p role="status" className="text-xs text-amber-700 dark:text-amber-300">This project uses {budgetCurrency} shopper budgets. You can preview and save this {value.currency} layout; to simulate it, create a new {value.currency} project or use {budgetCurrency} here. Existing budgets are not converted.</p>}
        {customizationOpen && <p className="text-[11px] text-muted-foreground">Grid sizes use cells, not measured floor area. Shelf direction and aisle gap apply to interior rows and cross-aisles; wall spacing and seating clearance are separate. Your brief is saved with the layout for further editing; it does not automatically place fixtures. Seating starts in the chosen area and extends into neighboring space as the count increases. Dining tables reserve floor space and show seating; table service and dining time are not simulated.</p>}
      </>}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return <div className="space-y-1 text-xs"><label htmlFor={id}>{label}</label>{cloneElement(children, { id })}</div>;
}
