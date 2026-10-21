import { useEffect, useLayoutEffect, useRef, useState } from "react";
import * as api from "@/shared/api/client";
import { DEFAULT_TEMPLATE_CHOICE, templateRequest, type TemplateChoice } from "../templateOptions";

export function LayoutOptionsFile({ value, onChange, canExport }: {
  value: TemplateChoice;
  onChange: (value: TemplateChoice) => void;
  canExport: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const latestOnChange = useRef(onChange);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useLayoutEffect(() => { latestOnChange.current = onChange; }, [onChange]);
  useEffect(() => () => request.current?.abort(), []);

  function downloadOptions() {
    const { source_setup_id: _source, name: _name, ...layout } = templateRequest(value);
    const preset: api.LayoutPreset = { format: "twinstore-layout-options", version: 1, layout };
    const url = URL.createObjectURL(new Blob([JSON.stringify(preset, null, 2) + "\n"], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `twinstore-${value.templateId}-options.json`;
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
      if (file.size > 64 * 1024) throw new Error("Choose an options file smaller than 64 KB.");
      const contents: unknown = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
      if (controller.signal.aborted) return;
      const preset = await api.validateLayoutPreset(contents, controller.signal);
      if (controller.signal.aborted) return;
      const { template_id, source_setup_id: _source, name: _name, ...options } = preset.layout;
      latestOnChange.current({ ...DEFAULT_TEMPLATE_CHOICE, ...options, templateId: template_id });
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof SyntaxError
        ? "This file is not valid JSON. Choose a TwinStore layout options file."
        : cause instanceof Error ? cause.message : "Could not import layout options.");
    } finally {
      if (!controller.signal.aborted) { setBusy(false); request.current = null; }
    }
  }

  return <div className="space-y-1.5 rounded border p-2 text-xs">
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={!canExport || busy} className="rounded border px-2 py-1 disabled:opacity-40" onClick={downloadOptions}>Export options</button>
      <button type="button" disabled={busy} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => input.current?.click()}>{busy ? "Checking options…" : "Import options"}</button>
      <input ref={input} type="file" accept=".json,application/json" aria-label="Import layout options file" className="sr-only" tabIndex={-1} disabled={busy}
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void importOptions(file); }} />
    </div>
    <p className="text-muted-foreground">Reuse this floor's generation settings and design brief in another project. Manual fixture and product edits are not included. Import replaces the current generation options.</p>
    {error && <p role="alert" className="text-destructive">{error}</p>}
  </div>;
}
