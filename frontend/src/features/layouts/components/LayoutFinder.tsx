import { Check, Search } from "lucide-react";
import { useId, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import type { Layout } from "../hooks/useLayouts";

export function LayoutFinder({ layouts, selectedId, onSelect, disabled }: {
  layouts: Layout[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("all");
  const fieldId = useId();
  const terms = search.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const filtered = layouts.filter((layout) => {
    if (group === "single" && layout.building) return false;
    if (group === "building" && !layout.building) return false;
    const text = [layout.name, layout.building?.name, layout.building?.label,
      layout.building ? `${layout.building.level}F` : "", layout.generation?.template_id.replace(/_/g, " "),
      layout.generation?.requirements, layout.generation?.currency].filter(Boolean).join(" ").toLowerCase();
    return terms.every((term) => text.includes(term));
  }).sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId) || b.createdAt.localeCompare(a.createdAt));

  return <Dialog open={open} onOpenChange={(next) => {
    setOpen(next);
    if (next) { setSearch(""); setGroup("all"); }
  }}>
    <DialogTrigger asChild>
      <button type="button" disabled={disabled} aria-label="Find layout" title="Find layout"
        className="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50">
        <Search className="size-4" aria-hidden />
      </button>
    </DialogTrigger>
    <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-xl">
      <DialogHeader>
        <DialogTitle>Find a layout</DialogTitle>
        <DialogDescription>Search names, buildings, floor labels, store formats or saved design briefs.</DialogDescription>
      </DialogHeader>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-40 flex-1 space-y-1">
          <label htmlFor={`${fieldId}-search`} className="text-xs">Search layouts</label>
          <Input id={`${fieldId}-search`} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="e.g. café, 2F, quiet corner…" />
        </div>
        <div className="space-y-1">
          <label htmlFor={`${fieldId}-group`} className="block text-xs">Layout group</label>
          <select id={`${fieldId}-group`} value={group} onChange={(event) => setGroup(event.target.value)}
            className="h-9 rounded-lg border bg-background px-2 text-sm">
            <option value="all">All layouts</option><option value="single">Single floors</option><option value="building">Building floors</option>
          </select>
        </div>
      </div>
      <p role="status" className="text-xs text-muted-foreground">{filtered.length} of {layouts.length} layouts</p>
      <div className="min-h-0 space-y-2 overflow-y-auto" aria-label="Matching layouts">
        {filtered.map((layout) => <button key={layout.id} type="button" disabled={disabled}
          aria-pressed={layout.id === selectedId} data-testid={`layout-search-result-${layout.id}`}
          className={cn("w-full rounded-xl border p-3 text-left hover:bg-muted disabled:opacity-50", layout.id === selectedId && "border-primary bg-primary/5")}
          onClick={() => { onSelect(layout.id); setOpen(false); }}>
          <div className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-sm font-medium">{layout.name}</span>
            {layout.id === selectedId && <Check className="size-4 shrink-0 text-primary" aria-label="Selected layout" />}
          </div>
          {layout.building && <p className="mt-1 text-xs text-muted-foreground">{layout.building.name} · {layout.building.level}F of {layout.building.floor_count} · {layout.building.label}</p>}
          <p className="mt-1 text-xs text-muted-foreground">
            {[layout.generation?.template_id.replace(/_/g, " "), layout.generation?.currency,
              layout.status === "locked" ? "Simulation saved" : layout.status === "running" ? "Running" : "Draft"].filter(Boolean).join(" · ")}
          </p>
          {layout.generation?.requirements && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{layout.generation.requirements}</p>}
        </button>)}
        {filtered.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No matching layouts. Try another name, format or floor.</p>}
      </div>
    </DialogContent>
  </Dialog>;
}
