import { Download } from "lucide-react";

import { pitchCsvUrl, type PitchReport, type PitchComparison } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { formatMoney } from "@/shared/utils/money";

const labels: Record<PitchComparison["metric"], string> = { purchase_intent: "Purchase intent", trust: "Trust", pressure: "Pressure" };
const signed = (x: number) => `${x > 0 ? "+" : ""}${x.toFixed(2)}`;

export function StaffPitchReportView({ projectId, report: r }: { projectId: string; report: PitchReport }) {
  return <div className="space-y-4">
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-lg font-semibold">{r.name}</h2><p className="text-sm text-muted-foreground">Synthetic staff script screening · {r.model}</p></div>
        <Button asChild variant="outline" size="sm"><a href={pitchCsvUrl(projectId, r.pitch_id)} download><Download className="size-4" /> Paired answers CSV</a></Button>
      </div>
      <p className="font-medium">{r.recommendation}</p>
      <p className="text-sm">{r.pairs} complete pairs / {r.attempted} attempted · {r.excluded} excluded · seed {r.request.seed}</p>
      <p className="text-xs text-muted-foreground">These are hypothetical 1–5 ratings, not observed purchase conversion or a sales forecast.</p>
    </section>
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <h3 className="font-semibold">Paired comparison</h3>
      <p className="text-xs text-muted-foreground">B minus A, in scale points. Higher purchase intent and trust are favorable; lower pressure is favorable. Intervals describe the synthetic panel only.</p>
      <div className="overflow-x-auto"><table className="w-full text-sm">
        <thead><tr className="text-left"><th className="py-2">Metric</th><th>A mean</th><th>B mean</th><th>B − A</th><th>95% paired interval</th></tr></thead>
        <tbody>{r.comparisons.map((c) => <tr key={c.metric} className="border-t">
          <th className="py-3 text-left font-medium">{labels[c.metric]}<span className="block text-xs font-normal text-muted-foreground">{c.metric === "purchase_intent" ? "Primary outcome" : "Guardrail"}</span></th>
          <td>{c.a_mean.toFixed(2)}</td><td>{c.b_mean.toFixed(2)}</td><td>{signed(c.diff)}</td>
          <td>{c.ci_low == null || c.ci_high == null ? "Insufficient pairs" : `${signed(c.ci_low)} to ${signed(c.ci_high)}`}</td>
        </tr>)}</tbody>
      </table></div>
    </section>
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <h3 className="font-semibold">Exact test conditions</h3>
      <p className="text-sm">{r.product.name} · {r.product.sku} · {formatMoney(r.product.price, r.product.currency)} {r.product.promo && `· ${r.product.promo}`}</p>
      <p className="whitespace-pre-wrap text-sm">{r.request.context}</p>
      {r.request.product_facts && <p className="whitespace-pre-wrap text-sm"><b>Operator-provided product facts:</b> {r.request.product_facts}</p>}
      <div className="grid gap-3 md:grid-cols-2">{r.request.variants.map((v, i) => <div key={i} className="rounded-xl bg-muted/40 p-3">
        <h4 className="font-semibold">{i === 0 ? "A" : "B"} · {v.name}</h4><p className="mt-2 whitespace-pre-wrap text-sm">{v.script}</p>
      </div>)}</div>
    </section>
    <details className="rounded-2xl border bg-card p-4"><summary className="cursor-pointer text-sm font-semibold">Exploratory segments</summary>
      <p className="my-2 text-xs text-muted-foreground">Descriptive intent differences, B minus A. Small groups are unstable; these are not separate winner tests.</p>
      <table className="w-full text-sm"><thead><tr className="text-left"><th>Segment</th><th>Pairs</th><th>Intent difference</th></tr></thead>
        <tbody>{r.segments.map((s) => <tr key={s.segment}><td className="py-1">{s.segment}</td><td>{s.pairs}</td><td>{signed(s.intent_diff)}</td></tr>)}</tbody>
      </table>
    </details>
    <section className="rounded-2xl border bg-card p-4">
      <h3 className="font-semibold">Customer replies and reasons</h3>
      <p className="mb-3 text-xs text-muted-foreground">First {Math.min(8, r.answers.length)} sampled personas, including failures. Download the CSV for all responses.</p>
      <div className="space-y-2">{r.answers.slice(0, 8).map((a) => <details key={a.respondent} className="rounded-xl border p-3">
        <summary className="cursor-pointer text-sm">{a.respondent} · {a.age_group} · {a.gender}{!a.a || !a.b ? " · excluded pair" : ""}</summary>
        <div className="mt-2 grid gap-3 md:grid-cols-2">{([{ arm: "A", rating: a.a, error: a.error_a }, { arm: "B", rating: a.b, error: a.error_b }]).map((v) => <div key={v.arm} className="space-y-1 text-sm">
          <h4 className="font-semibold">{v.arm}</h4>{v.rating ? <><blockquote>“{v.rating.reply}”</blockquote><p className="text-muted-foreground">{v.rating.reason}</p></> : <p className="text-destructive">{v.error || "No response"}</p>}
        </div>)}</div>
      </details>)}</div>
    </section>
    <details className="rounded-2xl border bg-card p-4"><summary className="cursor-pointer text-sm font-semibold">Method and field pilot guidance</summary>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      <p className="mt-3 text-xs text-muted-foreground">Completed in {r.seconds}s.</p>
    </details>
  </div>;
}
