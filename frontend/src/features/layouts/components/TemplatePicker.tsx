import { weekdayLong } from "@/shared/i18n/timeFormat";
import { RequestError } from "@/shared/components/RequestError";
import { starterCategoryLabel } from "@/shared/i18n/catalogCategories";
import { Check, ChevronDown, X } from "lucide-react";
import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { useI18n } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { storeTypeLabel, templateName } from "@/shared/i18n/storeLabels";
import { rackDiningSeats } from "@/shared/utils/dining";
import { cloneElement, useId, useRef, useState, type ReactElement } from "react";
import { useQuery } from "@tanstack/react-query";

import { INTERIOR_DESIGNS } from "@/features/store-viewer/realistic/designThemes";
import type { StoreDesign } from "@/shared/types/domain";
import * as api from "@/shared/api/client";
import { cn } from "@/shared/utils/cn";
import { searchText } from "@/shared/utils/searchText";
import { applyLayoutPriority, LAYOUT_PRIORITIES, LAYOUT_STYLES, resolveFloorSize, resolveOperatingHours, templateRequest, validTemplateChoice, validWeeklyHours, type FloorSize, type LayoutPriority, type OperatingHours, type TemplateChoice } from "../templateOptions";
import { LayoutBriefField } from "./LayoutBriefField";
import { ReservedAreasEditor } from "./ReservedAreasEditor";
import { FloorPlanPreview } from "./FloorPlanPreview";
import { GenerationOptionsFile } from "./GenerationOptionsFile";
import { CompareFloorPlans } from "./CompareFloorPlans";
import { WeeklyHoursEditor } from "./WeeklyHoursEditor";
import { formatWeeklyHours } from "../weeklyHours";
import { InteriorColorControls } from "./InteriorColorControls";
import { cellsText, designLabel, priorityLabels, SEATING_LABELS, STYLE_LABELS } from "../optionLabels";
import { resolveAssortmentSettings, type AssortmentSettings } from "../assortmentSettings";

const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";
const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7];

export function TemplatePicker({ value, onChange, onTemplateSelected, budgetCurrency, onApplyDesignToAll, onApplyCurrencyToAll, onApplyHoursToAll, onApplySizeToAll, onApplyPriorityToAll, onApplyAssortmentToAll, sharedAssortment = false, sharedDesign, sharedCurrency, sharedHours = false, sharedSize = false, showOperatingHours = true, defaultCustomizationOpen = true }: {
  value: TemplateChoice;
  onChange: (v: TemplateChoice) => void;
  onTemplateSelected?: (template: api.StoreTemplate) => void;
  budgetCurrency?: string;
  onApplyDesignToAll?: (design: NonNullable<TemplateChoice["design_theme"]>, colors: TemplateChoice["design_colors"]) => void;
  onApplyCurrencyToAll?: (currency: string) => void;
  onApplyHoursToAll?: (hours: OperatingHours) => void;
  onApplySizeToAll?: (size: FloorSize) => void;
  onApplyPriorityToAll?: (priority: LayoutPriority) => void;
  onApplyAssortmentToAll?: (settings: AssortmentSettings) => void;
  sharedAssortment?: boolean;
  sharedDesign?: NonNullable<TemplateChoice["design_theme"]>;
  sharedCurrency?: string;
  sharedHours?: boolean;
  sharedSize?: boolean;
  showOperatingHours?: boolean;
  defaultCustomizationOpen?: boolean;
}) {
  const { locale, t } = useI18n();
  const customizationId = useId();
  const [customizationOpen, setCustomizationOpen] = useState(defaultCustomizationOpen);
  const [search, setSearch] = useState("");
  const searchInput = useRef<HTMLInputElement>(null);
  const formatList = useRef<HTMLDivElement>(null);
  const [storeType, setStoreType] = useState("");
  const [size, setSize] = useState("all");
  const [seating, setSeating] = useState("all");
  const [sort, setSort] = useState("default");
  const [priorityId, setPriorityId] = useState(LAYOUT_PRIORITIES[0]!.id);
  const [seedDraft, setSeedDraft] = useState<{ seed: number; text: string } | null>(null);
  const validSeed = Number.isSafeInteger(value.seed);
  const seedText = seedDraft && Object.is(seedDraft.seed, value.seed) ? seedDraft.text : validSeed ? String(value.seed) : "";
  const priority = LAYOUT_PRIORITIES.find((choice) => choice.id === priorityId) ?? LAYOUT_PRIORITIES[0]!;
  const priorityText = priorityLabels(priority, t);
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
  const assortment = resolveAssortmentSettings(value);
  const tableMix = value.table_mix;
  const tableCount = tableMix ? tableMix.two_seat + tableMix.four_seat + tableMix.six_seat : value.dining_tables ?? selected?.default_dining_tables ?? 0;
  const mixStartingCount = value.dining_tables ?? (preview.isSuccess ? preview.data.racks.filter((rack) => rack.type === "table").length : tableCount);
  const closedDays = value.weekly_hours?.filter((entry) => !entry.is_open).map((entry) => entry.day) ?? value.closed_days ?? selected?.closed_days ?? [];
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
  const terms = searchText(search).split(" ").filter(Boolean);
  const filtered = templates.filter((format) => {
    if (storeType && format.store_type !== storeType) return false;
    const cells = format.grid[0] * format.grid[1];
    if (size === "compact" && cells > 144) return false;
    if (size === "medium" && (cells <= 144 || cells > 480)) return false;
    if (size === "large" && cells <= 480) return false;
    if (seating === "with" && format.default_dining_tables === 0) return false;
    if (seating === "without" && format.default_dining_tables > 0) return false;
    const labels = LOCALES.map(({ code }) => `${storeTypeLabel(format.store_type, code)} ${templateName(format.id, format.name, code)}`).join(" ");
    const text = searchText(`${format.name} ${format.description} ${format.store_type} ${format.id} ${labels}`);
    return terms.every((term) => text.includes(term));
  }).sort((a, b) => {
    const byName = () => templateName(a.id, a.name, locale).localeCompare(templateName(b.id, b.name, locale), locale);
    if (sort === "name") return byName();
    if (sort === "smallest") return a.grid[0] * a.grid[1] - b.grid[0] * b.grid[1] || byName();
    if (sort === "largest") return b.grid[0] * b.grid[1] - a.grid[0] * a.grid[1] || byName();
    if (sort === "seats") return b.default_dining_tables - a.default_dining_tables || byName();
    return 0;
  });
  const update = (patch: Partial<TemplateChoice>) => onChange({ ...value, ...patch });
  const selectFormat = (id: string) => {
    if (id === value.templateId) return;
    const format = templates.find((item) => item.id === id);
    if (format) { update({ templateId: id }); onTemplateSelected?.(format); }
  };
  const handleFormatKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) {
      event.preventDefault(); event.stopPropagation(); return;
    }
    if (event.key === "Enter") { event.preventDefault(); event.stopPropagation(); event.currentTarget.click(); return; }
    const arrow = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key);
    if (!arrow && event.key !== "Home" && event.key !== "End") return;
    event.preventDefault(); event.stopPropagation();
    const delta = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
    const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? filtered.length - 1 : (index + delta + filtered.length) % filtered.length;
    const next = filtered[nextIndex];
    if (!next) return;
    // Keep focus synchronous so rapid key presses cannot race deferred navigation.
    if (arrow) selectFormat(next.id);
    formatList.current?.querySelectorAll<HTMLButtonElement>('button[role="radio"]')[nextIndex]?.focus();
  };
  const clearFilters = () => {
    setSearch(""); setStoreType(""); setSize("all"); setSeating("all"); setSort("default");
    searchInput.current?.focus();
  };
  function updateTableMix(patch: Partial<api.DiningTableMix>) {
    const mix = { two_seat: 0, four_seat: 0, six_seat: 0, ...tableMix, ...patch };
    update({ table_mix: mix, dining_tables: mix.two_seat + mix.four_seat + mix.six_seat });
  }

  return (
    <div className="min-w-0 space-y-3 [overflow-wrap:anywhere]">
      <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
        <div className="space-y-1 text-xs">
          <label htmlFor={`${customizationId}-search`}>{t("findStoreFormat")}</label>
          <div className="relative">
            <input id={`${customizationId}-search`} ref={searchInput} className={cn(controlClass, "pr-8")} value={search}
              onChange={(e) => setSearch(e.target.value)} placeholder={t("formatSearchPlaceholder")}
              onKeyDown={(event) => { if (event.key === "Escape" && search) { event.preventDefault(); event.stopPropagation(); setSearch(""); } }} />
            {search && <button type="button" aria-label={t("clearFormatSearch")} className="absolute inset-y-0 right-0 grid w-8 place-items-center rounded hover:bg-muted"
              onClick={() => { setSearch(""); searchInput.current?.focus(); }}><X className="size-3.5" aria-hidden /></button>}
          </div>
        </div>
        <label className="space-y-1 text-xs">{t("storeCategory")}
          <select aria-label={t("storeCategory")} className={controlClass} value={storeType} onChange={(e) => setStoreType(e.target.value)}>
            <option value="">{t("allCategories")}</option>
            {[...new Set(templates.map((format) => format.store_type))].sort((a, b) => storeTypeLabel(a, locale).localeCompare(storeTypeLabel(b, locale), locale))
              .map((type) => <option key={type} value={type}>{storeTypeLabel(type, locale)}</option>)}
          </select>
        </label>
      </div>
      <details className="space-y-2 rounded border px-2 py-1.5 text-xs">
        <summary className="cursor-pointer">{t("moreFormatFilters")}</summary>
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label={t("defaultFloorSize")}><select className={controlClass} value={size} onChange={(e) => setSize(e.target.value)}>
            <option value="all">{t("anySize")}</option><option value="compact">{t("compactSize")}</option>
            <option value="medium">{t("mediumSize")}</option><option value="large">{t("largeSize")}</option>
          </select></Field>
          <Field label={t("defaultSeating")}><select className={controlClass} value={seating} onChange={(e) => setSeating(e.target.value)}>
            <option value="all">{t("anySeating")}</option><option value="with">{t("withDiningTables")}</option><option value="without">{t("withoutDiningTables")}</option>
          </select></Field>
          <Field label={t("sortFormats")}><select className={controlClass} value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="default">{t("formatOrder")}</option><option value="name">{t("formatNameOrder")}</option>
            <option value="smallest">{t("smallestFloorFirst")}</option><option value="largest">{t("largestFloorFirst")}</option><option value="seats">{t("mostTablesFirst")}</option>
          </select></Field>
        </div>
        <p className="text-muted-foreground">{t("formatFiltersHint")}</p>
      </details>
      {templatesQuery.isSuccess && <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <p className="text-muted-foreground" aria-live="polite">{t(templates.length === 1 ? "formatCountSingle" : "formatCount", { shown: filtered.length, total: templates.length })}</p>
        {(search || storeType || size !== "all" || seating !== "all" || sort !== "default") && <button type="button" className="underline"
          onClick={clearFilters}>{t("clearFormatFilters")}</button>}
      </div>}
      {templatesQuery.isPending && <p role="status" className="text-xs">{t("loadingFormats")}</p>}
      {templatesQuery.isError && <p role="alert" className="text-xs text-destructive">{t("loadFormatsError")} <button type="button" className="underline" disabled={templatesQuery.isFetching}
        onClick={() => void templatesQuery.refetch()}>{t(templatesQuery.isFetching ? "tryingAgain" : "tryAgain")}</button></p>}
      <p id={`${customizationId}-keyboard`} className="sr-only">{t("formatKeyboardHint")}</p>
      <RadioGroupPrimitive.Root ref={formatList} value={value.templateId} onValueChange={selectFormat}
        loop className="grid min-w-0 max-h-48 grid-cols-1 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2" aria-label={t("storeFormats")}
        aria-describedby={`${customizationId}-keyboard`}>
        {filtered.map((format, index) => (
          <RadioGroupPrimitive.Item key={format.id} value={format.id}
            onKeyDownCapture={(event) => handleFormatKeyDown(event, index)}
            className={cn("min-w-0 rounded-md border p-2 text-left text-xs transition-colors [overflow-wrap:anywhere]", value.templateId === format.id ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
            <div className="flex items-start justify-between gap-2 font-medium"><span className="min-w-0 flex-1">{templateName(format.id, format.name, locale)}</span>
              <RadioGroupPrimitive.Indicator className="shrink-0"><Check className="size-3.5 text-primary" aria-hidden /></RadioGroupPrimitive.Indicator>
            </div>
            <div className="text-muted-foreground">{storeTypeLabel(format.store_type, locale)}</div>
            <div className="text-muted-foreground">{t("defaultFormatSummary", { width: format.grid[0], height: format.grid[1], displays: format.racks, products: format.skus })}</div>
          </RadioGroupPrimitive.Item>
        ))}
      </RadioGroupPrimitive.Root>
      {templatesQuery.isSuccess && !filtered.length && <p className="text-xs text-muted-foreground">
        {t(templates.length ? "noMatchingFormats" : "emptyFormats")}
        {!templates.length && <> <button type="button" className="underline" disabled={templatesQuery.isFetching}
          onClick={() => void templatesQuery.refetch()}>{t(templatesQuery.isFetching ? "tryingAgain" : "tryAgain")}</button></>}
      </p>}
      {selected && (search || storeType || size !== "all" || seating !== "all") && <p className="text-xs text-muted-foreground">{t("formatSelectionHint")}</p>}
      {value.templateId && <>
        <div className="grid gap-3 sm:grid-cols-[170px_minmax(0,1fr)]">
          <div className="space-y-1.5">
            {preview.isSuccess && validTemplateChoice(value) ? <>
              <FloorPlanPreview store={preview.data} areas={value.reserved_areas ?? []} name={templateName(value.templateId, preview.data.name, locale)} />
              <CompareFloorPlans store={preview.data} areas={value.reserved_areas ?? []} templateId={value.templateId} currency={value.currency} />
              <p className="text-xs text-muted-foreground">{t("templatePreviewSize", { width: preview.data.grid_size[0], height: preview.data.grid_size[1],
                displays: preview.data.racks.filter((r) => r.slots.length).length,
                products: new Set(preview.data.racks.flatMap((r) => r.slots.flatMap((s) => s.items.map((i) => i.sku)))).size })}</p>
              <p className="text-xs text-muted-foreground">{t("templatePreviewSeating", { tables: preview.data.racks.filter((r) => r.type === "table").length,
                seats: preview.data.racks.reduce((sum, rack) => sum + rackDiningSeats(rack), 0) })}</p>
              <p className="text-xs text-muted-foreground">{t("templatePreviewCounters", { counters: preview.data.racks.filter((r) => r.type === "counter").length })}</p>
              <p className="text-[10px] text-muted-foreground">{t("planLegend", { inLabel: t("planIn"), outLabel: t("planOut") })}</p>
            </> : <div className="flex min-h-24 items-center justify-center rounded border bg-muted p-3 text-xs" role="status">
              {t(!validTemplateChoice(value) ? "templatePreviewInvalid" : preview.isError ? "templatePreviewUnavailable" : "templatePreviewUpdating")}
            </div>}
            {preview.isError && <RequestError error={preview.error}><button type="button" className="underline" onClick={() => void preview.refetch()}>{t("tryAgain")}</button></RequestError>}
          </div>
          <div className="space-y-2">
            {selected && <p className="text-xs"><span className="text-muted-foreground">{t("selectedFormat")}: </span><strong>{templateName(selected.id, selected.name, locale)}</strong></p>}
            <p className="text-xs text-muted-foreground">{selected?.description}</p>
            <div className="grid grid-cols-2 gap-2">
              <Field label={t("widthCells")}><input type="number" className={controlClass} min={8} max={40} step={1} placeholder={String(selected?.grid[0] ?? 12)} value={value.width ?? ""} onChange={(e) => update({ width: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              <Field label={t("depthCells")}><input type="number" className={controlClass} min={6} max={40} step={1} placeholder={String(selected?.grid[1] ?? 10)} value={value.height ?? ""} onChange={(e) => update({ height: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
              {onApplySizeToAll && <div className="col-span-2 space-y-1 text-xs">
                <button type="button" className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-50" disabled={!floorSize || sharedSize}
                  onClick={() => { if (floorSize) onApplySizeToAll(floorSize); }}>{t(floorSize && sharedSize ? "laySizeAllFloors" : "layApplySizeAllFloors")}</button>
                <p className="text-muted-foreground">{floorSize
                  ? t("layApplySizeHint", { width: floorSize.width, height: floorSize.height })
                  : t("layApplySizeInvalid")}</p>
              </div>}
              <div className="col-span-2 space-y-1"><Field label={t("priceCurrency")}><select className={controlClass} value={value.currency} onChange={(e) => update({ currency: e.target.value })}>
                <option value="USD">USD · $</option><option value="KRW">KRW · ₩</option><option value="JPY">JPY · ¥</option>
              </select></Field>
                {onApplyCurrencyToAll && <button type="button" className="text-left text-[10px] underline disabled:opacity-50" disabled={sharedCurrency === value.currency}
                  onClick={() => onApplyCurrencyToAll(value.currency)}>{t(sharedCurrency === value.currency ? "layCurrencyAllFloors" : "layApplyCurrencyAllFloors")}</button>}
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
              <summary className="cursor-pointer">{t("layApplyPriorityTitle")}</summary>
              <Field label={t("layPriority")}><select className={controlClass} value={priority.id} onChange={(event) => setPriorityId(event.target.value)}>
                {LAYOUT_PRIORITIES.map((choice) => <option key={choice.id} value={choice.id}>{priorityLabels(choice, t).name}</option>)}
              </select></Field>
              <p>{priorityText.description}</p>
              <p className="text-muted-foreground">{t("layPriorityHint")}</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => onChange(applyLayoutPriority(value, priority))}>{t("layApplyPriority")}</button>
                {onApplyPriorityToAll && <button type="button" className="rounded border px-2 py-1 hover:bg-muted"
                  onClick={() => onApplyPriorityToAll(priority)}>{t("layApplyPriorityAllFloors")}</button>}
              </div>
              {onApplyPriorityToAll && <p className="text-muted-foreground">{t("layApplyPriorityAllHint")}</p>}
            </details>
            <div className="grid grid-cols-2 gap-2">
              <div className="col-span-2 grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
              <div className="space-y-1"><Field label={t("layPattern")}><select className={controlClass} value={value.style ?? ""} onChange={(e) => update({ style: (e.target.value || null) as TemplateChoice["style"] })}>
                <option value="">{t("layFormatDefault")}</option>
                {LAYOUT_STYLES.map(([id]) => <option key={id} value={id}>{t(STYLE_LABELS[id])}</option>)}
              </select></Field>
              {!value.style && selected && <p className="text-[11px] text-muted-foreground">{t("layDefaultPattern", { pattern: t(STYLE_LABELS[selected.default_style]) })}</p>}
              </div>
              <Field label={t("layDensity")}><select className={controlClass} value={value.density ?? "balanced"} onChange={(e) => update({ density: e.target.value as TemplateChoice["density"] })}>
                <option value="spacious">{t("layDensitySpacious")}</option><option value="balanced">{t("layDensityBalanced")}</option><option value="dense">{t("layDensityDense")}</option>
              </select></Field>
              <Field label={t("layShelfDirection")}><select className={controlClass} value={value.shelf_direction ?? "horizontal"}
                disabled={(value.style ?? selected?.default_style) === "perimeter"}
                onChange={(e) => update({ shelf_direction: e.target.value as TemplateChoice["shelf_direction"] })}>
                <option value="horizontal">{t("layDirectionHorizontal")}</option><option value="vertical">{t("layDirectionVertical")}</option>
              </select></Field>
              <Field label={t("layAisleGap")}><select className={controlClass} value={value.aisle_width ?? ""}
                disabled={(value.style ?? selected?.default_style) === "perimeter"}
                onChange={(e) => update({ aisle_width: e.target.value === "" ? null : Number(e.target.value) })}>
                <option value="">{t("layDensityDefault", { cells: cellsText(densityGap, t) })}</option>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{cellsText(n, t)}</option>)}
              </select></Field>
              </div>
              {(value.style ?? selected?.default_style) === "cross" && <p className="col-span-2 text-[11px] text-muted-foreground">{t("layCrossHint")}</p>}
              {(value.style ?? selected?.default_style) === "plaza" && <p className="col-span-2 text-[11px] text-muted-foreground">{t("layPlazaHint")}</p>}
              <div className="col-span-2 space-y-1"><Field label={t("layMaxShelfRun")}><select className={controlClass} value={value.max_shelf_run ?? ""}
                disabled={(value.style ?? selected?.default_style) === "perimeter"}
                onChange={(e) => update({ max_shelf_run: e.target.value === "" ? null : Number(e.target.value) })}>
                <option value="">{t("layDensityDefault", { cells: cellsText(densityRun, t) })}</option>
                {Array.from({ length: 8 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{t(n === 1 ? "layDisplayCellOne" : "layDisplayCellMany", { count: n })}</option>)}
              </select></Field>
                <p className="text-[10px] text-muted-foreground">{t("layMaxShelfRunHint")}</p>
              </div>
              <Field label={t("layEntranceWall")}><select className={controlClass} value={value.gate_wall ?? "front"} onChange={(e) => update({ gate_wall: e.target.value as TemplateChoice["gate_wall"] })}>
                <option value="front">{t("layWallFront")}</option><option value="back">{t("layWallBack")}</option><option value="left">{t("layWallLeft")}</option><option value="right">{t("layWallRight")}</option>
              </select></Field>
              <Field label={t("layEntrancePosition")}><select className={controlClass} value={value.entrance ?? "left"} onChange={(e) => update({ entrance: e.target.value as TemplateChoice["entrance"] })}>
                <option value="left">{t(sideGates ? "layNearBack" : "layLeft")}</option><option value="center">{t("layCenter")}</option><option value="right">{t(sideGates ? "layNearFront" : "layRight")}</option>
              </select></Field>
              <Field label={t("layExitPosition")}><select className={controlClass} value={value.exit_position ?? "shared"} onChange={(e) => update({ exit_position: e.target.value as TemplateChoice["exit_position"], ...(e.target.value === "shared" ? { exit_wall: null } : {}) })}>
                <option value="shared">{t("layShareEntrance")}</option><option value="left">{t(sideExit ? "layNearBack" : "layLeft")}</option><option value="center">{t("layCenter")}</option><option value="right">{t(sideExit ? "layNearFront" : "layRight")}</option>
              </select></Field>
              <Field label={t("layExitWall")}><select className={controlClass} value={sharedExit ? "" : value.exit_wall ?? ""} disabled={sharedExit}
                onChange={(e) => update({ exit_wall: e.target.value === "" ? null : e.target.value as TemplateChoice["exit_wall"] })}>
                <option value="">{t("layEntranceWall")}</option><option value="front">{t("layWallFront")}</option><option value="back">{t("layWallBack")}</option><option value="left">{t("layWallLeft")}</option><option value="right">{t("layWallRight")}</option>
              </select></Field>
              <p className="col-span-2 text-[10px] text-muted-foreground">{t("layExitHint")}</p>
              <div className="col-span-2 sm:col-span-1"><Field label={t("layCheckoutCounters")}><select className={controlClass} value={value.checkouts ?? ""} onChange={(e) => update({ checkouts: e.target.value === "" ? null : Number(e.target.value) })}>
                <option value="">{t("layCheckoutsDefault", { count: selected?.default_checkouts ?? 1 })}</option>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
              </select></Field></div>
              <Field label={t("layCheckoutWall")}><select className={controlClass} value={value.checkout_wall ?? "front"}
                onChange={(e) => update({ checkout_wall: e.target.value as TemplateChoice["checkout_wall"] })}>
                <option value="front">{t("layWallFront")}</option><option value="back">{t("layWallBack")}</option>
                <option value="left">{t("layWallLeft")}</option><option value="right">{t("layWallRight")}</option>
              </select></Field>
              <div className="col-span-2 sm:col-span-1"><Field label={t("layCheckoutPlacement")}><select className={controlClass} value={value.checkout_placement ?? "auto"}
                onChange={(e) => update({ checkout_placement: e.target.value as TemplateChoice["checkout_placement"] })}>
                <option value="auto">{t("layFormatDefaultWith", { value: t(selected?.default_checkout_placement === "near_entrance" ? "layDefaultNearEntrance" : selected?.default_checkout_placement === "away_from_entrance" ? "layDefaultAwayFromEntrance" : "layDefaultWallOrder") })}</option><option value="near_entrance">{t("layNearTheEntrance")}</option>
                <option value="away_from_entrance">{t("layAwayFromTheEntrance")}</option>
              </select></Field></div>
              <Field label={t("layCounterSpace")}><select className={controlClass} value={value.checkout_clearance ?? 0}
                onChange={(event) => update({ checkout_clearance: Number(event.target.value) })}>
                <option value={0}>{t("layCounterAdjacent")}</option>{[1, 2, 3].map((n) => <option key={n} value={n}>{cellsText(n, t)}</option>)}
              </select></Field>
              <p className="col-span-2 text-[10px] text-muted-foreground">{t("layCounterSpaceHint")}</p>
              <div className="col-span-2 space-y-1 sm:col-span-1"><Field label={t("layInteriorDesignRealistic")}><select className={controlClass} value={value.design_theme ?? ""} onChange={(e) => update({ design_theme: (e.target.value || null) as TemplateChoice["design_theme"] })}>
                <option value="">{t("layFormatDefault")}</option>
                {(Object.keys(INTERIOR_DESIGNS) as StoreDesign[]).map((id) => <option key={id} value={id}>{designLabel(id, t)}</option>)}
              </select></Field>
                {!value.design_theme && selected && <p className="text-[11px] text-muted-foreground">{t("layDefaultDesign", { design: designLabel(selected.default_design, t) })}</p>}
                {onApplyDesignToAll && <button type="button" className="text-left text-[10px] underline disabled:opacity-50" disabled={!activeDesign || sharedDesign === activeDesign}
                  onClick={() => { if (activeDesign) onApplyDesignToAll(activeDesign, value.design_colors ?? null); }}>{t(activeDesign && sharedDesign === activeDesign ? "layDesignAllFloors" : "layApplyDesignAllFloors")}</button>}
              </div>
              <Field label={t("layShelfDesign")}><select className={controlClass} value={value.fixture_design ?? "mixed"} onChange={(e) => update({ fixture_design: e.target.value as TemplateChoice["fixture_design"] })}>
                <option value="mixed">{t("layMixedDisplays")}</option><option value="a">{t("rackEditOpenA")}</option><option value="b">{t("rackEditOpenB")}</option><option value="c">{t("layWallEndRackC")}</option>
              </select></Field>
              <div className="space-y-1"><Field label={tableMix ? t("layDiningTablesMixed") : t("layDiningTablesSeats", { seats: value.dining_seats ?? 4 })}><input type="number" min={0} max={48} step={1} className={controlClass}
                disabled={!!tableMix} placeholder={t("layFormatDefaultWith", { value: selected?.default_dining_tables ?? 0 })} value={tableMix ? tableCount : value.dining_tables ?? ""}
                onChange={(e) => update({ dining_tables: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
                <p className="text-[10px] text-muted-foreground">{t(tableMix ? "layTablesFromMix" : "layTablesHint")}</p>
              </div>
              <div className="space-y-1"><Field label={t("laySeatsPerTable")}><select className={controlClass} value={value.dining_seats ?? 4}
                disabled={!!tableMix || tableCount === 0}
                onChange={(e) => update({ dining_seats: Number(e.target.value) as 2 | 4 | 6 })}>
                {[2, 4, 6].map((n) => <option key={n} value={n}>{t("laySeats", { count: n })}</option>)}
              </select></Field><p className="text-[10px] text-muted-foreground">{tableMix ? t("layChooseSizesBelow") : t("layTableCells", { size: value.table_rotation === 90 ? `2×${(value.dining_seats ?? 4) / 2}` : `${(value.dining_seats ?? 4) / 2}×2` })}</p></div>
              <Field label={t("layTableRotation")}><select className={controlClass} value={value.table_rotation ?? 0}
                disabled={tableCount === 0}
                onChange={(e) => update({ table_rotation: Number(e.target.value) as 0 | 90 })}>
                <option value={0}>0°</option><option value={90}>90°</option>
              </select></Field>
              <div className="col-span-2 sm:col-span-1"><Field label={t("laySeatingStartsNear")}><select className={controlClass} value={value.seating_zone ?? "auto"}
                disabled={tableCount === 0}
                onChange={(e) => update({ seating_zone: e.target.value as TemplateChoice["seating_zone"] })}>
                <option value="auto">{selected?.default_seating_zone && selected.default_seating_zone !== "auto" ? t("layFormatDefaultWith", { value: t(SEATING_LABELS[selected.default_seating_zone]).toLocaleLowerCase(locale) }) : t("layFormatDefault")}</option>
                {(Object.keys(SEATING_LABELS) as (keyof typeof SEATING_LABELS)[]).map((zone) => <option key={zone} value={zone}>{t(SEATING_LABELS[zone])}</option>)}
              </select></Field>
                {(value.seating_zone === "near_entrance" || value.seating_zone === "away_from_entrance") && <p className="text-[10px] text-muted-foreground">{t("laySeatingFollowsEntrance")}</p>}
              </div>
              <div className="col-span-2 sm:col-span-1"><Field label={t("laySpaceAroundTables")}><select className={controlClass} value={value.table_clearance ?? 1}
                disabled={tableCount === 0}
                onChange={(e) => update({ table_clearance: Number(e.target.value) })}>
                <option value={1}>{t("layClearanceStandard")}</option><option value={2}>{t("layClearanceMore")}</option><option value={3}>{t("layClearanceOpen")}</option>
              </select></Field></div>
              <div className="col-span-2 space-y-2 rounded border p-2 text-xs">
                <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
                  {([["table_clearance_x", "layGapLeftRight"], ["table_clearance_y", "layGapBackFront"]] as const).map(([key, label]) =>
                    <Field key={key} label={t(label)}><select className={controlClass} value={value[key] ?? ""} disabled={tableCount === 0}
                      onChange={(event) => update({ [key]: event.target.value === "" ? null : Number(event.target.value) })}>
                      <option value="">{t("layGapShared")}</option>
                      {[1, 2, 3, 4].map((gap) => <option key={gap} value={gap}>{cellsText(gap, t)}</option>)}
                    </select></Field>)}
                </div>
                <p className="text-muted-foreground">{t("layCurrentGaps", { x: value.table_clearance_x ?? value.table_clearance ?? 1, y: value.table_clearance_y ?? value.table_clearance ?? 1 })}</p>
                {(value.table_clearance_x != null || value.table_clearance_y != null) && <button type="button" className="underline"
                  onClick={() => update({ table_clearance_x: null, table_clearance_y: null })}>{t("layUseSharedGaps")}</button>}
              </div>
            </div>
            <InteriorColorControls design={activeDesign} colors={value.design_colors} onChange={(design_colors) => update({ design_colors })} />
            <details className="space-y-2 rounded border p-2 text-xs">
              <summary className="cursor-pointer">{tableMix ? t("layMixedTableSizesCount", { count: tableCount }) : t("layMixedTableSizes")}</summary>
              <label className="flex items-center gap-2"><input type="checkbox" checked={!!tableMix}
                onChange={(event) => event.target.checked
                  ? updateTableMix({ [value.dining_seats === 2 ? "two_seat" : value.dining_seats === 6 ? "six_seat" : "four_seat"]: mixStartingCount })
                  : update({ table_mix: null, dining_tables: tableCount })} />{t("layUseMixedTableSizes")}</label>
              {tableMix && <div className="grid grid-cols-3 gap-2">
                {([["two_seat", 2], ["four_seat", 4], ["six_seat", 6]] as const).map(([key, seats]) => <Field key={key} label={t("laySeatTables", { seats })}>
                  <input type="number" min={0} max={48} step={1} className={controlClass} value={tableMix[key]}
                    onChange={(event) => updateTableMix({ [key]: Number(event.target.value) })} />
                </Field>)}
              </div>}
              <p className="text-muted-foreground">{t("layMixedTablesHint")}</p>
            </details>
            <div className="space-y-1 text-xs">
              <Field label={t("templateSeed")}><input type="text" className={controlClass} value={seedText}
                aria-invalid={!validSeed} aria-describedby={`${customizationId}-seed-help${validSeed ? "" : ` ${customizationId}-seed-error`}`}
                onChange={(event) => {
                  const text = event.target.value;
                  const parsed = /^[+-]?\d+$/.test(text.trim()) ? Number(text.trim()) : NaN;
                  const seed = Number.isSafeInteger(parsed) ? parsed : NaN;
                  setSeedDraft({ seed, text }); update({ seed });
                }} /></Field>
              <p id={`${customizationId}-seed-help`} className="text-muted-foreground">{t("templateSeedHint")}</p>
              {!validSeed && <p id={`${customizationId}-seed-error`} role="alert" className="text-destructive">{t("templateSeedInvalid")}</p>}
              {value.seed === Number.MAX_SAFE_INTEGER && <p className="text-muted-foreground">{t("templateSeedHighest")}</p>}
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-50" disabled={!validSeed || value.seed === Number.MAX_SAFE_INTEGER}
                onClick={() => update({ seed: value.seed + 1 })}>{validSeed ? t("templateShuffleSeed", { seed: String(value.seed) }) : t("templateShuffle")}</button>
              <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={() => update({ style: null, width: null, height: null, density: "balanced", aisle_width: null, max_shelf_run: null, shelf_direction: "horizontal", entrance: "left", gate_wall: "front", exit_position: "shared", exit_wall: null, checkouts: null, checkout_placement: "auto", checkout_wall: "front", checkout_clearance: 0, fixture_design: "mixed", design_theme: null, design_colors: null, dining_tables: null, dining_seats: 4, table_mix: null, table_rotation: 0, table_clearance: 1, table_clearance_x: null, table_clearance_y: null, seating_zone: "auto", reserved_areas: [], excluded_categories: [], products_per_category: null, category_product_limits: {}, open_hour: null, close_hour: null, closed_days: null, weekly_hours: null, seed: 0 })}>{t("layResetOptions")}</button>
            </div>
            </div>
          </div>
        </div>
        <div id={`${customizationId}-more`} hidden={!customizationOpen} className="space-y-3">
        {showOperatingHours && <details className="space-y-2 rounded border p-2 text-xs">
          <summary className="cursor-pointer">{t("templateHoursSummary", { count: 7 - closedDays.length })}</summary>
          <label className="flex items-center gap-2"><input type="checkbox" checked={value.weekly_hours != null}
            disabled={value.weekly_hours == null && !operatingHours}
            onChange={(event) => {
              if (!event.target.checked) update({ weekly_hours: null });
              else if (operatingHours) update({ weekly_hours: Array.from({ length: 7 }, (_, index) => ({
                day: index + 1, is_open: !operatingHours.closed_days.includes(index + 1),
                open_hour: operatingHours.open_hour, close_hour: operatingHours.close_hour,
              })) });
            }} />{t("templateHoursIndividual")}</label>
          {value.weekly_hours != null ? <>
            <WeeklyHoursEditor hours={value.weekly_hours} onChange={(weekly_hours) => update({ weekly_hours })} />
            {!validWeeklyHours(value.weekly_hours) && <p role="alert" className="text-destructive">{t("templateHoursInvalid")}</p>}
            <p className="text-muted-foreground">{t("templateHoursIndividualHint")}</p>
          </> : <>
          <div className="grid grid-cols-2 gap-2">
            <Field label={t("templateOpeningHour")}><input type="number" min={0} max={23} step={1} className={controlClass}
              placeholder={String(selected?.open_hours[0] ?? 0)} value={value.open_hour ?? ""}
              onChange={(event) => update({ open_hour: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
            <Field label={t("templateClosingHour")}><input type="number" min={1} max={24} step={1} className={controlClass}
              placeholder={String(selected?.open_hours[1] ?? 24)} value={value.close_hour ?? ""}
              onChange={(event) => update({ close_hour: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
          </div>
          <p className="text-muted-foreground">{t("templateHoursBlankHint")}</p>
          <fieldset className="space-y-2">
            <legend>{t("templateOpenWeekdays")}</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {WEEKDAYS.map((day, index) => <label key={day} className="flex items-center gap-1.5">
                <input type="checkbox" checked={!closedDays.includes(index + 1)} disabled={closedDays.length === 6 && !closedDays.includes(index + 1)}
                  onChange={(event) => update({ closed_days: event.target.checked
                    ? closedDays.filter((value) => value !== index + 1)
                    : [...closedDays, index + 1].sort((a, b) => a - b) })} />{weekdayLong(index + 1, locale)}
              </label>)}
            </div>
          </fieldset>
          <p className="text-muted-foreground">{t("templateHoursDayHint")}</p>
          </>}
          <button type="button" className="underline" onClick={() => update({ open_hour: null, close_hour: null, closed_days: null, weekly_hours: null })}>{t("templateHoursReset")}</button>
          {onApplyHoursToAll && <div className="space-y-1 border-t pt-2">
            <button type="button" className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-50"
              disabled={!operatingHours || sharedHours} onClick={() => { if (operatingHours) onApplyHoursToAll(operatingHours); }}>
              {t(operatingHours && sharedHours ? "templateHoursShared" : "templateHoursApply")}
            </button>
            <p className="text-muted-foreground">{operatingHours
              ? operatingHours.weekly_hours ? t("templateHoursApplyHint", { hours: formatWeeklyHours(operatingHours.weekly_hours, locale) }) : t("templateHoursSharedApplyHint", { open: String(operatingHours.open_hour).padStart(2, "0") + ":00", close: String(operatingHours.close_hour).padStart(2, "0") + ":00", count: 7 - operatingHours.closed_days.length })
              : t("templateHoursApplyInvalid")}</p>
          </div>}
        </details>}
        {categories.length > 0 && <details className="space-y-2 rounded border p-2 text-xs">
          <summary className="cursor-pointer">{t("templateCategoriesSummary", { included: includedCount, total: categories.length })}</summary>
          <p className="text-muted-foreground">{t("templateCategoriesHint")}</p>
          <Field label={t("templateProductsPerCategory")}><input type="number" min={1} max={16} step={1} className={controlClass}
            placeholder={t("templateFullAssortment")} value={value.products_per_category ?? ""}
            onChange={(event) => update({ products_per_category: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
          <p className="text-muted-foreground">{t("templateProductsLimitHint")}</p>
          <p className="text-muted-foreground">{t("templateProductsOverrideHint")}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {categories.map((category) => <div key={category.id} className="flex items-center gap-2">
              <label className="flex min-w-0 flex-1 items-center gap-2">
                <input type="checkbox" checked={!excluded.has(category.id)} disabled={!excluded.has(category.id) && includedCount === 1}
                  onChange={(event) => update({ excluded_categories: event.target.checked
                    ? (value.excluded_categories ?? []).filter((id) => id !== category.id)
                    : [...(value.excluded_categories ?? []), category.id] })} />{starterCategoryLabel(category.id, category.label, locale)}
              </label>
              <input type="number" min={1} max={16} step={1} className="w-16 shrink-0 rounded-md border bg-background px-2 py-1.5 text-xs disabled:opacity-40"
                aria-label={t("templateProductsFor", { category: starterCategoryLabel(category.id, category.label, locale) })} disabled={excluded.has(category.id)}
                placeholder={value.products_per_category == null ? t("templateAllProducts") : String(value.products_per_category)} value={value.category_product_limits?.[category.id] ?? ""}
                onChange={(event) => {
                  const category_product_limits = { ...value.category_product_limits };
                  if (event.target.value === "") delete category_product_limits[category.id];
                  else category_product_limits[category.id] = Number(event.target.value);
                  update({ category_product_limits });
                }} />
            </div>)}
          </div>
          {Object.keys(value.category_product_limits ?? {}).length > 0 && <button type="button" className="underline" onClick={() => update({ category_product_limits: {} })}>{t("templateProductsShared")}</button>}
          {(value.excluded_categories?.length ?? 0) > 0 && <button type="button" className="underline" onClick={() => update({ excluded_categories: [] })}>{t("templateCategoriesRestore")}</button>}
          {onApplyAssortmentToAll && <div className="space-y-1 border-t pt-2">
            <button type="button" className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-50"
              disabled={!assortment || sharedAssortment} onClick={() => { if (assortment) onApplyAssortmentToAll(assortment); }}>
              {t(assortment && sharedAssortment ? "templateAssortmentShared" : "templateAssortmentApply")}
            </button>
            <p className="text-muted-foreground">{t("templateAssortmentApplyHint")}</p>
          </div>}
        </details>}
        <ReservedAreasEditor areas={value.reserved_areas ?? []} onChange={(reserved_areas) => update({ reserved_areas })}
          grid={[value.width ?? selected?.grid[0] ?? 12, value.height ?? selected?.grid[1] ?? 10]} entrance={value.entrance} gateWall={value.gate_wall} />
        <LayoutBriefField value={value} onApply={(patch) => update(patch)} onBriefChange={(requirements) => update({ requirements })} />
        </div>
        {budgetCurrency && value.currency !== budgetCurrency && <p role="status" className="text-xs text-amber-700 dark:text-amber-300">{t("layBudgetCurrencyMismatch", { budget: budgetCurrency, currency: value.currency })}</p>}
        {customizationOpen && <p className="text-[11px] text-muted-foreground">{t("layCustomizationFootnote")}</p>}
      </>}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return <div className="space-y-1 text-xs"><label htmlFor={id}>{label}</label>{cloneElement(children, { id })}</div>;
}
