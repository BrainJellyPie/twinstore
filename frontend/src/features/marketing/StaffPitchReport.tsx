import { Download } from "lucide-react";

import { pitchCsvUrl, type PitchReport, type PitchComparison } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { personaLabel, segmentLabel } from "@/shared/i18n/personaLabels";
import { StudyReading } from "./StudyReading";

const labels: Record<PitchComparison["metric"], MessageKey> = { purchase_intent: "mkMetricIntent", trust: "mkMetricTrust", pressure: "mkMetricPressure" };
const signed = (x: number) => `${x > 0 ? "+" : ""}${x.toFixed(2)}`;

export function StaffPitchReportView({ projectId, report: r }: { projectId: string; report: PitchReport }) {
  const { t } = useI18n();
  return <div className="space-y-4">
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-lg font-semibold">{r.name}</h2><p className="text-sm text-muted-foreground">{t("mkPitchScreening", { model: r.model })}</p></div>
        <Button asChild variant="outline" size="sm"><a href={pitchCsvUrl(projectId, r.pitch_id)} download><Download className="size-4" /> {t("mkPairedCsv")}</a></Button>
      </div>
      <p className="font-medium">{r.recommendation}</p>
      <p className="text-sm">{t("mkPitchPairs", { pairs: r.pairs, attempted: r.attempted, excluded: r.excluded, seed: String(r.request.seed) })}</p>
      <p className="text-xs text-muted-foreground">{t("mkPitchHypothetical")}</p>
    </section>
    <StudyReading projectId={projectId} study="staff-pitches" jobId={r.pitch_id}
      answers={r.answers.reduce((n, a) => n + (a.a ? 1 : 0) + (a.b ? 1 : 0), 0)} />
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <h3 className="font-semibold">{t("mkPairedComparison")}</h3>
      <p className="text-xs text-muted-foreground">{t("mkPairedHint")}</p>
      <div className="overflow-x-auto"><table className="w-full text-sm">
        <thead><tr className="text-left"><th className="py-2">{t("mkColMetric")}</th><th>{t("mkColAMean")}</th><th>{t("mkColBMean")}</th><th>B − A</th><th>{t("mkColPaired95")}</th></tr></thead>
        <tbody>{r.comparisons.map((c) => <tr key={c.metric} className="border-t">
          <th className="py-3 text-left font-medium">{t(labels[c.metric])}<span className="block text-xs font-normal text-muted-foreground">{c.metric === "purchase_intent" ? t("mkPrimaryOutcome") : t("mkGuardrail")}</span></th>
          <td>{c.a_mean.toFixed(2)}</td><td>{c.b_mean.toFixed(2)}</td><td>{signed(c.diff)}</td>
          <td>{c.ci_low == null || c.ci_high == null ? t("mkInsufficientPairs") : t("mkRangeTo", { low: signed(c.ci_low), high: signed(c.ci_high) })}</td>
        </tr>)}</tbody>
      </table></div>
    </section>
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <h3 className="font-semibold">{t("mkExactConditions")}</h3>
      <p className="text-sm">{r.product.name} · {r.product.sku} · {formatMoney(r.product.price, r.product.currency)} {r.product.promo && `· ${r.product.promo}`}</p>
      <p className="whitespace-pre-wrap text-sm">{r.request.context}</p>
      {r.request.product_facts && <p className="whitespace-pre-wrap text-sm"><b>{t("mkOperatorFacts")}</b> {r.request.product_facts}</p>}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">{r.request.variants.map((v, i) => <div key={i} className="rounded-xl bg-muted/40 p-3">
        <h4 className="font-semibold">{i === 0 ? "A" : "B"} · {v.name}</h4><p className="mt-2 whitespace-pre-wrap text-sm">{v.script}</p>
      </div>)}</div>
    </section>
    <details className="rounded-2xl border bg-card p-4"><summary className="cursor-pointer text-sm font-semibold">{t("mkExploratorySegments")}</summary>
      <p className="my-2 text-xs text-muted-foreground">{t("mkExploratoryHint")}</p>
      <table className="w-full text-sm"><thead><tr className="text-left"><th>{t("mkColSegment")}</th><th>{t("mkColPairs")}</th><th>{t("mkColIntentDiff")}</th></tr></thead>
        <tbody>{r.segments.map((s) => <tr key={s.segment}><td className="py-1">{segmentLabel(s.segment, t)}</td><td>{s.pairs}</td><td>{signed(s.intent_diff)}</td></tr>)}</tbody>
      </table>
    </details>
    <section className="rounded-2xl border bg-card p-4">
      <h3 className="font-semibold">{t("mkRepliesTitle")}</h3>
      <p className="mb-3 text-xs text-muted-foreground">{t("mkRepliesHint", { count: Math.min(8, r.answers.length) })}</p>
      <div className="space-y-2">{r.answers.slice(0, 8).map((a) => <details key={a.respondent} className="rounded-xl border p-3">
        <summary className="cursor-pointer text-sm">{a.respondent} · {personaLabel(a.age_group, t)} · {personaLabel(a.gender, t)}{!a.a || !a.b ? t("mkExcludedPair") : ""}</summary>
        <div className="mt-2 grid gap-3 md:grid-cols-2">{([{ arm: "A", rating: a.a, error: a.error_a }, { arm: "B", rating: a.b, error: a.error_b }]).map((v) => <div key={v.arm} className="space-y-1 text-sm">
          <h4 className="font-semibold">{v.arm}</h4>{v.rating ? <><blockquote>“{v.rating.reply}”</blockquote><p className="text-muted-foreground">{v.rating.reason}</p></> : <p className="text-destructive">{v.error || t("mkNoResponse")}</p>}
        </div>)}</div>
      </details>)}</div>
    </section>
    <details className="rounded-2xl border bg-card p-4"><summary className="cursor-pointer text-sm font-semibold">{t("mkMethodPilotGuidance")}</summary>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      <p className="mt-3 text-xs text-muted-foreground">{t("mkCompletedIn", { seconds: String(r.seconds) })}</p>
    </details>
  </div>;
}
