import { useEffect, useLayoutEffect, useRef, useState } from "react";
import * as api from "@/shared/api/client";
import { DEFAULT_TEMPLATE_CHOICE, templateRequest, type BuildingFloorChoice, type TemplateChoice } from "../templateOptions";

type Props = { canExport: boolean } & (
  { kind: "layout"; value: TemplateChoice; onChange: (value: TemplateChoice) => void }
  | { kind: "building"; value: BuildingFloorChoice[]; onChange: (value: BuildingFloorChoice[]) => void }
);

function portableLayout(value: TemplateChoice): api.GenerateLayoutRequest {
  const { source_setup_id: _source, name: _name, ...layout } = templateRequest(value);
  return layout;
}

function importedChoice({ template_id, source_setup_id: _source, name: _name, ...options }: api.GenerateLayoutRequest): TemplateChoice {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, ...options, templateId: template_id };
  if (!Number.isSafeInteger(choice.seed)) throw new Error("This options file has a seed outside the supported whole-number range. Current settings were kept.");
  return choice;
}

export function GenerationOptionsFile(props: Props) {
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const latestProps = useRef(props);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useLayoutEffect(() => { latestProps.current = props; }, [props]);
  useEffect(() => () => request.current?.abort(), []);
  const building = props.kind === "building";
  const sizeLimit = building ? 256 : 64;

  function downloadOptions() {
    const preset: api.LayoutPreset | api.BuildingPreset = props.kind === "building"
      ? { format: "twinstore-building-options", version: 1, floors: props.value.map((floor) => ({ label: floor.label, layout: portableLayout(floor.choice) })) }
      : { format: "twinstore-layout-options", version: 1, layout: portableLayout(props.value) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(preset, null, 2) + "\n"], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = props.kind === "building" ? "twinstore-building-options.json" : `twinstore-${props.value.templateId}-options.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  async function importOptions(file: File) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError(null);
    try {
      if (file.size > sizeLimit * 1024) throw new Error(`Choose an options file smaller than ${sizeLimit} KB.`);
      const contents: unknown = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
      if (controller.signal.aborted) return;
      if (props.kind === "building") {
        const preset = await api.validateBuildingPreset(contents, controller.signal);
        if (controller.signal.aborted) return;
        const current = latestProps.current;
        if (current.kind !== "building") return;
        current.onChange(preset.floors.map((floor) => ({ label: floor.label, choice: importedChoice(floor.layout) })));
      } else {
        const preset = await api.validateLayoutPreset(contents, controller.signal);
        if (controller.signal.aborted) return;
        const current = latestProps.current;
        if (current.kind !== "layout") return;
        current.onChange(importedChoice(preset.layout));
      }
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof SyntaxError
        ? "This file is not valid JSON. Choose a TwinStore options file."
        : cause instanceof Error ? cause.message : "Could not import layout options.");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); request.current = null; }
    }
  }

  return <div className="space-y-1.5 rounded border p-2 text-xs">
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={!props.canExport || busy} className="rounded border px-2 py-1 disabled:opacity-40" onClick={downloadOptions}>{building ? "Export building options" : "Export options"}</button>
      <button type="button" disabled={busy} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => input.current?.click()}>{busy ? "Checking options…" : building ? "Import building options" : "Import options"}</button>
      <input ref={input} type="file" accept=".json,application/json" aria-label={building ? "Import building options file" : "Import layout options file"} className="sr-only" tabIndex={-1} disabled={busy}
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void importOptions(file); }} />
    </div>
    <p className="text-muted-foreground">{building
      ? "Reuse all floors, their order, labels and generation settings in another project. Import replaces the current floor list after checking every floor. Manual fixture and product edits are not included."
      : "Reuse this floor's generation settings and design brief in another project. Manual fixture and product edits are not included. Import replaces the current generation options."}</p>
    {error && <p role="alert" className="text-destructive">{error}</p>}
  </div>;
}
