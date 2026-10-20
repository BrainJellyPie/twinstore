// Pick a retail format; a mini floor plan previews the generated store (fridges, shelves,
// counter, entrance) before it is created.

import { useQuery } from "@tanstack/react-query";

import * as api from "@/shared/api/client";
import type { Store } from "@/shared/types/domain";
import { cn } from "@/shared/utils/cn";

export interface TemplateChoice {
  templateId: string;
  seed: number;
  currency: string;
  style: "aisles" | "loop" | null;
}

const RACK_COLORS: Record<string, string> = {
  fridge: "#38bdf8",
  shelf: "#f59e0b",
  counter: "#475569",
  entrance: "#22c55e",
  exit: "#22c55e",
};

export function TemplatePicker({ value, onChange }: { value: TemplateChoice; onChange: (v: TemplateChoice) => void }) {
  const { data: templates = [] } = useQuery({
    queryKey: ["store-templates"],
    queryFn: ({ signal }) => api.getStoreTemplates(signal),
    staleTime: Infinity,
  });
  const preview = useQuery({
    queryKey: ["store-templates", value.templateId, value.seed, value.currency, value.style],
    queryFn: ({ signal }) => api.previewStoreTemplate(value.templateId, value.seed, value.currency, value.style, signal),
    enabled: !!value.templateId,
    staleTime: Infinity,
  });

  return (
    <div className="space-y-2">
      <div className="grid max-h-56 grid-cols-2 gap-1.5 overflow-y-auto pr-1">
        {templates.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange({ ...value, templateId: t.id })}
            className={cn(
              "rounded-md border p-2 text-left text-xs transition-colors",
              value.templateId === t.id ? "border-primary bg-primary/5" : "hover:bg-muted/50",
            )}
            title={t.description}
          >
            <div className="font-medium">{t.name}</div>
            <div className="text-muted-foreground">
              {t.grid[0]}×{t.grid[1]} · {t.racks} fixtures · {t.skus} products
            </div>
          </button>
        ))}
      </div>
      {value.templateId && (
        <div className="flex gap-3">
          <div className="w-40 shrink-0">{preview.data ? <FloorPlan store={preview.data} /> : <div className="aspect-square rounded bg-muted" />}</div>
          <div className="flex flex-1 flex-col gap-2 text-xs">
            <p className="text-muted-foreground">{templates.find((t) => t.id === value.templateId)?.description}</p>
            <div className="flex items-center gap-2">
              <span className="w-16 text-muted-foreground">Products</span>
              {(["USD", "KRW"] as const).map((c) => (
                <button key={c} type="button" onClick={() => onChange({ ...value, currency: c })}
                  className={cn("rounded border px-2 py-0.5", value.currency === c ? "border-primary bg-primary/10" : "hover:bg-muted")}>
                  {c === "KRW" ? "한국어 · ₩" : "English · $"}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <span className="w-16 text-muted-foreground">Floor</span>
              {([null, "aisles", "loop"] as const).map((s) => (
                <button key={s ?? "default"} type="button" onClick={() => onChange({ ...value, style: s })}
                  className={cn("rounded border px-2 py-0.5", value.style === s ? "border-primary bg-primary/10" : "hover:bg-muted")}>
                  {s === null ? "Format default" : s === "aisles" ? "Parallel aisles" : "Racetrack loop"}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <span className="w-16 text-muted-foreground">Variant</span>
              <button type="button" className="rounded border px-2 py-0.5 hover:bg-muted" onClick={() => onChange({ ...value, seed: value.seed + 1 })}>
                Shuffle (#{value.seed})
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FloorPlan({ store }: { store: Store }) {
  const [w, h] = store.grid_size;
  return (
    <svg viewBox={`-0.2 -0.2 ${w + 0.4} ${h + 0.4}`} className="w-full rounded border bg-[#f4f1ea]" role="img" aria-label="Floor plan preview">
      <rect x={0} y={0} width={w} height={h} fill="none" stroke="#94a3b8" strokeWidth={0.12} />
      {store.racks.map((r) => (
        <rect
          key={r.id}
          x={r.position[0] + 0.08}
          y={r.position[1] + 0.08}
          width={0.84}
          height={0.84}
          rx={0.12}
          fill={RACK_COLORS[r.type] ?? "#cbd5e1"}
          opacity={r.type === "entrance" || r.type === "exit" ? 0.6 : 0.95}
        >
          <title>{r.rack_name || r.type}</title>
        </rect>
      ))}
    </svg>
  );
}
