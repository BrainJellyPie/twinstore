import { useId, useState } from "react";
import type { LayoutOptions, ReservedArea } from "@/shared/api/client";

const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";
const STARTING_POINTS = [
  { id: "custom", label: "Custom area", name: "Reserved area", width: 3, height: 3, zone: "back_left" },
  { id: "consultation", label: "Consultation corner", name: "Consultation", width: 4, height: 3, zone: "back_right" },
  { id: "pickup", label: "Pickup near the entrance", name: "Pickup", width: 3, height: 2, zone: "front_entry" },
  { id: "fitting", label: "Fitting area", name: "Fitting area", width: 3, height: 3, zone: "back_left" },
  { id: "demo", label: "Central demonstration area", name: "Demonstration", width: 4, height: 4, zone: "center" },
  { id: "event", label: "Central event space", name: "Event space", width: 6, height: 4, zone: "center" },
] as const;

export function ReservedAreasEditor({ areas, onChange, grid, entrance = "left" }: {
  areas: ReservedArea[];
  onChange: (areas: ReservedArea[]) => void;
  grid: [number, number];
  entrance?: LayoutOptions["entrance"];
}) {
  const id = useId();
  const [startingPoint, setStartingPoint] = useState("custom");
  const validGrid = Number.isInteger(grid[0]) && grid[0] >= 8 && grid[0] <= 40 &&
    Number.isInteger(grid[1]) && grid[1] >= 6 && grid[1] <= 40;
  const update = (index: number, patch: Partial<ReservedArea>) =>
    onChange(areas.map((area, i) => i === index ? { ...area, ...patch } : area));

  function addArea() {
    const point = STARTING_POINTS.find((p) => p.id === startingPoint) ?? STARTING_POINTS[0];
    const width = Math.min(point.width, grid[0] - 2), height = Math.min(point.height, grid[1] - 2);
    let x = 2, y = 2;
    if (point.zone === "back_right") x = grid[0] - width - 2;
    if (point.zone === "center") { x = Math.floor((grid[0] - width) / 2); y = Math.floor((grid[1] - height) / 2); }
    if (point.zone === "front_entry") {
      x = entrance === "right" ? grid[0] - width - 2 : entrance === "center" ? Math.floor((grid[0] - width) / 2) : 2;
      y = grid[1] - height - 2;
    }
    x = Math.max(1, Math.min(x, grid[0] - width - 1));
    y = Math.max(1, Math.min(y, grid[1] - height - 1));
    let sequence = point.id === "custom" ? areas.length + 1 : 1;
    let label = sequence === 1 && point.id !== "custom" ? point.name : `${point.name} ${sequence}`;
    while (areas.some((area) => area.label.trim().toLowerCase() === label.toLowerCase())) label = `${point.name} ${++sequence}`;
    onChange([...areas, { label, x, y, width, height }]);
  }

  return <section className="space-y-2 rounded-md border p-2" aria-label="Reserved floor areas">
    <p className="text-xs font-medium">Keep areas clear</p>
    <div className="flex flex-wrap items-end gap-2">
      <div className="min-w-0 flex-1 space-y-1 text-xs"><label htmlFor={`${id}-starting-point`}>Area starting point</label>
        <select id={`${id}-starting-point`} className={controlClass} value={startingPoint} onChange={(event) => setStartingPoint(event.target.value)}>
          {STARTING_POINTS.map((point) => <option key={point.id} value={point.id}>{point.label}</option>)}
        </select>
      </div>
      <button type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
        disabled={areas.length >= 8 || !validGrid} onClick={addArea}>Add reserved area</button>
    </div>
    <p className="text-[11px] text-muted-foreground">Starting points fit the current floor and remain editable. They can overlap; adjust positions if you need separate areas.</p>
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
