import type { AuditReport, CaptureBox } from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";

export interface RestockAssumptions {
  tradingDays: number;
  contributionMarginPercent: number;
  overheadMinor: number;
}

export type RestockEvidence = "positive_lower_bound" | "crosses_zero" | "no_interval" | "nonpositive_interval" | "not_estimated";

export interface RestockAction {
  sku: string;
  name: string;
  levels: number[];
  box: CaptureBox | null;
  revenuePerDay: number | null;
  revenueOverHorizon: number | null;
  netContribution: number | null;
  netInterval: [number, number] | null;
  paybackTradingDays: number | null;
  evidence: RestockEvidence;
}

const EVIDENCE_ORDER: Record<RestockEvidence, number> = {
  positive_lower_bound: 0, crosses_zero: 1, no_interval: 2, nonpositive_interval: 3, not_estimated: 4,
};

export function planRestocking(report: AuditReport, assumptions: RestockAssumptions): { actions: RestockAction[]; error: string | null } {
  const { tradingDays, contributionMarginPercent, overheadMinor } = assumptions;
  if (!Number.isFinite(tradingDays) || tradingDays <= 0 || tradingDays > 30
      || !Number.isFinite(contributionMarginPercent) || contributionMarginPercent < 0 || contributionMarginPercent > 100
      || !Number.isSafeInteger(overheadMinor) || overheadMinor < 0) {
    return { actions: [], error: translate(useLocale.getState().locale, "capRestockError") };
  }
  const margin = contributionMarginPercent / 100;
  const actions: RestockAction[] = [];
  const seen = new Map<string, RestockAction>();
  for (const finding of report.findings) {
    if (finding.kind !== "missing") continue;
    // The audit prices removing a SKU from the entire face, even if it is missing
    // on several levels. Such findings represent one action, not additive losses.
    const prior = finding.sku ? seen.get(finding.sku) : undefined;
    if (prior) {
      if (!prior.levels.includes(finding.level)) prior.levels.push(finding.level);
      continue;
    }
    const loss = finding.loss_per_day;
    const estimated = finding.sku !== "" && loss !== null && Number.isFinite(loss)
      && Number.isFinite(loss * tradingDays);
    const revenue = estimated ? loss : null;
    const net = revenue === null ? null : revenue * tradingDays * margin - overheadMinor;
    const ci = finding.loss_ci;
    const interval: [number, number] | null = net !== null && ci !== null
      && ci.every((v) => Number.isFinite(v * tradingDays)) && ci[0] <= ci[1]
      ? [ci[0] * tradingDays * margin - overheadMinor, ci[1] * tradingDays * margin - overheadMinor] : null;
    const evidence: RestockEvidence = net === null ? "not_estimated" : !interval ? "no_interval"
      : interval[0] > 0 ? "positive_lower_bound" : interval[1] <= 0 ? "nonpositive_interval" : "crosses_zero";
    const contributionPerDay = (revenue ?? 0) * margin;
    const payback = contributionPerDay > 0 ? overheadMinor / contributionPerDay : null;
    const action: RestockAction = {
      sku: finding.sku, name: finding.name, levels: [finding.level], box: finding.box,
      revenuePerDay: revenue, revenueOverHorizon: revenue === null ? null : revenue * tradingDays,
      netContribution: net, netInterval: interval,
      paybackTradingDays: payback !== null && Number.isFinite(payback) ? payback : null, evidence,
    };
    actions.push(action);
    if (finding.sku) seen.set(finding.sku, action);
  }
  actions.sort((a, b) => EVIDENCE_ORDER[a.evidence] - EVIDENCE_ORDER[b.evidence]
    || (b.netInterval?.[0] ?? b.netContribution ?? -Infinity) - (a.netInterval?.[0] ?? a.netContribution ?? -Infinity)
    || a.sku.localeCompare(b.sku));
  return { actions, error: null };
}

export function restockCsv(report: AuditReport, actions: RestockAction[], assumptions: RestockAssumptions): string {
  const rows: (string | number | null)[][] = [[
    "audit_id", "capture_id", "setup_id", "rack_id", "face", "currency", "sku", "product", "levels",
    "trading_days", "contribution_margin_percent", "overhead_minor", "isolated_revenue_per_day_minor",
    "revenue_over_horizon_minor", "net_contribution_minor", "net_ci_low_minor", "net_ci_high_minor",
    "payback_trading_days", "evidence",
  ]];
  for (const action of actions) rows.push([
    report.job_id, report.capture_id, report.setup_id, report.rack_id, report.face, report.currency,
    action.sku, action.name, [...action.levels].sort().join(";"), assumptions.tradingDays,
    assumptions.contributionMarginPercent, assumptions.overheadMinor, action.revenuePerDay,
    action.revenueOverHorizon, action.netContribution, action.netInterval?.[0] ?? null,
    action.netInterval?.[1] ?? null, action.paybackTradingDays, action.evidence,
  ]);
  return rows.map((row) => row.map((value) => {
    if (value === null) return "";
    if (typeof value === "number") return String(value);
    // Quoting alone does not prevent spreadsheet formulas in names or IDs.
    const safe = /^[\s]*[=+\-@]/.test(value) ? `'${value}` : value;
    return `"${safe.replace(/"/g, '""')}"`;
  }).join(",")).join("\r\n") + "\r\n";
}
