// A/B comparison of two runs: per-customer paired differences with bootstrap
// confidence intervals, drawn as a forest plot (relative effect of B vs A).

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";

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
import { explainComparison, type ComparisonReport, type MetricComparison, type RunListItem } from "@/shared/api/client";
import type { Layout } from "@/features/layouts/hooks/useLayouts";
import { currencyCode, formatMoney, formatPercent } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { messages, type Locale, type MessageKey } from "@/shared/i18n/messages";
import { translate } from "@/shared/i18n/translate";

import { useCompare, useProjectRuns } from "../hooks";
import { metricLabel, runLabel } from "../labels";

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
      <DialogContent className="max-h-[92dvh] w-[95vw] overflow-y-auto sm:max-w-[920px]">
        <CompareBody {...props} />
      </DialogContent>
    </Dialog>
  );
}

function CompareBody({ projectId, layouts, defaultRunId }: CompareDialogProps) {
  const { locale, t } = useI18n();
  const runs = (useProjectRuns(projectId).data ?? []).filter((r) => r.status === "completed");
  const layoutName = new Map(layouts.map((l) => [l.id, l.name]));
  const otherDefault = runs.find((r) => r.run_id !== defaultRunId)?.run_id ?? null;
  const [runA, setRunA] = useState<string | null>(otherDefault);
  const [runB, setRunB] = useState<string | null>(defaultRunId ?? null);
  const a = runA ?? otherDefault;
  const b = runB ?? defaultRunId ?? null;
  const compare = useCompare(projectId, a, b);
  // Spend comes in the currency's minor unit; show it as money, like the rest of the app.
  const code = currencyCode((runs.find((r) => r.run_id === a) ?? runs.find((r) => r.run_id === b))?.summary?.currency);

  const runName = (r: RunListItem) => `${layoutName.get(r.setup_id) ?? r.setup_id} — ${runLabel(r, locale)}`;
  const nameOf = (id: string | null) => { const r = runs.find((run) => run.run_id === id); return r ? runName(r) : undefined; };
  const option = (r: RunListItem) => <SelectItem key={r.run_id} value={r.run_id}>{runName(r)}</SelectItem>;

  return (
    <div className="min-w-0 space-y-4">
      <DialogHeader>
        <DialogTitle>{t("cmpTitle")}</DialogTitle>
        <DialogDescription>{t("cmpDescription")}</DialogDescription>
      </DialogHeader>

      {runs.length < 2 ? (
        <p className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">{t("cmpNeedTwo")}</p>
      ) : (
        <>
          <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
            {/* Narrow screens cut long run names with an ellipsis; the full name is the trigger's tooltip. */}
            <Select value={a ?? undefined} onValueChange={setRunA}>
              <SelectTrigger className="w-full min-w-0 text-xs" aria-label={t("cmpBaselineRun")} title={nameOf(a)}>
                <SelectValue placeholder={t("cmpBaseline")}>{nameOf(a) && <span className="block min-w-0 truncate">{nameOf(a)}</span>}</SelectValue>
              </SelectTrigger>
              <SelectContent>{runs.map(option)}</SelectContent>
            </Select>
            <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
            <Select value={b ?? undefined} onValueChange={setRunB}>
              <SelectTrigger className="w-full min-w-0 text-xs" aria-label={t("cmpVariantRun")} title={nameOf(b)}>
                <SelectValue placeholder={t("cmpVariant")}>{nameOf(b) && <span className="block min-w-0 truncate">{nameOf(b)}</span>}</SelectValue>
              </SelectTrigger>
              <SelectContent>{runs.map(option)}</SelectContent>
            </Select>
          </div>

          {a === b && <p className="text-xs text-muted-foreground">{t("cmpPickTwo")}</p>}
          {compare.isLoading && <p className="text-sm text-muted-foreground">{t("cmpBootstrapping")}</p>}
          {compare.isError && (
            <p className="text-xs text-destructive">
              {compare.error instanceof Error ? compare.error.message : t("cmpFailed")}
            </p>
          )}
          {compare.data && <CompareTable report={compare.data} code={code} />}
          {compare.data && a && b && a !== b && <Explain key={`${a}:${b}`} projectId={projectId} a={a} b={b} />}
        </>
      )}
    </div>
  );
}

/** The model's reading of the difference: what changed, where it came from, what is within noise. */
function Explain({ projectId, a, b }: { projectId: string; a: string; b: string }) {
  const { t } = useI18n();
  const explain = useMutation({ mutationFn: () => explainComparison(projectId, a, b) });
  const r = explain.data;
  if (!r) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => explain.mutate()} disabled={explain.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-60">
          {explain.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5 text-primary" />}
          {explain.isPending ? t("cmpComparing") : t("cmpExplain")}
        </button>
        <span className="text-xs text-muted-foreground">{t("cmpExplainHint")}</span>
        {explain.error && <p role="alert" className="basis-full text-xs text-destructive">{explain.error.message}</p>}
      </div>
    );
  }
  return (
    <section className="space-y-2 rounded-xl border bg-card p-3 text-sm" aria-label={t("cmpWhyDiffer")}>
      <p className="font-medium">{r.summary}</p>
      {r.where && <p className="text-foreground/85">{r.where}</p>}
      {r.caveats && <p className="text-muted-foreground">{r.caveats}</p>}
      {r.figures.length > 0 && (
        <ul className="space-y-0.5 border-l-2 border-primary/30 pl-2" aria-label={t("figuresUsed")}>
          {r.figures.map((f) => <li key={f} className="text-[0.7rem] tabular-nums text-muted-foreground">{f}</li>)}
        </ul>
      )}
    </section>
  );
}

function CompareTable({ report, code }: { report: ComparisonReport; code: string }) {
  const { locale, t } = useI18n();
  // On narrow screens the table scrolls sideways: the metric column stays put, the right edge fades until the end.
  const [scrolledToEnd, setScrolledToEnd] = useState(false);
  const spend = report.metrics.find((m) => m.metric === "spend");
  return (
    <div className="space-y-3">
      {spend && <Headline m={spend} code={code} locale={locale} />}
      <div className="relative">
      <div className="overflow-x-auto" role="region" aria-label={t("cmpMetricsRegion")} tabIndex={0}
        onScroll={(event) => { const el = event.currentTarget; setScrolledToEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 1); }}>
      <table className="w-full min-w-[640px] text-xs">
        <thead className="text-muted-foreground">
          <tr className="border-b">
            <th className="sticky left-0 z-10 bg-popover py-1.5 pr-2 text-left font-medium">{t("cmpMetric")}</th>
            <th className="text-right font-medium">A</th>
            <th className="text-right font-medium">B</th>
            <th className="w-[230px] text-center font-medium">{t("cmpBvsA", { confidence: Math.round(report.confidence * 100) })}</th>
            <th className="text-right font-medium">{t("cmpChange")}</th>
            <th className="text-right font-medium" title={t("cmpProbHint")}>P(B&gt;A)</th>
            <th className="text-right font-medium" title={t("cmpNHint")}>n@5%</th>
          </tr>
        </thead>
        <tbody>
          {report.metrics.map((m) => (
            <tr key={m.metric} className="border-b last:border-0">
              <td className="sticky left-0 z-10 bg-popover py-1.5 pr-2">{metricLabel(m.metric, locale)}</td>
              <td className="text-right tabular-nums">{fmt(m, m.mean_a, code)}</td>
              <td className="text-right tabular-nums">{fmt(m, m.mean_b, code)}</td>
              <td className="px-2"><ForestBar m={m} code={code} locale={locale} /></td>
              <td className="text-right tabular-nums">{m.mean_a ? signed(m.rel_diff) : "—"}</td>
              <td className="text-right tabular-nums">{formatPercent(m.prob_b_greater, 0)}</td>
              <td className="text-right tabular-nums text-muted-foreground" title={m.mean_a === 0 ? t("cmpZeroBaselineHint") : undefined}>
                {m.mean_a === 0 ? "—" : m.n_for_5pct_effect.toLocaleString(locale)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {!scrolledToEnd && <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-popover to-transparent sm:hidden" />}
      </div>
      <p className="text-xs text-muted-foreground sm:hidden">{t("cmpScrollHint")}</p>
      <p className="text-xs text-muted-foreground">
        {t("cmpFootnote", { paired: report.paired_customers, draws: report.n_bootstrap })}
      </p>
      {report.notes.map((n, i) => (
        <p key={`${i}-${n}`} className="rounded-md border tone-warn px-2.5 py-1.5 text-sm">{noteText(report, i, t)}</p>
      ))}
    </div>
  );
}

/** A note in the user's language when its kind is known here; else the server's English text. */
function noteText(report: ComparisonReport, index: number, t: (key: MessageKey, params?: Record<string, string | number>) => string): string {
  const coded = report.note_codes?.[index];
  const key = coded ? `cmpNote_${coded.code}` : "";
  return coded && Object.prototype.hasOwnProperty.call(messages, key) ? t(key as MessageKey, coded.params) : report.notes[index]!;
}

function Headline({ m, code, locale }: { m: MetricComparison; code: string; locale: Locale }) {
  const { t } = useI18n();
  const decisive = m.ci_low > 0 || m.ci_high < 0;
  const better = m.ci_low > 0;
  return (
    <div
      className={
        "rounded-md border px-3 py-2 text-sm " +
        (decisive ? (better ? "tone-good" : "tone-bad") : "bg-muted/40")
      }
    >
      <span className="font-medium">{t("cmpHeadline", { change: signedChange(m, m.diff, code, locale) })}</span>{" "}
      <span className="text-muted-foreground">
        {t("cmpRangeVerdict", {
          low: signedChange(m, m.ci_low, code, locale),
          high: signedChange(m, m.ci_high, code, locale),
          verdict: decisive ? t(better ? "cmpBetter" : "cmpWorse") : t("cmpNoDiff", { prob: formatPercent(m.prob_b_greater, 0) }),
        })}
      </span>
    </div>
  );
}

// Each row has its own symmetric scale: what matters is whether the interval
// crosses zero, and a shared scale would flatten small effects next to large ones.
function ForestBar({ m, code, locale }: { m: MetricComparison; code: string; locale: Locale }) {
  const W = 110;
  const baseline = m.mean_a || 1;
  const rel = m.diff / baseline;
  const lo = m.ci_low / baseline;
  const hi = m.ci_high / baseline;
  const span = Math.max(0.01, Math.abs(lo), Math.abs(hi)) * 1.15;
  const scale = (x: number) => W / 2 + (Math.max(-span, Math.min(span, x)) / span) * (W / 2 - 6);
  const decisive = lo > 0 || hi < 0;
  const goodDirection = HIGHER_IS_BETTER.has(m.metric);
  const color = !decisive ? "var(--muted-foreground)" : !goodDirection ? "var(--chart-5)" : lo > 0 ? "var(--positive)" : "var(--negative)";
  return (
    <div className="flex items-center gap-2">
      <svg width={W} height={16} viewBox={`0 0 ${W} 16`} aria-hidden>
        <line x1={W / 2} x2={W / 2} y1={1} y2={15} stroke="var(--border)" strokeDasharray="2 2" />
        <line x1={scale(lo)} x2={scale(hi)} y1={8} y2={8} stroke={color} strokeWidth={3} strokeLinecap="round" />
        <circle cx={scale(rel)} cy={8} r={3.5} fill="white" stroke={color} strokeWidth={2} />
      </svg>
      <span className="whitespace-nowrap text-[0.72rem] tabular-nums text-muted-foreground">
        {signedChange(m, m.ci_low, code, locale)} … {signedChange(m, m.ci_high, code, locale)}
      </span>
    </div>
  );
}

function signed(ratio: number): string {
  const s = formatPercent(ratio);
  return ratio > 0 ? `+${s}` : s;
}

function signedChange(m: MetricComparison, delta: number, code: string, locale: Locale): string {
  if (m.mean_a) return signed(delta / m.mean_a);
  const value = m.metric === "bought" ? formatPercent(delta).replace("%", translate(locale, "cmpPoints")) : fmt(m, delta, code);
  return delta > 0 ? `+${value}` : value;
}

function fmt(m: MetricComparison, v: number, code: string): string {
  if (m.metric === "bought") return formatPercent(v);
  if (m.metric === "spend" || m.metric === "impulse_spend") return formatMoney(v, code);
  return v.toFixed(v >= 100 ? 0 : 2);
}
