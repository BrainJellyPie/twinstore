import { useId, useState } from "react";
import { cn } from "@/shared/utils/cn";
import { applyLayoutPriority, BUILDING_PRESETS, DEFAULT_TEMPLATE_CHOICE, buildingPreset, choiceFromGeneration, validBuildingFloors, type BuildingFloorChoice } from "../templateOptions";
import type { Layout } from "../hooks/useLayouts";
import { TemplatePicker } from "./TemplatePicker";
import { GenerationOptionsFile } from "./GenerationOptionsFile";
import { ReviewBuildingFloors } from "./ReviewBuildingFloors";

export function BuildingPicker({ floors, onChange, defaultCurrency = "USD", sourceLayouts = [] }: {
  floors: BuildingFloorChoice[];
  onChange: (floors: BuildingFloorChoice[]) => void;
  defaultCurrency?: string;
  sourceLayouts?: Layout[];
}) {
  const [active, setActive] = useState(0);
  const [pickerVersion, setPickerVersion] = useState(0);
  const [reviewOpen, setReviewOpen] = useState(false);
  const fieldId = useId();
  const index = Math.min(active, floors.length - 1);
  const floor = floors[index];

  const addFloor = () => {
    let n = floors.length + 1;
    while (floors.some((f) => f.label === `Level ${n}`)) n++;
    onChange([...floors, { label: `Level ${n}`, choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "design_showroom", currency: defaultCurrency } }]);
    setActive(floors.length);
  };

  const moveFloor = (offset: -1 | 1) => {
    const target = index + offset;
    if (target < 0 || target >= floors.length) return;
    const next = [...floors];
    [next[index], next[target]] = [next[target]!, next[index]!];
    onChange(next);
    setActive(target);
  };

  const duplicateFloor = () => {
    if (!floor || floors.length >= 6) return;
    const base = floor.label.trim().slice(0, 68) || "Floor";
    let n = 1;
    while (floors.some((f) => f.label.trim().toLowerCase() === `${base} copy ${n}`.toLowerCase())) n++;
    const copy = { label: `${base} copy ${n}`, choice: { ...floor.choice } };
    onChange([...floors.slice(0, index + 1), copy, ...floors.slice(index + 1)]);
    setActive(index + 1);
  };

  return <div className="space-y-3 rounded-lg border p-3">
    <p className="text-xs text-muted-foreground">Create 2–6 linked floor layouts. Each floor is edited and simulated independently; shoppers do not travel between floors.</p>
    <GenerationOptionsFile key={pickerVersion} kind="building" value={floors} canExport={validBuildingFloors(floors)} onChange={(next) => {
      onChange(next); setActive(0); setPickerVersion((version) => version + 1);
    }} />
    <div className="flex flex-wrap gap-1.5" aria-label="Building starting points">
      {BUILDING_PRESETS.map((p) => <button key={p.id} type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted"
        onClick={() => { onChange(buildingPreset(p.id, defaultCurrency)); setActive(0); setPickerVersion((version) => version + 1); }}>{p.name}</button>)}
    </div>
    <div className="flex flex-wrap gap-1.5" aria-label="Building floors">
      {floors.map((f, i) => <button key={i} type="button" aria-pressed={i === index}
        className={cn("rounded border px-2 py-1 text-xs", i === index ? "border-primary bg-primary/10" : "hover:bg-muted")}
        onClick={() => setActive(i)}>{i + 1}F · {f.label || "Unnamed floor"}</button>)}
      <button type="button" disabled={floors.length >= 6} onClick={addFloor} className="rounded border px-2 py-1 text-xs disabled:opacity-40">Add floor</button>
    </div>
    <ReviewBuildingFloors floors={floors} onEdit={setActive} open={reviewOpen} onOpenChange={setReviewOpen} />
    {floor && <>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 space-y-1">
          <label htmlFor={fieldId} className="text-xs">Floor label</label>
          <input id={fieldId} className="w-full rounded border bg-background px-2 py-1.5 text-xs" value={floor.label} maxLength={80}
            onChange={(e) => onChange(floors.map((f, i) => i === index ? { ...f, label: e.target.value } : f))} />
        </div>
        <button type="button" disabled={floors.length <= 2} className="rounded border px-2 py-1.5 text-xs disabled:opacity-40"
          onClick={() => {
            onChange(floors.filter((_, i) => i !== index)); setActive(Math.max(0, index - 1));
            setPickerVersion((version) => version + 1);
          }}>Remove floor</button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <button type="button" disabled={index === 0} onClick={() => moveFloor(-1)}
          className="rounded border px-2 py-1 text-xs disabled:opacity-40">Move to lower level</button>
        <button type="button" disabled={index === floors.length - 1} onClick={() => moveFloor(1)}
          className="rounded border px-2 py-1 text-xs disabled:opacity-40">Move to higher level</button>
        <button type="button" disabled={floors.length >= 6} onClick={duplicateFloor}
          className="rounded border px-2 py-1 text-xs disabled:opacity-40">Duplicate floor</button>
      </div>
      {floor.choice.sourceSetupId && sourceLayouts.length > 0 && <div className="space-y-1 text-xs">
        <label htmlFor={`${fieldId}-source`}>Saved floor settings</label>
        <select id={`${fieldId}-source`} className="w-full rounded border bg-background px-2 py-1.5" value={floor.choice.sourceSetupId}
          onChange={(event) => {
            const source = sourceLayouts.find((layout) => layout.id === event.target.value);
            if (source?.generation) {
              onChange(floors.map((f, i) => i === index
                ? { ...f, choice: choiceFromGeneration(source.generation!, source.id) } : f));
              setPickerVersion((version) => version + 1);
            }
          }}>
          {sourceLayouts.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
        </select>
      </div>}
      <TemplatePicker key={`${index}-${pickerVersion}`} value={floor.choice} budgetCurrency={defaultCurrency}
        onChange={(choice) => onChange(floors.map((f, i) => i === index ? { ...f, choice } : f))}
        onApplyDesignToAll={(design_theme) => onChange(floors.map((f) => ({ ...f, choice: { ...f.choice, design_theme } })))}
        onApplyCurrencyToAll={(currency) => onChange(floors.map((f) => ({ ...f, choice: { ...f.choice, currency } })))}
        onApplyHoursToAll={(hours) => onChange(floors.map((f) => ({ ...f, choice: { ...f.choice, ...hours, closed_days: [...hours.closed_days] } })))}
        onApplySizeToAll={(size) => {
          onChange(floors.map((f) => ({ ...f, choice: { ...f.choice, ...size } })));
          setReviewOpen(true);
        }}
        onApplyPriorityToAll={(priority) => {
          onChange(floors.map((f) => ({ ...f, choice: applyLayoutPriority(f.choice, priority) })));
          setReviewOpen(true);
        }}
        sharedSize={floor.choice.width != null && floor.choice.height != null &&
          floors.every((f) => f.choice.width === floor.choice.width && f.choice.height === floor.choice.height)}
        sharedHours={floor.choice.open_hour != null && floor.choice.close_hour != null && floor.choice.closed_days != null &&
          floors.every((f) => f.choice.open_hour === floor.choice.open_hour && f.choice.close_hour === floor.choice.close_hour &&
            f.choice.closed_days?.length === floor.choice.closed_days?.length &&
            f.choice.closed_days?.every((day) => floor.choice.closed_days?.includes(day)))}
        sharedDesign={floors.every((f) => f.choice.design_theme === floor.choice.design_theme) ? floor.choice.design_theme ?? undefined : undefined}
        sharedCurrency={floors.every((f) => f.choice.currency === floor.choice.currency) ? floor.choice.currency : undefined} />
    </>}
    {!validBuildingFloors(floors) && <p role="alert" className="text-xs text-destructive">Each floor needs a unique label and valid layout values.</p>}
  </div>;
}
