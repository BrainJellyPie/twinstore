import { useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { Upload } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { uploadFidelity, type FidelityMetric } from "@/shared/api/client";

function verdict(m: FidelityMetric): "good" | "fair" | "poor" | null {
  if (m.value === null) return null;
  const v = m.value;
  if (m.better === "higher") return v >= 0.8 ? "good" : v >= 0.5 ? "fair" : "poor";
  if (m.better === "closer to 1") {
    const off = Math.abs(Math.log(Math.max(v, 1e-6)));
    return off <= 0.1 ? "good" : off <= 0.35 ? "fair" : "poor";
  }
  return null; // distances have no universal scale
}

const VERDICT_CLASS = {
  good: "bg-emerald-100 text-emerald-800",
  fair: "bg-amber-100 text-amber-800",
  poor: "bg-rose-100 text-rose-800",
} as const;

// Validate a run against a real POS export of the same store.
export function FidelitySection({ projectId, runId }: { projectId: string; runId: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({ mutationFn: (file: File) => uploadFidelity(projectId, runId, file) });
  const report = upload.data;

  return (
    <div className="border-t px-3 py-3">
      <div className="mb-1 flex items-center justify-between">
        <div className="text-xs font-medium">Validate against real sales</div>
        <Button
          variant="outline"
          size="sm"
          className="h-7 gap-1 px-2 text-xs"
          disabled={upload.isPending}
          onClick={() => inputRef.current?.click()}
        >
          <Upload className="size-3" />
          {upload.isPending ? "Scoring…" : "Upload POS"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
      </div>
      {!report && !upload.isError && (
        <p className="text-[11px] text-muted-foreground">
          CSV/XLSX with a receipt id and SKU per line (quantity, unit price and time optional). Scores how
          closely simulated sales match the real ones.
        </p>
      )}
      {upload.isError && (
        <p className="text-xs text-destructive">
          {upload.error instanceof Error ? upload.error.message : "Upload failed"}
        </p>
      )}
      {report && (
        <div className="mt-2 space-y-1.5">
          <div className="text-[11px] text-muted-foreground">
            {report.real_transactions.toLocaleString()} real receipts · {report.sim_customers.toLocaleString()} simulated
            customers · {report.matched_skus} SKUs
          </div>
          <ul className="space-y-1">
            {report.metrics.map((m) => {
              const v = verdict(m);
              return (
                <li key={m.name} className="flex items-center justify-between gap-2 text-xs" title={m.description}>
                  <span className="truncate">{m.name.replace(/_/g, " ")}</span>
                  <span className="flex shrink-0 items-center gap-1.5 tabular-nums">
                    {m.value === null ? "n/a" : m.value.toFixed(3)}
                    {v && <span className={`rounded px-1 text-[10px] ${VERDICT_CLASS[v]}`}>{v}</span>}
                  </span>
                </li>
              );
            })}
          </ul>
          {report.notes.map((n) => (
            <p key={n} className="text-[11px] text-muted-foreground">{n}</p>
          ))}
        </div>
      )}
    </div>
  );
}
