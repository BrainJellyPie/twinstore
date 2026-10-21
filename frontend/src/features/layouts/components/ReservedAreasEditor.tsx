import { useId } from "react";
import type { ReservedArea } from "@/shared/api/client";

const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";

export function ReservedAreasEditor({ areas, onChange }: {
  areas: ReservedArea[];
  onChange: (areas: ReservedArea[]) => void;
}) {
  const id = useId();
  const update = (index: number, patch: Partial<ReservedArea>) =>
    onChange(areas.map((area, i) => i === index ? { ...area, ...patch } : area));

  return <section className="space-y-2 rounded-md border p-2" aria-label="Reserved floor areas">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-xs font-medium">Keep areas clear</span>
      <button type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
        disabled={areas.length >= 8} onClick={() => onChange([...areas,
          { label: `Reserved area ${areas.length + 1}`, x: 2, y: 2, width: 3, height: 3 },
        ])}>Add reserved area</button>
    </div>
    <p className="text-[11px] text-muted-foreground">Reserve open space for consultation, pickup, events or later editing. Columns start at 1 on the left; rows start at 1 at the back wall. Keep rectangles inside the outer wall cells.</p>
    {areas.map((area, index) => <fieldset key={index} className="space-y-2 rounded border p-2">
      <legend className="px-1 text-xs">Area {index + 1}</legend>
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1 space-y-1 text-xs">
          <label htmlFor={`${id}-${index}-label`}>Area {index + 1} name</label>
          <input id={`${id}-${index}-label`} className={controlClass} value={area.label} maxLength={80}
            onChange={(e) => update(index, { label: e.target.value })} />
        </div>
        <button type="button" className="rounded border px-2 py-1.5 text-xs hover:bg-muted"
          aria-label={`Remove area ${index + 1}`} onClick={() => onChange(areas.filter((_, i) => i !== index))}>Remove</button>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {([
          ["x", "Start column", 1], ["y", "Start row", 1], ["width", "Width", 0], ["height", "Depth", 0],
        ] as const).map(([key, label, offset]) => <div key={key} className="space-y-1 text-xs">
          <label htmlFor={`${id}-${index}-${key}`}>{label}</label>
          <input id={`${id}-${index}-${key}`} aria-label={`Area ${index + 1} ${label.toLowerCase()}`}
            className={controlClass} type="number" min={1 + offset} max={38 + offset} step={1}
            value={Number.isFinite(area[key]) ? area[key] + offset : ""}
            onChange={(e) => update(index, { [key]: e.target.value === "" ? NaN : Number(e.target.value) - offset })} />
        </div>)}
      </div>
    </fieldset>)}
    {areas.length > 0 && <p className="text-[11px] text-muted-foreground">Dashed outlines mark these areas in the preview. They stay walkable; walls, rooms and service behavior are not added. Manual floor edits can use this space later.</p>}
  </section>;
}
