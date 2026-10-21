import { useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { Receipt, Upload } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { readReceipts, uploadFidelity, type FidelityMetric } from "@/shared/api/client";
import { ReceiptReviewPanel } from "./ReceiptReviewPanel";

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
  good: "tone-good",
  fair: "tone-warn",
  poor: "tone-bad",
} as const;

// Validate a run against a real POS export of the same store.
export function FidelitySection({ projectId, runId }: { projectId: string; runId: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const receiptRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({ mutationFn: (file: File) => uploadFidelity(projectId, runId, file) });
  const receipts = useMutation({
    mutationFn: (files: File[]) => readReceipts(projectId, files, { runId }),
  });
  const report = upload.data;

  return (
    <div className="border-t px-3 py-3">
      <div className="mb-1 flex items-center justify-between">
        <div className="section-title">Validate against real sales</div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-2 text-xs"
            disabled={receipts.isPending || upload.isPending}
            onClick={() => receiptRef.current?.click()}
            title="Photograph receipts: a vision model reads them into POS lines"
          >
            <Receipt className="size-3" />
            {receipts.isPending ? "Reading…" : "Receipts"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 px-2 text-xs"
            disabled={upload.isPending || receipts.isPending}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="size-3" />
            {upload.isPending ? "Scoring…" : "Upload POS"}
          </Button>
        </div>
        <input
          ref={receiptRef}
          type="file"
          multiple
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) receipts.mutate(files);
            e.target.value = "";
          }}
        />
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) {
              receipts.reset();
              upload.mutate(file);
            }
            e.target.value = "";
          }}
        />
      </div>
      {!report && !upload.isError && (
        <p className="text-xs text-muted-foreground">
          CSV/XLSX with a receipt id and SKU per line (quantity, unit price and time optional). Scores how
          closely simulated sales match the real ones.
        </p>
      )}
      {receipts.data && (
        <ReceiptReviewPanel key={`${projectId}:${runId}:${receipts.submittedAt}`} projectId={projectId} runId={runId}
          result={receipts.data} scoring={upload.isPending} onScore={(file) => upload.mutate(file)} />
      )}
      {receipts.isError && (
        <p className="text-xs text-destructive">{receipts.error instanceof Error ? receipts.error.message : "Could not read the receipts"}</p>
      )}
      {upload.isError && (
        <p className="text-xs text-destructive">
          {upload.error instanceof Error ? upload.error.message : "Upload failed"}
        </p>
      )}
      {report && (
        <div className="mt-2 space-y-1.5">
          <div className="text-xs text-muted-foreground">
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
                    {v && <span className={`rounded px-1 text-[0.72rem] ${VERDICT_CLASS[v]}`}>{v}</span>}
                  </span>
                </li>
              );
            })}
          </ul>
          {report.notes.map((n) => (
            <p key={n} className="text-xs text-muted-foreground">{n}</p>
          ))}
        </div>
      )}
    </div>
  );
}
