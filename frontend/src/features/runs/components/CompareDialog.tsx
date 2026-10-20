// A/B comparison of two runs: per-customer paired differences with bootstrap
// confidence intervals, drawn as a forest plot (relative effect of B vs A).

import { useState } from "react";
import { ArrowRight } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { ComparisonReport, MetricComparison, RunListItem } from "@/shared/api/client";
import type { Layout } from "@/features/layouts/hooks/useLayouts";
import { formatPercent } from "@/shared/utils/money";

import { useCompare, useProjectRuns } from "../hooks";
import { METRIC_LABELS, runLabel } from "../labels";

// Metrics where "more" is unambiguously good for the store.
const HIGHER_IS_BETTER = new Set(["spend", "units", "bought", "impulse_spend"]);

export interface CompareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  layouts: Layout[];
  defaultRunId?: string;
}

export function CompareDialog(props: CompareDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="w-[95vw] sm:max-w-[920px]">
        <CompareBody {...props} />
      </DialogContent>
    </Dialog>
  );
}

function CompareBody({ projectId, layouts, defaultRunId }: CompareDialogProps) {
  const runs = (useProjectRuns(projectId).data ?? []).filter((r) => r.status === "completed");
  const layoutName = new Map(layouts.map((l) => [l.id, l.name]));
  const otherDefault = runs.find((r) => r.run_id !== defaultRunId)?.run_id ?? null;
  const [runA, setRunA] = useState<string | null>(otherDefault);
  const [runB, setRunB] = useState<string | null>(defaultRunId ?? null);
  const a = runA ?? otherDefault;
  const b = runB ?? defaultRunId ?? null;
  const compare = useCompare(projectId, a, b);

  const option = (r: RunListItem) => (
    <SelectItem key={r.run_id} value={r.run_id}>
      {layoutName.get(r.setup_id) ?? r.setup_id} — {runLabel(r)}
    </SelectItem>
  );

  return (
    <div className="space-y-4">
      <DialogHeader>
        <DialogTitle>Compare runs</DialogTitle>
        <DialogDescription>
          Customers are paired by persona, so the difference isolates the layout (or engine) change.
          Runs with the same seed share every random draw — that gives the tightest intervals.
        </DialogDescription>
      </DialogHeader>

      {runs.length < 2 ? (
        <p className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
          At least two completed runs are needed. Start a preview run on another layout (or with another
          engine) and come back.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
            <Select value={a ?? undefined} onValueChange={setRunA}>
              <SelectTrigger className="w-full min-w-0 text-xs" aria-label="Baseline run (A)">
                <SelectValue placeholder="Baseline (A)" />
              </SelectTrigger>
              <SelectContent>{runs.map(option)}</SelectContent>
            </Select>
            <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
            <Select value={b ?? undefined} onValueChange={setRunB}>
              <SelectTrigger className="w-full min-w-0 text-xs" aria-label="Variant run (B)">
                <SelectValue placeholder="Variant (B)" />
              </SelectTrigger>
              <SelectContent>{runs.map(option)}</SelectContent>
            </Select>
          </div>

          {a === b && <p className="text-xs text-muted-foreground">Pick two different runs.</p>}
          {compare.isLoading && <p className="text-sm text-muted-foreground">Bootstrapping intervals…</p>}
          {compare.isError && (
            <p className="text-xs text-destructive">
              {compare.error instanceof Error ? compare.error.message : "Comparison failed"}
            </p>
          )}
          {compare.data && <CompareTable report={compare.data} />}
        </>
      )}
    </div>
  );
}

function CompareTable({ report }: { report: ComparisonReport }) {
  const spend = report.metrics.find((m) => m.metric === "spend");
  return (
    <div className="space-y-3">
      {spend && <Headline m={spend} />}
      <table className="w-full text-xs">
        <thead className="text-muted-foreground">
          <tr className="border-b">
            <th className="py-1.5 text-left font-medium">Metric</th>
            <th className="text-right font-medium">A</th>
            <th className="text-right font-medium">B</th>
            <th className="w-[230px] text-center font-medium">B vs A ({Math.round(report.confidence * 100)}% CI)</th>
            <th className="text-right font-medium">Change</th>
            <th className="text-right font-medium" title="Share of bootstrap draws where B > A">P(B&gt;A)</th>
            <th className="text-right font-medium" title="Customers needed to detect a 5% change with 80% power">n@5%</th>
          </tr>
        </thead>
        <tbody>
          {report.metrics.map((m) => (
            <tr key={m.metric} className="border-b last:border-0">
              <td className="py-1.5">{METRIC_LABELS[m.metric] ?? m.metric}</td>
              <td className="text-right tabular-nums">{fmt(m, m.mean_a)}</td>
              <td className="text-right tabular-nums">{fmt(m, m.mean_b)}</td>
              <td className="px-2"><ForestBar m={m} /></td>
              <td className="text-right tabular-nums">{m.mean_a ? signed(m.rel_diff) : "—"}</td>
              <td className="text-right tabular-nums">{formatPercent(m.prob_b_greater, 0)}</td>
              <td className="text-right tabular-nums text-muted-foreground">{m.n_for_5pct_effect.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-muted-foreground">
        {report.paired_customers.toLocaleString()} paired customers · {report.n_bootstrap.toLocaleString()} bootstrap draws.
        Spend values are in the currency's minor unit.
      </p>
      {report.notes.map((n) => (
        <p key={n} className="rounded-md border border-amber-300 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-900">{n}</p>
      ))}
    </div>
  );
}

function Headline({ m }: { m: MetricComparison }) {
  const lowRel = m.mean_a ? m.ci_low / m.mean_a : 0;
  const highRel = m.mean_a ? m.ci_high / m.mean_a : 0;
  const decisive = m.ci_low > 0 || m.ci_high < 0;
  const better = m.ci_low > 0;
  return (
    <div
      className={
        "rounded-md border px-3 py-2 text-sm " +
        (decisive ? (better ? "border-emerald-300 bg-emerald-50" : "border-rose-300 bg-rose-50") : "bg-muted/40")
      }
    >
      <span className="font-medium">Spend per visitor: {signed(m.rel_diff)}</span>{" "}
      <span className="text-muted-foreground">
        ({signed(lowRel)} to {signed(highRel)}) —{" "}
        {decisive
          ? better
            ? "B is reliably better."
            : "B is reliably worse."
          : `no reliable difference yet (P(B>A) = ${formatPercent(m.prob_b_greater, 0)}).`}
      </span>
    </div>
  );
}

// Each row has its own symmetric scale: what matters is whether the interval
// crosses zero, and a shared scale would flatten small effects next to large ones.
function ForestBar({ m }: { m: MetricComparison }) {
  const W = 110;
  const rel = m.mean_a ? m.diff / m.mean_a : 0;
  const lo = m.mean_a ? m.ci_low / m.mean_a : 0;
  const hi = m.mean_a ? m.ci_high / m.mean_a : 0;
  const span = Math.max(0.01, Math.abs(lo), Math.abs(hi)) * 1.15;
  const scale = (x: number) => W / 2 + (Math.max(-span, Math.min(span, x)) / span) * (W / 2 - 6);
  const decisive = lo > 0 || hi < 0;
  const goodDirection = HIGHER_IS_BETTER.has(m.metric);
  const color = !decisive ? "#94a3b8" : !goodDirection ? "#3b82f6" : lo > 0 ? "#10b981" : "#f43f5e";
  return (
    <div className="flex items-center gap-2">
      <svg width={W} height={16} viewBox={`0 0 ${W} 16`} aria-hidden>
        <line x1={W / 2} x2={W / 2} y1={1} y2={15} stroke="#cbd5e1" strokeDasharray="2 2" />
        <line x1={scale(lo)} x2={scale(hi)} y1={8} y2={8} stroke={color} strokeWidth={3} strokeLinecap="round" />
        <circle cx={scale(rel)} cy={8} r={3.5} fill="white" stroke={color} strokeWidth={2} />
      </svg>
      <span className="whitespace-nowrap text-[10px] tabular-nums text-muted-foreground">
        {signed(lo)} … {signed(hi)}
      </span>
    </div>
  );
}

function signed(ratio: number): string {
  const s = formatPercent(ratio);
  return ratio > 0 ? `+${s}` : s;
}

function fmt(m: MetricComparison, v: number): string {
  if (m.metric === "bought") return formatPercent(v);
  if (m.metric === "spend" || m.metric === "impulse_spend") return Math.round(v).toLocaleString();
  return v.toFixed(v >= 100 ? 0 : 2);
}
