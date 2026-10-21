import { useState } from "react";
import { Download } from "lucide-react";

import type { AuditReport, CaptureBox } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { formatMoney } from "@/shared/utils/money";
import { planRestocking, restockCsv, type RestockAssumptions, type RestockEvidence } from "./restockPlanner";

const LABEL: Record<RestockEvidence, string> = {
  positive_lower_bound: "Positive lower bound", crosses_zero: "Interval crosses zero",
  no_interval: "No interval available", nonpositive_interval: "Nonpositive interval", not_estimated: "Not estimated",
};

export function RestockPlanner({ report, onFocus }: { report: AuditReport; onFocus: (box: CaptureBox | null) => void }) {
  const [assumptions, setAssumptions] = useState<RestockAssumptions>({ tradingDays: 1, contributionMarginPercent: 30, overheadMinor: 0 });
  const plan = planRestocking(report, assumptions);
  if (!report.findings.some((finding) => finding.kind === "missing")) return null;
  const fields: { key: keyof RestockAssumptions; label: string; min: number; max?: number; step: number }[] = [
    { key: "tradingDays", label: "Recovery horizon (trading days)", min: 0.1, max: 30, step: 0.1 },
    { key: "contributionMarginPercent", label: "Blended contribution margin (%)", min: 0, max: 100, step: 1 },
    { key: "overheadMinor", label: `Overhead per SKU (${report.currency} minor units)`, min: 0, max: Number.MAX_SAFE_INTEGER, step: 1 },
  ];
  function download() {
    const url = URL.createObjectURL(new Blob(["\ufeff", restockCsv(report, plan.actions, assumptions)], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `restock-${report.job_id}.csv`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <section aria-label="Restocking priorities" className="space-y-3 rounded-xl border p-3">
    <h4 className="section-title">Restocking priorities</h4>
    <p className="text-xs text-muted-foreground">
      Compare isolated missing-SKU scenarios. Change these planning assumptions for your store:
      recovery uses the audit's daily traffic, with the same demand each trading day.
      Overhead is an extra handling or delivery cost; inventory cost is already reflected in the margin.
    </p>
    <div className="space-y-2">{fields.map((field) => <label key={field.key} className="block text-xs">
      {field.label}
      <input aria-label={field.label} type="number" min={field.min} max={field.max} step={field.step}
        value={assumptions[field.key]} onChange={(e) => setAssumptions((current) => ({ ...current, [field.key]: Number(e.target.value) }))}
        className="mt-1 block w-full rounded border bg-background px-2 py-1" />
    </label>)}</div>
    {plan.error && <p role="alert" className="text-xs text-destructive">{plan.error}</p>}
    <ol className="space-y-2">{plan.actions.map((action, index) => <li key={action.sku || index} className="rounded border p-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div><div className="font-medium">{index + 1}. {action.name || action.sku || "Unidentified item"}</div>
          <p className="text-muted-foreground">{action.sku} · levels {action.levels.join(", ")}</p>
        </div>
        {action.box && <Button size="xs" variant="ghost" onClick={() => onFocus(action.box)}>Locate</Button>}
      </div>
      <div className="mt-1 font-medium">Net contribution: {action.netContribution === null ? "Not estimated" : formatMoney(action.netContribution, report.currency)}</div>
      {action.netInterval && <p className="text-muted-foreground">95% interval: {formatMoney(action.netInterval[0], report.currency)} … {formatMoney(action.netInterval[1], report.currency)}</p>}
      <p>{LABEL[action.evidence]}</p>
      {action.paybackTradingDays !== null && <p className="text-muted-foreground">Overhead payback at the point estimate: {action.paybackTradingDays.toFixed(2)} trading days</p>}
    </li>)}</ol>
    <p className="text-xs text-muted-foreground">
      Positive lower bounds rank first. These are simulation scenarios, with fixed margin and cost assumptions.
      They exclude operational uncertainty. Do not add the estimates: substitution between products makes joint recovery different.
    </p>
    <Button size="sm" variant="outline" disabled={plan.error !== null || !plan.actions.length} onClick={download}>
      <Download className="mr-1 size-3" />Export restocking CSV
    </Button>
  </section>;
}
