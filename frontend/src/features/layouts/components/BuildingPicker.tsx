import { useId, useState } from "react";
import { cn } from "@/shared/utils/cn";
import { BUILDING_PRESETS, DEFAULT_TEMPLATE_CHOICE, buildingPreset, validBuildingFloors, type BuildingFloorChoice } from "../templateOptions";
import { TemplatePicker } from "./TemplatePicker";

export function BuildingPicker({ floors, onChange }: { floors: BuildingFloorChoice[]; onChange: (floors: BuildingFloorChoice[]) => void }) {
  const [active, setActive] = useState(0);
  const fieldId = useId();
  const index = Math.min(active, floors.length - 1);
  const floor = floors[index];

  const addFloor = () => {
    let n = floors.length + 1;
    while (floors.some((f) => f.label === `Level ${n}`)) n++;
    onChange([...floors, { label: `Level ${n}`, choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "design_showroom" } }]);
    setActive(floors.length);
  };

  return <div className="space-y-3 rounded-lg border p-3">
    <p className="text-xs text-muted-foreground">Create 2–6 linked floor layouts. Each floor is edited and simulated independently; shoppers do not travel between floors.</p>
    <div className="flex flex-wrap gap-1.5" aria-label="Building starting points">
      {BUILDING_PRESETS.map((p) => <button key={p.id} type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted"
        onClick={() => { onChange(buildingPreset(p.id)); setActive(0); }}>{p.name}</button>)}
    </div>
    <div className="flex flex-wrap gap-1.5" aria-label="Building floors">
      {floors.map((f, i) => <button key={i} type="button" aria-pressed={i === index}
        className={cn("rounded border px-2 py-1 text-xs", i === index ? "border-primary bg-primary/10" : "hover:bg-muted")}
        onClick={() => setActive(i)}>{i + 1}F · {f.label || "Unnamed floor"}</button>)}
      <button type="button" disabled={floors.length >= 6} onClick={addFloor} className="rounded border px-2 py-1 text-xs disabled:opacity-40">Add floor</button>
    </div>
    {floor && <>
      <div className="flex items-end gap-2">
        <div className="flex-1 space-y-1">
          <label htmlFor={fieldId} className="text-xs">Floor label</label>
          <input id={fieldId} className="w-full rounded border bg-background px-2 py-1.5 text-xs" value={floor.label} maxLength={80}
            onChange={(e) => onChange(floors.map((f, i) => i === index ? { ...f, label: e.target.value } : f))} />
        </div>
        <button type="button" disabled={floors.length <= 2} className="rounded border px-2 py-1.5 text-xs disabled:opacity-40"
          onClick={() => { onChange(floors.filter((_, i) => i !== index)); setActive(Math.max(0, index - 1)); }}>Remove floor</button>
      </div>
      <TemplatePicker key={index} value={floor.choice} onChange={(choice) => onChange(floors.map((f, i) => i === index ? { ...f, choice } : f))} />
    </>}
    {!validBuildingFloors(floors) && <p role="alert" className="text-xs text-destructive">Each floor needs a unique label and valid grid dimensions.</p>}
  </div>;
}
