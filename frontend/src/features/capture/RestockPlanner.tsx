import { useState } from "react";
import { Download } from "lucide-react";

import type { AuditReport, CaptureBox } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { planRestocking, restockCsv, type RestockAssumptions, type RestockEvidence } from "./restockPlanner";

const LABEL: Record<RestockEvidence, MessageKey> = {
  positive_lower_bound: "capRestockLabelPositive", crosses_zero: "capRestockLabelCrosses",
  no_interval: "capRestockLabelNoInterval", nonpositive_interval: "capRestockLabelNonpositive", not_estimated: "capRestockLabelNotEstimated",
};

export function RestockPlanner({ report, onFocus }: { report: AuditReport; onFocus: (box: CaptureBox | null) => void }) {
  const { t } = useI18n();
  const [assumptions, setAssumptions] = useState<RestockAssumptions>({ tradingDays: 1, contributionMarginPercent: 30, overheadMinor: 0 });
  const plan = planRestocking(report, assumptions);
  if (!report.findings.some((finding) => finding.kind === "missing")) return null;
  const fields: { key: keyof RestockAssumptions; label: string; min: number; max?: number; step: number }[] = [
    { key: "tradingDays", label: t("capRestockHorizon"), min: 0.1, max: 30, step: 0.1 },
    { key: "contributionMarginPercent", label: t("capRestockMargin"), min: 0, max: 100, step: 1 },
    { key: "overheadMinor", label: t("capRestockOverhead", { currency: report.currency }), min: 0, max: Number.MAX_SAFE_INTEGER, step: 1 },
  ];
  function download() {
    const url = URL.createObjectURL(new Blob(["\ufeff", restockCsv(report, plan.actions, assumptions)], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `restock-${report.job_id}.csv`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <section aria-label={t("capRestockTitle")} className="space-y-3 rounded-xl border p-3">
    <h4 className="section-title">{t("capRestockTitle")}</h4>
    <p className="text-xs text-muted-foreground">{t("capRestockIntro")}</p>
    <div className="space-y-2">{fields.map((field) => <label key={field.key} className="block text-xs">
      {field.label}
      <input aria-label={field.label} type="number" min={field.min} max={field.max} step={field.step}
        value={assumptions[field.key]} onChange={(e) => setAssumptions((current) => ({ ...current, [field.key]: Number(e.target.value) }))}
        className="mt-1 block w-full rounded border bg-background px-2 py-1" />
    </label>)}</div>
    {plan.error && <p role="alert" className="text-xs text-destructive">{plan.error}</p>}
    <ol className="space-y-2">{plan.actions.map((action, index) => <li key={action.sku || index} className="rounded border p-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div><div className="font-medium">{index + 1}. {action.name || action.sku || t("capUnidentifiedItem")}</div>
          <p className="text-muted-foreground">{t("capSkuLevels", { sku: action.sku, levels: action.levels.join(", ") })}</p>
        </div>
        {action.box && <Button size="xs" variant="ghost" onClick={() => onFocus(action.box)}>{t("capLocate")}</Button>}
      </div>
      <div className="mt-1 font-medium">{t("capNetContribution", { value: action.netContribution === null ? t("capRestockLabelNotEstimated") : formatMoney(action.netContribution, report.currency) })}</div>
      {action.netInterval && <p className="text-muted-foreground">{t("capInterval95", { low: formatMoney(action.netInterval[0], report.currency), high: formatMoney(action.netInterval[1], report.currency) })}</p>}
      <p>{t(LABEL[action.evidence])}</p>
      {action.paybackTradingDays !== null && <p className="text-muted-foreground">{t("capPayback", { days: action.paybackTradingDays.toFixed(2) })}</p>}
    </li>)}</ol>
    <p className="text-xs text-muted-foreground">{t("capRestockFooter")}</p>
    <Button size="sm" variant="outline" disabled={plan.error !== null || !plan.actions.length} onClick={download}>
      <Download className="mr-1 size-3" />{t("capExportRestock")}
    </Button>
  </section>;
}
