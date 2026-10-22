import { useId, useState } from "react";
import type { LayoutOptions, ReservedArea } from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import { AREA_POSITION_LABELS } from "../optionLabels";
import { AREA_POSITIONS, moveReservedArea, swapReservedAreaDimensions } from "../reservedAreaPlacement";

const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";
// Each starting point's label and default area name are translated; the area name is ordinary editable text.
const STARTING_POINTS = [
  { id: "custom", label: "layAreaStart_custom", name: "layAreaName_custom", width: 3, height: 3, zone: "back_left" },
  { id: "consultation", label: "layAreaStart_consultation", name: "layAreaName_consultation", width: 4, height: 3, zone: "back_right" },
  { id: "pickup", label: "layAreaStart_pickup", name: "layAreaName_pickup", width: 3, height: 2, zone: "front_entry" },
  { id: "fitting", label: "layAreaStart_fitting", name: "layAreaName_fitting", width: 3, height: 3, zone: "back_left" },
  { id: "demo", label: "layAreaStart_demo", name: "layAreaName_demo", width: 4, height: 4, zone: "center" },
  { id: "event", label: "layAreaStart_event", name: "layAreaName_event", width: 6, height: 4, zone: "center" },
] as const;

export function ReservedAreasEditor({ areas, onChange, grid, entrance = "left", gateWall = "front" }: {
  areas: ReservedArea[];
  onChange: (areas: ReservedArea[]) => void;
  grid: [number, number];
  entrance?: LayoutOptions["entrance"];
  gateWall?: LayoutOptions["gate_wall"];
}) {
  const { locale, t } = useI18n();
  const id = useId();
  const [startingPoint, setStartingPoint] = useState("custom");
  const validGrid = Number.isInteger(grid[0]) && grid[0] >= 8 && grid[0] <= 40 &&
    Number.isInteger(grid[1]) && grid[1] >= 6 && grid[1] <= 40;
  const update = (index: number, patch: Partial<ReservedArea>) =>
    onChange(areas.map((area, i) => i === index ? { ...area, ...patch } : area));

  function addArea() {
    const point = STARTING_POINTS.find((p) => p.id === startingPoint) ?? STARTING_POINTS[0];
    const sidePickup = point.id === "pickup" && (gateWall === "left" || gateWall === "right");
    const width = Math.min(sidePickup ? point.height : point.width, grid[0] - 2);
    const height = Math.min(sidePickup ? point.width : point.height, grid[1] - 2);
    let x = 2, y = 2;
    if (point.zone === "back_right") x = grid[0] - width - 2;
    if (point.zone === "center") { x = Math.floor((grid[0] - width) / 2); y = Math.floor((grid[1] - height) / 2); }
    if (point.zone === "front_entry") {
      x = entrance === "right" ? grid[0] - width - 2 : entrance === "center" ? Math.floor((grid[0] - width) / 2) : 2;
      y = gateWall === "back" ? 2 : grid[1] - height - 2;
      if (sidePickup) {
        x = gateWall === "left" ? 2 : grid[0] - width - 2;
        y = entrance === "right" ? grid[1] - height - 2 : entrance === "center" ? Math.floor((grid[1] - height) / 2) : 2;
      }
    }
    x = Math.max(1, Math.min(x, grid[0] - width - 1));
    y = Math.max(1, Math.min(y, grid[1] - height - 1));
    const name = t(point.name);
    let sequence = point.id === "custom" ? areas.length + 1 : 1;
    let label = sequence === 1 && point.id !== "custom" ? name : `${name} ${sequence}`;
    while (areas.some((area) => area.label.trim().toLowerCase() === label.toLowerCase())) label = `${name} ${++sequence}`;
    onChange([...areas, { label, x, y, width, height }]);
  }

  return <section className="space-y-2 rounded-md border p-2" aria-label={t("layReservedAreasRegion")}>
    <p className="text-xs font-medium">{t("layKeepAreasClear")}</p>
    <div className="flex flex-wrap items-end gap-2">
      <div className="min-w-0 flex-1 basis-full space-y-1 text-xs sm:basis-0"><label htmlFor={`${id}-starting-point`}>{t("layAreaStartingPoint")}</label>
        <select id={`${id}-starting-point`} className={controlClass} value={startingPoint} onChange={(event) => setStartingPoint(event.target.value)}>
          {STARTING_POINTS.map((point) => <option key={point.id} value={point.id}>{t(point.label)}</option>)}
        </select>
      </div>
      <button type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
        disabled={areas.length >= 8 || !validGrid} onClick={addArea}>{t("layAddReservedArea")}</button>
    </div>
    <p className="text-[11px] text-muted-foreground">{t("layStartingPointsHint")}</p>
    <p className="text-[11px] text-muted-foreground">{t("layReserveHint")}</p>
    {areas.map((area, index) => <fieldset key={index} className="space-y-2 rounded border p-2">
      <legend className="px-1 text-xs">{t("layAreaNumber", { number: index + 1 })}</legend>
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1 space-y-1 text-xs">
          <label htmlFor={`${id}-${index}-label`}>{t("layAreaNameLabel", { number: index + 1 })}</label>
          <input id={`${id}-${index}-label`} className={controlClass} value={area.label} maxLength={80}
            onChange={(e) => update(index, { label: e.target.value })} />
        </div>
        <button type="button" className="rounded border px-2 py-1.5 text-xs hover:bg-muted"
          aria-label={t("layRemoveArea", { number: index + 1 })} onClick={() => onChange(areas.filter((_, i) => i !== index))}>{t("remove")}</button>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {([
          ["x", "layAreaStartColumn", 1], ["y", "layAreaStartRow", 1], ["width", "layWidth", 0], ["height", "layDepth", 0],
        ] as const).map(([key, label, offset]) => <div key={key} className="space-y-1 text-xs">
          <label htmlFor={`${id}-${index}-${key}`}>{t(label)}</label>
          <input id={`${id}-${index}-${key}`} aria-label={t("layAreaField", { number: index + 1, field: t(label).toLocaleLowerCase(locale) })}
            className={controlClass} type="number" min={1 + offset} max={38 + offset} step={1}
            value={Number.isFinite(area[key]) ? area[key] + offset : ""}
            onChange={(e) => update(index, { [key]: e.target.value === "" ? NaN : Number(e.target.value) - offset })} />
        </div>)}
      </div>
      <div className="space-y-1 text-xs">
        <p>{t("layMoveAreaTo")}</p>
        <div className="flex flex-wrap gap-1.5">
          {AREA_POSITIONS.map(([position]) => {
            const moved = moveReservedArea(area, grid, position);
            const label = t(AREA_POSITION_LABELS[position]);
            return <button key={position} type="button" aria-label={t("layMoveAreaToPosition", { number: index + 1, position: label.toLocaleLowerCase(locale) })}
              className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-40" disabled={!moved}
              onClick={() => { if (moved) update(index, moved); }}>{label}</button>;
          })}
          <button type="button" aria-label={t("laySwapAreaDims", { number: index + 1 })}
            className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-40"
            disabled={!swapReservedAreaDimensions(area, grid)} onClick={() => {
              const swapped = swapReservedAreaDimensions(area, grid);
              if (swapped) update(index, swapped);
            }}>{t("laySwapWidthDepth")}</button>
        </div>
        <p className="text-[11px] text-muted-foreground">{t("layMoveAreaHint")}</p>
      </div>
    </fieldset>)}
    {areas.length > 0 && <p className="text-[11px] text-muted-foreground">{t("layDashedHint")}</p>}
  </section>;
}
