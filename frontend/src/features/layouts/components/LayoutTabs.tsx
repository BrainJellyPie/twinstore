// Layout switching/adding must work in every mode (ready/running/playback). Each
// layout has its own simulation history, so navigation cannot be gated on the
// current mode. `disabled` is reserved for ProjectShell.navigationDisabled and
// blocks both the tabs and the Add button together.

import { Plus } from "lucide-react";

import { cn } from "@/shared/utils/cn";

import type { Layout } from "../hooks/useLayouts";

export interface LayoutTabsProps {
  layouts: Layout[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  onAddNew: () => void;
  disabled?: boolean;
}

export function LayoutTabs({ layouts, selectedId, onSelect, onAddNew, disabled = false }: LayoutTabsProps) {
  return (
    <div className="glass flex max-w-full items-center gap-1 rounded-xl border p-1 shadow-float">
      <div className="flex min-w-0 items-center gap-1 overflow-x-auto" role="tablist" aria-label="Layouts">
      {layouts.map((layout) => {
        const selected = layout.id === selectedId;
        return (
          <button
            key={layout.id}
            type="button"
            role="tab"
            aria-selected={selected}
            title={layout.building ? `${layout.building.name}: ${layout.building.label} (${layout.building.level}/${layout.building.floor_count} floors)` : layout.name}
            disabled={disabled}
            onClick={() => onSelect(layout.id)}
            className={cn(
              "h-8 rounded-lg px-3 text-sm font-medium whitespace-nowrap transition-colors disabled:opacity-50",
              selected ? "bg-primary text-primary-foreground shadow-[0_6px_16px_-8px_var(--primary)]" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {layout.building && <span className="mr-1.5 rounded bg-current/10 px-1 text-[10px]">{layout.building.level}F</span>}
            {layout.name}
          </button>
        );
      })}
      </div>
      <span className="mx-0.5 h-5 w-px bg-border" aria-hidden />
      <button
        type="button"
        disabled={disabled}
        onClick={onAddNew}
        className="flex h-8 shrink-0 items-center gap-1 rounded-lg px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
      >
        <Plus className="size-4" aria-hidden />
        New layout
      </button>
    </div>
  );
}
