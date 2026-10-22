import { useI18n } from "@/shared/i18n/i18n";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { RequestError } from "@/shared/components/RequestError";
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
  if (!Number.isSafeInteger(choice.seed)) throw new UserMessageError("optionsInvalidSeed");
  return choice;
}

export function GenerationOptionsFile(props: Props) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const latestProps = useRef(props);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
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
      if (file.size > sizeLimit * 1024) throw new UserMessageError("optionsTooLarge", { limit: sizeLimit });
      const source = (await file.text()).replace(/^\uFEFF/, "");
      const contents: unknown = JSON.parse(source);
      // JSON.parse can round a fractional seed to a safe integer, or underflow it to zero.
      // Read numeric seed tokens as decimals before sending the parsed object for validation.
      const tokens = source.match(/"(?:\\.|[^"\\])*"|[{}[\],:]|[^\s{}[\],:]+/g) ?? [];
      for (let index = 0; index + 2 < tokens.length; index++) {
        const key = tokens[index]!;
        if (!key.startsWith('"') || tokens[index + 1] !== ":" || JSON.parse(key) !== "seed") continue;
        const parts = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(tokens[index + 2]!);
        if (!parts) continue;
        const digits = `${parts[2]}${parts[3] ?? ""}`.replace(/^0+/, "");
        if (!digits) continue;
        const shift = Number(parts[4] ?? "0") - (parts[3]?.length ?? 0);
        const end = digits.length + shift;
        if (!Number.isFinite(end) || end < 1 || end > 16 ||
          (shift < 0 && /[1-9]/.test(digits.slice(end))) ||
          !Number.isSafeInteger(Number(`${parts[1]}${digits.slice(0, end).padEnd(end, "0")}`))) {
          throw new UserMessageError("optionsInvalidSeed");
        }
      }
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
        ? new UserMessageError("optionsInvalidJson")
        : cause instanceof Error ? cause : new UserMessageError("optionsImportFailed"));
    } finally {
      if (!controller.signal.aborted) { setBusy(false); request.current = null; }
    }
  }

  return <div className="space-y-1.5 rounded border p-2 text-xs">
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={!props.canExport || busy} className="rounded border px-2 py-1 disabled:opacity-40" onClick={downloadOptions}>{t(building ? "optionsExportBuilding" : "optionsExport")}</button>
      <button type="button" disabled={busy} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => input.current?.click()}>{t(busy ? "optionsChecking" : building ? "optionsImportBuilding" : "optionsImport")}</button>
      <input ref={input} type="file" accept=".json,application/json" aria-label={t(building ? "optionsBuildingFile" : "optionsLayoutFile")} className="sr-only" tabIndex={-1} disabled={busy}
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void importOptions(file); }} />
    </div>
    <p className="text-muted-foreground">{building
      ? t("optionsBuildingHint")
      : t("optionsLayoutHint")}</p>
    <RequestError error={error} />
  </div>;
}
