import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { useRunDiagnostics } from "../hooks";
import { engineLabel } from "../labels";

// Data-quality, reproducibility and cost facts of a run.
export function DiagnosticsSection({ projectId, runId }: { projectId: string; runId: string }) {
  const { data } = useRunDiagnostics(projectId, runId);
  const [open, setOpen] = useState(false);
  if (!data) return null;

  const d = data.diagnostics;
  const m = data.manifest;
  const t = data.token_usage;
  const failed = d.failed_customers ?? [];
  const violations = Object.values(d.buy_violations ?? {}).reduce((a, b) => a + b, 0);
  const issues = failed.length + (d.dropped_invalid_buys ?? 0) + violations;

  return (
    <div className="border-t px-3 py-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-xs font-medium"
        aria-expanded={open}
      >
        <span className="flex items-center gap-1">
          {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
          Run diagnostics
        </span>
        <span className={issues > 0 ? "text-warn" : "text-muted-foreground"}>
          {issues > 0 ? `${issues} issue${issues === 1 ? "" : "s"}` : "clean"}
        </span>
      </button>
      {open && (
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Engine</dt>
          <dd className="text-right">{engineLabel(m.engine_type)}{m.model ? ` · ${m.model}` : ""}</dd>
          <dt className="text-muted-foreground">Seed / replicate</dt>
          <dd className="text-right tabular-nums">{m.seed ?? "—"} / {m.replicate ?? "—"}</dd>
          <dt className="text-muted-foreground">Exposure · ordering</dt>
          <dd className="text-right">{m.exposure_model || "legacy"} · {m.route_ordering || "legacy"}</dd>
          <dt className="text-muted-foreground">Customers simulated</dt>
          <dd className="text-right tabular-nums">
            {(d.requested_customers ?? 0) - failed.length} / {d.requested_customers ?? "—"}
          </dd>
          <dt className="text-muted-foreground">Hallucinated buys dropped</dt>
          <dd className="text-right tabular-nums">{d.dropped_invalid_buys ?? 0}</dd>
          <dt className="text-muted-foreground">Over-budget buys dropped</dt>
          <dd className="text-right tabular-nums">{d.dropped_over_budget ?? 0}</dd>
          <dt className="text-muted-foreground">Placement violations</dt>
          <dd className="text-right tabular-nums">{violations}</dd>
          <dt className="text-muted-foreground">LLM requests (cached)</dt>
          <dd className="text-right tabular-nums">
            {(t.requests ?? 0).toLocaleString()} ({(t.cached_requests ?? 0).toLocaleString()})
          </dd>
          <dt className="text-muted-foreground">Tokens</dt>
          <dd className="text-right tabular-nums">{(t.total_tokens ?? 0).toLocaleString()}</dd>
          {m.store_fingerprint && (
            <>
              <dt className="text-muted-foreground">Layout fingerprint</dt>
              <dd className="truncate text-right font-mono text-[0.72rem]">{m.store_fingerprint}</dd>
            </>
          )}
          {failed.length > 0 && (
            <div className="col-span-2 mt-1 rounded-md border bg-muted/40 p-2">
              <div className="mb-1 font-medium">Failed customers</div>
              <ul className="max-h-28 space-y-0.5 overflow-y-auto">
                {failed.slice(0, 50).map((f) => (
                  <li key={f.persona_id} className="truncate" title={f.reason}>
                    <span className="font-mono">{f.persona_id}</span> — {f.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}
