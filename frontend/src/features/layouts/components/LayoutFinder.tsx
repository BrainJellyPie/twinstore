import { Check, Search, X } from "lucide-react";
import { useId, useRef, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import { searchText } from "@/shared/utils/searchText";
import { translate, useI18n } from "@/shared/i18n/i18n";
import { LOCALES, messages, type Locale, type MessageKey } from "@/shared/i18n/messages";
import type { Layout } from "../hooks/useLayouts";

// A layout's store format by name, as the template gallery shows it; a format this version does not know, by its id.
function formatName(templateId: string, locale: Locale): string {
  const key = `tpl_${templateId}`;
  return Object.prototype.hasOwnProperty.call(messages, key) ? translate(locale, key as MessageKey) : templateId.replace(/_/g, " ");
}

export function LayoutFinder({ layouts, selectedId, onSelect, disabled }: {
  layouts: Layout[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  disabled?: boolean;
}) {
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("all");
  const fieldId = useId();
  const input = useRef<HTMLInputElement>(null);
  const terms = searchText(search).split(" ").filter(Boolean);
  const filtered = layouts.filter((layout) => {
    if (group === "single" && layout.building) return false;
    if (group === "building" && !layout.building) return false;
    const text = searchText([layout.id, layout.name, layout.building?.name, layout.building?.label,
      layout.building ? `${layout.building.level}F` : "", layout.generation?.template_id,
      ...(layout.generation ? LOCALES.map(({ code }) => formatName(layout.generation!.template_id, code)) : []),
      layout.generation?.requirements, layout.generation?.currency,
      ...(layout.generation?.reserved_areas ?? []).map((area) => area.label)].filter(Boolean).join(" "));
    return terms.every((term) => text.includes(term));
  }).sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId) || b.createdAt.localeCompare(a.createdAt));
  const clearSearch = () => { setSearch(""); input.current?.focus(); };

  return <Dialog open={open} onOpenChange={(next) => {
    setOpen(next);
    if (next) { setSearch(""); setGroup("all"); }
  }}>
    <DialogTrigger asChild>
      <button type="button" data-layout-finder-trigger disabled={disabled} aria-label={t("findLayout")} title={t("findLayout")}
        className="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50">
        <Search className="size-4" aria-hidden />
      </button>
    </DialogTrigger>
    <DialogContent className="flex max-h-[90dvh] min-w-0 flex-col overflow-hidden [overflow-wrap:anywhere] sm:max-w-xl [@media(max-height:480px)]:gap-2 [@media(max-height:480px)]:p-4"
      onEscapeKeyDown={(event) => {
        if (event.isComposing || event.keyCode === 229) { event.preventDefault(); return; }
        if (event.target === input.current && search) { event.preventDefault(); clearSearch(); }
      }}>
      <DialogHeader className="min-w-0 shrink-0 pr-6">
        <DialogTitle>{t("findLayoutTitle")}</DialogTitle>
        <DialogDescription className="[@media(max-height:480px)]:sr-only">{t("findLayoutHint")}</DialogDescription>
      </DialogHeader>
      <div className="grid shrink-0 grid-cols-1 items-end gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0 space-y-1">
          <label htmlFor={`${fieldId}-search`} className="text-xs">{t("searchLayouts")}</label>
          <div className="relative min-w-0">
            <Input ref={input} id={`${fieldId}-search`} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("layoutSearchPlaceholder")} className="pr-10"
              onKeyDown={(event) => {
                // Enter opens the first match, ↓ moves into the results; not while an IME is composing.
                if (event.nativeEvent.isComposing || event.keyCode === 229) return;
                const first = filtered[0];
                if (event.key === "Enter" && first && !disabled) {
                  event.preventDefault();
                  if (first.id !== selectedId) onSelect(first.id);
                  setOpen(false);
                } else if (event.key === "ArrowDown") {
                  event.preventDefault();
                  event.currentTarget.closest("[role=dialog]")?.querySelector<HTMLButtonElement>("[data-layout-finder-result]")?.focus();
                }
              }} />
            {search && <button type="button" aria-label={t("clearLayoutSearch")} title={t("clearLayoutSearch")} onClick={clearSearch}
              className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-primary">
              <X className="size-4" aria-hidden />
            </button>}
          </div>
        </div>
        <div className="min-w-0 space-y-1">
          <label htmlFor={`${fieldId}-group`} className="block text-xs">{t("layoutGroup")}</label>
          <select id={`${fieldId}-group`} value={group} onChange={(event) => setGroup(event.target.value)}
            className="h-9 w-full min-w-0 rounded-lg border bg-background px-2 text-sm">
            <option value="all">{t("allLayouts")}</option><option value="single">{t("singleFloors")}</option><option value="building">{t("buildingFloors")}</option>
          </select>
        </div>
      </div>
      <p role="status" className="shrink-0 text-xs text-muted-foreground">{t(layouts.length === 1 ? "filteredOneLayout" : "filteredLayouts", { shown: filtered.length, total: layouts.length })}</p>
      <div className="min-h-0 min-w-0 flex-1 space-y-2 overflow-y-auto" role="region" aria-label={t("matchingLayouts")}>
        {filtered.map((layout) => <button key={layout.id} type="button" data-layout-finder-result disabled={disabled}
          aria-pressed={layout.id === selectedId} data-testid={`layout-search-result-${layout.id}`}
          className={cn("w-full min-w-0 rounded-xl border p-3 text-left hover:bg-muted disabled:opacity-50", layout.id === selectedId && "border-primary bg-primary/5")}
          onClick={() => { if (layout.id !== selectedId) onSelect(layout.id); setOpen(false); }}>
          <div className="flex min-w-0 items-center justify-between gap-2">
            <span className="min-w-0 text-sm font-medium">{layout.name.trim() || t("unnamedLayout", { number: layouts.indexOf(layout) + 1 })}</span>
            {layout.id === selectedId && <Check className="size-4 shrink-0 text-primary" aria-label={t("selectedLayout")} />}
          </div>
          {layout.building && <p className="mt-1 text-xs text-muted-foreground">{layout.building.name} · {t("buildingFloorPosition", { level: layout.building.level, count: layout.building.floor_count })} · {layout.building.label}</p>}
          <p className="mt-1 text-xs text-muted-foreground">
            {[layout.generation && formatName(layout.generation.template_id, locale), layout.generation?.currency,
              t(layout.status === "locked" ? "layoutSimulationSaved" : layout.status === "running" ? "layoutRunning" : "layoutDraft")].filter(Boolean).join(" · ")}
          </p>
          {layout.generation?.requirements && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{layout.generation.requirements}</p>}
          {!!layout.generation?.reserved_areas?.length && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{t("layoutReservedAreas", { areas: layout.generation.reserved_areas.map((area) => area.label).join(", ") })}</p>}
        </button>)}
        {filtered.length === 0 && <div className="space-y-3 py-6 text-center text-sm text-muted-foreground">
          <p>{t(layouts.length === 0 ? "noLayoutsSaved" : "noMatchingLayouts")}</p>
          {layouts.length > 0 && (search || group !== "all") && <button type="button" className="rounded-lg border px-3 py-2 text-foreground hover:bg-muted"
            onClick={() => { setGroup("all"); clearSearch(); }}>{t("resetLayoutFilters")}</button>}
        </div>}
      </div>
    </DialogContent>
  </Dialog>;
}
