import { useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { Receipt, Upload } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { readReceipts, uploadFidelity, type FidelityMetric } from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
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
const VERDICT_LABEL: Record<keyof typeof VERDICT_CLASS, MessageKey> = { good: "fidelityGood", fair: "fidelityFair", poor: "fidelityPoor" };

// A metric by a plain name in the selected language; its id (a statistic such as "sku_ndcg@10") stays in the tooltip.
const METRIC_LABELS: Record<string, MessageKey> = {
  sku_spearman: "fidelityMetric_sku_spearman", sku_js_similarity: "fidelityMetric_sku_js_similarity",
  "sku_ndcg@all": "fidelityMetric_sku_ndcg_all", rack_spearman: "fidelityMetric_rack_spearman",
  rack_js_similarity: "fidelityMetric_rack_js_similarity", basket_units_w1: "fidelityMetric_basket_units_w1",
  basket_units_mean_ratio: "fidelityMetric_basket_units_mean_ratio", basket_units_var_ratio: "fidelityMetric_basket_units_var_ratio",
  basket_value_w1: "fidelityMetric_basket_value_w1", basket_value_mean_ratio: "fidelityMetric_basket_value_mean_ratio",
  hourly_js_similarity: "fidelityMetric_hourly_js_similarity",
};
function metricLabel(name: string, t: (key: MessageKey, params?: Record<string, string | number>) => string): string {
  const top = /^sku_ndcg@(\d+)$/.exec(name);
  if (top) return t("fidelityMetric_sku_ndcg_top", { k: Number(top[1]) });
  return Object.prototype.hasOwnProperty.call(METRIC_LABELS, name) ? t(METRIC_LABELS[name]!) : name.replace(/_/g, " ");
}

// Validate a run against a real POS export of the same store.
export function FidelitySection({ projectId, runId }: { projectId: string; runId: string }) {
  const { locale, t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const receiptRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationKey: ["fidelity", projectId, runId],
    mutationFn: (file: File) => uploadFidelity(projectId, runId, file),
  });
  const receipts = useMutation({
    mutationKey: ["receipt-readings", projectId, runId],
    mutationFn: (files: File[]) => readReceipts(projectId, files, { runId }),
  });
  const report = upload.data;

  return (
    <div className="border-t px-3 py-3">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <div className="section-title">{t("fidelityTitle")}</div>
        <div className="flex flex-wrap justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-2 text-xs"
            disabled={receipts.isPending || upload.isPending}
            onClick={() => receiptRef.current?.click()}
            title={t("fidelityReceiptsHint")}
          >
            <Receipt className="size-3" />
            {receipts.isPending ? t("fidelityReading") : t("fidelityReceipts")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 px-2 text-xs"
            disabled={upload.isPending || receipts.isPending}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="size-3" />
            {upload.isPending ? t("fidelityScoring") : t("fidelityUpload")}
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
        <p className="text-xs text-muted-foreground">{t("fidelityHint")}</p>
      )}
      {receipts.data && (
        <ReceiptReviewPanel key={`${projectId}:${runId}:${receipts.submittedAt}`} projectId={projectId} runId={runId}
          result={receipts.data} scoring={upload.isPending} onScore={(file) => upload.mutate(file)} />
      )}
      {receipts.isError && (
        <p role="alert" className="text-xs text-destructive">{receipts.error instanceof Error ? receipts.error.message : t("fidelityReadFailed")}</p>
      )}
      {upload.isError && (
        <p role="alert" className="text-xs text-destructive">
          {upload.error instanceof Error ? upload.error.message : t("fidelityUploadFailed")}
        </p>
      )}
      {report && (
        <div className="mt-2 space-y-1.5">
          <div className="text-xs text-muted-foreground">
            {t("fidelitySummary", { receipts: report.real_transactions, customers: report.sim_customers, skus: report.matched_skus })}
          </div>
          <ul className="space-y-1">
            {report.metrics.map((m) => {
              const v = verdict(m);
              return (
                <li key={m.name} className="flex items-center justify-between gap-2 text-xs" title={m.description}>
                  <span className="truncate" title={m.name}>{metricLabel(m.name, t)}</span>
                  <span className="flex shrink-0 items-center gap-1.5 tabular-nums">
                    {m.value === null ? t("notAvailable") : m.value.toLocaleString(locale, { minimumFractionDigits: 3, maximumFractionDigits: 3 })}
                    {v && <span className={`rounded px-1 text-[0.72rem] ${VERDICT_CLASS[v]}`}>{t(VERDICT_LABEL[v])}</span>}
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
