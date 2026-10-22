// Layout switching/adding must work in every mode (ready/running/playback). Each
// layout has its own simulation history, so navigation cannot be gated on the
// current mode. `disabled` is reserved for ProjectShell.navigationDisabled and
// blocks both the tabs and the Add button together.

import { Plus } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import type { Layout } from "../hooks/useLayouts";
import { LayoutFinder } from "./LayoutFinder";

export interface LayoutTabsProps {
  layouts: Layout[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  onAddNew: () => void;
  disabled?: boolean;
}

export function LayoutTabs({ layouts, selectedId, onSelect, onAddNew, disabled = false }: LayoutTabsProps) {
  const { t } = useI18n();
  const hintId = useId();
  const selectedTab = useRef<HTMLButtonElement>(null);
  const tablist = useRef<HTMLDivElement>(null);
  const focusWithin = useRef(false);
  const [focusedId, setFocusedId] = useState<string | undefined>(selectedId);
  const entryId = layouts.some(layout => layout.id === focusedId) ? focusedId
    : layouts.some(layout => layout.id === selectedId) ? selectedId : layouts[0]?.id;
  useEffect(() => { setFocusedId(selectedId); }, [selectedId]);
  useEffect(() => {
    selectedTab.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selectedId, layouts]);
  useEffect(() => {
    if (focusWithin.current && document.activeElement === document.body) {
      const fallback = Array.from(tablist.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? []).find(tab => tab.dataset.layoutId === entryId);
      fallback?.focus();
    }
  }, [layouts, entryId]);
  return (
    <div className="glass flex max-w-full items-center gap-1 rounded-xl border p-1 shadow-float">
      <p id={hintId} className="sr-only">{t("layoutKeyboardHint")}</p>
      <div ref={tablist} className="flex min-w-0 items-center gap-1 overflow-x-auto" role="tablist" aria-label={t("layoutsLabel")} aria-describedby={hintId} aria-orientation="horizontal"
        onFocus={() => { focusWithin.current = true; }}
        onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) focusWithin.current = false; }}>
      {layouts.map((layout, index) => {
        const selected = layout.id === selectedId;
        const label = layout.name.trim() || t("unnamedLayout", { number: index + 1 });
        return (
          <button
            key={layout.id}
            type="button"
            role="tab"
            data-layout-id={layout.id}
            tabIndex={disabled ? -1 : layout.id === entryId ? 0 : -1}
            ref={selected ? selectedTab : undefined}
            aria-selected={selected}
            aria-label={label}
            title={layout.building ? `${layout.building.name}: ${layout.building.label} · ${t("buildingFloorPosition", { level: layout.building.level, count: layout.building.floor_count })}` : label}
            disabled={disabled}
            onFocus={() => setFocusedId(layout.id)}
            onClick={() => { if (layout.id !== selectedId) onSelect(layout.id); }}
            onKeyDown={(event) => {
              if (disabled) return;
              if (event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) {
                if (event.key === "Enter" || event.key === " ") event.preventDefault();
                return;
              }
              if (event.altKey || event.ctrlKey || event.metaKey) return;
              const next = event.key === "Home" ? 0 : event.key === "End" ? layouts.length - 1
                : event.key === "ArrowRight" ? (index + 1) % layouts.length
                : event.key === "ArrowLeft" ? (index - 1 + layouts.length) % layouts.length : -1;
              if (next < 0) return;
              event.preventDefault();
              tablist.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
            }}
            className={cn(
              "h-8 max-w-[min(12rem,100%)] shrink-0 truncate rounded-lg px-3 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary disabled:opacity-50",
              selected ? "bg-primary text-primary-foreground shadow-[0_6px_16px_-8px_var(--primary)]" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {layout.building && <span aria-hidden className="mr-1.5 rounded bg-current/10 px-1 text-[10px]">{t("layFloorBadge", { number: layout.building.level })}</span>}
            {label}
          </button>
        );
      })}
      </div>
      <span className="mx-0.5 h-5 w-px bg-border" aria-hidden />
      <LayoutFinder layouts={layouts} selectedId={selectedId} onSelect={onSelect} disabled={disabled} />
      <button
        type="button"
        disabled={disabled}
        aria-label={t("newLayout")}
        title={t("newLayout")}
        onClick={onAddNew}
        className="flex h-8 shrink-0 items-center gap-1 rounded-lg px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
      >
        <Plus className="size-4" aria-hidden />
        <span className="hidden sm:inline">{t("newLayout")}</span>
      </button>
    </div>
  );
}
