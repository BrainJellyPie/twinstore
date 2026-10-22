// A/B test result: per-arm KPIs, paired lifts with 95 % CIs (same shoppers in every arm), the tracked products and
// what each variant changed. Everything can be downloaded as CSV for a deck or a client report.

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileText, Info, Loader2, Sparkles, Trophy, TriangleAlert } from "lucide-react";

import * as api from "@/shared/api/client";
import { experimentMarkdownUrl, experimentReportUrl, writeNarrative } from "@/shared/api/marketing";
import { queryKeys } from "@/shared/queries/keys";

import type { ExperimentReport as Report, FocusOutcome, VariantResult } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";
import { visitorsPerDayText } from "@/shared/utils/estimate";

import { DemandChart, LiftChart, type LiftRow } from "./charts";
import { FactorialReview } from "./FactorialReview";

const pct = (v: number, digits = 1) => `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(digits)} %`;
const pp = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)} pt`;

function metric(v: VariantResult, name: string) {
  return v.vs_control.find((m) => m.metric === name);
}

function download(name: string, rows: (string | number)[][]) {
  const csv = rows.map((r) => r.map((c) => {
    // Keep report labels as text when opened in a spreadsheet; numeric losses stay numeric.
    const text = typeof c === "string" && /^[=+\-@]/.test(c.trimStart()) ? `'${c}` : String(c);
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `${name}.csv` });
  a.click();
  URL.revokeObjectURL(url);
}

export function ExperimentReportView({ projectId, report: r, layoutName }: { projectId: string; report: Report; layoutName?: string }) {
  const money = (v: number) => formatMoney(v, r.currency);
  const signedMoney = (v: number) => `${v >= 0 ? "+" : "−"}${formatMoney(Math.abs(v), r.currency)}`;
  const arms = [r.control, ...r.variants];
  const winner = r.variants.find((v) => v.name === r.winner);
  const spendRows: LiftRow[] = r.variants.flatMap((v) => {
    const m = metric(v, "spend");
    return m ? [{
      key: v.name, label: v.name, sub: m.mean_a === 0 ? "from zero" : `${pct(m.rel_diff)} vs control`, diff: m.diff, lo: m.ci_low, hi: m.ci_high,
      detail: `P(better than control) ${Math.round(m.prob_b_greater * 100)} % · ${signedMoney(Math.round(m.diff * r.visitors_per_day))} per day`,
    }] : [];
  });
  const focusSkus = [...new Set(r.variants.flatMap((v) => v.focus.map((f) => f.sku)))];
  const focusName = (sku: string) => r.variants.flatMap((v) => v.focus).find((f) => f.sku === sku)?.name ?? sku;
  const unitRows = (sku: string): LiftRow[] => r.variants.flatMap((v) => {
    const f = v.focus.find((x) => x.sku === sku && x.metric === "units");
    return f ? [{
      key: `${sku}-${v.name}`, label: v.name, sub: f.control ? `${pct(f.rel_diff, 0)} units` : "new sales",
      diff: f.diff * 100, lo: f.ci_low * 100, hi: f.ci_high * 100, detail: `P(more units) ${Math.round(f.prob_better * 100)} %`,
    }] : [];
  });

  const exportCsv = () => {
    const rows: (string | number)[][] = [["arm", "revenue_per_visitor", "conversion", "units_per_visitor", "spend_diff", "spend_ci_low", "spend_ci_high", "p_better", "changes"]];
    for (const a of arms) {
      const m = metric(a, "spend");
      rows.push([a.name, a.revenue_per_visitor, a.conversion, a.units_per_visitor, m?.diff ?? "", m?.ci_low ?? "", m?.ci_high ?? "", m?.prob_b_greater ?? "", a.applied.join("; ")]);
    }
    rows.push([]);
    rows.push(["variant", "sku", "product", "metric", "control", "variant_value", "diff", "ci_low", "ci_high", "p_better"]);
    for (const v of r.variants) for (const f of v.focus) rows.push([v.name, f.sku, f.name, f.metric, f.control, f.variant, f.diff, f.ci_low, f.ci_high, f.prob_better]);
    download(r.name.replace(/[^\w-]+/g, "_") || r.experiment_id, rows);
  };

  return (
    <div className="space-y-4">
      <div className={cn("flex flex-wrap items-center gap-3 rounded-2xl border px-4 py-3", winner ? "tone-good" : "bg-foreground/[0.03]")}>
        {winner ? <Trophy className="size-5 shrink-0" /> : <Info className="size-5 shrink-0 text-muted-foreground" />}
        <div className="min-w-0 flex-1">
          {winner ? (
            <p className="text-sm"><b>{winner.name}</b> earns more per visitor than the control, beyond the noise of this panel
              {(() => { const m = metric(winner, "spend"); return m ? <> — <b className="num">{signedMoney(m.diff)}</b> per visitor ({m.mean_a === 0 ? "from zero" : pct(m.rel_diff)}), about <b className="num">{signedMoney(Math.round(m.diff * r.visitors_per_day))}</b> a day.</> : "."; })()}
            </p>
          ) : (
            <p className="text-sm">No variant beats the control on revenue per visitor beyond the noise of {r.panel_size} shoppers. Check the tracked products below — a change can move its own product without moving the basket.</p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={exportCsv}><Download className="size-4" /> CSV</Button>
      </div>
      <ReportBar projectId={projectId} experimentId={r.experiment_id} />
      <FactorialReview key={`${projectId}:${r.experiment_id}`} projectId={projectId} experimentId={r.experiment_id} />

      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${arms.length <= 5 ? arms.length : Math.ceil(arms.length / 2)}, minmax(0, 1fr))` }}>
        {arms.map((a, i) => {
          const spend = metric(a, "spend");
          const bought = metric(a, "bought");
          const units = metric(a, "units");
          return (
            <div key={a.name} className={cn("rounded-2xl border bg-card p-3", a.name === r.winner && "border-positive/60")}>
              <div className="mb-2 flex items-center gap-2">
                <span className={cn("grid size-5 place-items-center rounded-md text-[0.68rem] font-bold", i === 0 ? "bg-foreground/[0.08]" : "bg-primary text-primary-foreground")}>{String.fromCharCode(65 + i)}</span>
                <span className="truncate text-sm font-semibold">{a.name}</span>
              </div>
              <dl className="space-y-1.5 text-sm">
                <Kpi label="Revenue / visitor" value={money(a.revenue_per_visitor)} delta={spend ? spend.mean_a === 0 ? `${signedMoney(spend.diff)} from zero` : pct(spend.rel_diff) : null} up={spend ? spend.ci_low > 0 : null} down={spend ? spend.ci_high < 0 : null} />
                <Kpi label="Conversion" value={`${(a.conversion * 100).toFixed(1)} %`} delta={bought ? pp(bought.diff) : null} up={bought ? bought.ci_low > 0 : null} down={bought ? bought.ci_high < 0 : null} />
                <Kpi label="Units / visitor" value={a.units_per_visitor.toFixed(2)} delta={units ? units.mean_a === 0 ? `${units.diff >= 0 ? "+" : ""}${units.diff.toFixed(2)} from zero` : pct(units.rel_diff) : null} up={units ? units.ci_low > 0 : null} down={units ? units.ci_high < 0 : null} />
              </dl>
            </div>
          );
        })}
      </div>

      <section className="rounded-2xl border bg-card p-4">
        <h3 className="text-sm font-semibold">Revenue per visitor vs control</h3>
        <p className="mb-3 text-xs text-muted-foreground">Same {r.panel_size} shoppers in every arm; dot = paired difference, bar = 95 % bootstrap interval. A bar that crosses 0 is within noise.</p>
        <LiftChart rows={spendRows} format={signedMoney} axisLabel="per visitor" />
      </section>

      {r.price_response && (
        <section className="rounded-2xl border bg-card p-4">
          <h3 className="text-sm font-semibold">Price response · {r.price_response.name}</h3>
          <p className="mb-2 text-xs text-muted-foreground">
            Units per 100 visitors at each tested price (bars: 95 % intervals; orange = most product revenue)
            {r.price_response.elasticity != null && <> · elasticity across the arms ≈ <b className="num text-foreground">{r.price_response.elasticity.toFixed(2)}</b></>}
          </p>
          <DemandChart response={r.price_response} currency={r.currency} />
          <table className="mt-2 w-full text-xs">
            <thead className="text-left text-muted-foreground"><tr><th className="py-1">Arm</th><th className="text-right">Price</th><th className="text-right">Units / 100 visitors</th><th className="text-right">Product revenue / 100 visitors</th></tr></thead>
            <tbody className="num">
              {r.price_response.points.map((p) => (
                <tr key={p.arm} className="border-t border-foreground/[0.06]">
                  <td className="py-1">{p.arm}</td><td className="text-right">{money(p.price)}</td>
                  <td className="text-right">{(p.units * 100).toFixed(1)} <span className="text-muted-foreground">[{(p.units_low * 100).toFixed(1)}, {(p.units_high * 100).toFixed(1)}]</span></td>
                  <td className="text-right">{money(p.revenue * 100)}{p.price === r.price_response!.best_price ? " ★" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {focusSkus.length > 0 && (
        <section className="rounded-2xl border bg-card p-4">
          <h3 className="text-sm font-semibold">Tracked products</h3>
          <p className="mb-3 text-xs text-muted-foreground">Units per 100 visitors, paired difference to control with 95 % interval.</p>
          <div className={cn("grid gap-5", focusSkus.length > 1 && "lg:grid-cols-2")}>
            {focusSkus.map((sku) => (
              <div key={sku}>
                <div className="mb-1 text-sm font-medium">{sku === "*" ? "All tracked products" : focusName(sku)}</div>
                <LiftChart rows={unitRows(sku)} format={(v) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}`} axisLabel="units / 100" />
              </div>
            ))}
          </div>
          <FocusTable variants={r.variants} currency={r.currency} />
        </section>
      )}

      <SegmentTable report={r} />

      <section className="grid gap-3 lg:grid-cols-2">
        {r.variants.map((v) => (
          <div key={v.name} className="rounded-2xl border bg-card p-4 text-sm">
            <div className="mb-1.5 font-semibold">{v.name} changed</div>
            <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">{v.applied.map((a) => <li key={a}>{a}</li>)}</ul>
            {v.warnings.map((w) => <p key={w} className="mt-1.5 flex items-start gap-1.5 text-xs text-warn"><TriangleAlert className="mt-0.5 size-3.5 shrink-0" /> {w}</p>)}
          </div>
        ))}
      </section>

      <footer className="space-y-1 text-xs text-muted-foreground">
        <p>{layoutName ? `Control: ${layoutName} · ` : ""}{r.engine === "vlm" ? `Vision shoppers${r.model ? ` (${r.model})` : ""}` : "Rule shoppers"} · {r.panel_size} shoppers per arm · {visitorsPerDayText(r.visitors_per_day, r.simulated_visitors_per_day)} · {r.seconds}s</p>
        {r.notes.map((n) => <p key={n}>{n}</p>)}
      </footer>
    </div>
  );
}

/** Paired differences by age group and gender; tinted when the 95 % interval clears zero. */
function SegmentTable({ report: r }: { report: Report }) {
  const metrics = (["spend", "focus_units"] as const).filter((m) => r.variants.some((v) => v.segments?.some((s) => s.metric === m)));
  const segments = [...new Set(r.variants.flatMap((v) => (v.segments ?? []).map((s) => s.segment)))];
  if (!segments.length) return null;
  const fmt = (m: string, d: number) => (m === "spend" ? `${d >= 0 ? "+" : "−"}${formatMoney(Math.abs(d), r.currency)}` : `${d >= 0 ? "+" : "−"}${Math.abs(d * 100).toFixed(1)}`);
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h3 className="text-sm font-semibold">By segment</h3>
      <p className="mb-2 text-xs text-muted-foreground">Paired difference to control within each age group and gender (20+ shoppers); tinted cells clear zero at 95 %.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-1 pr-3">Segment</th><th className="pr-3 text-right">n</th>
              {r.variants.flatMap((v) => metrics.map((m) => <th key={`${v.name}-${m}`} className="px-2 text-right whitespace-nowrap">{v.name}<br /><span className="font-normal">{m === "spend" ? "revenue / visitor" : "units / 100"}</span></th>))}
            </tr>
          </thead>
          <tbody className="num">
            {segments.map((seg) => (
              <tr key={seg} className="border-t border-foreground/[0.06]">
                <td className="py-1 pr-3 whitespace-nowrap">{seg.replace(/^age /, "Age ").replace(/^gender /, "")}</td>
                <td className="pr-3 text-right text-muted-foreground">{r.variants[0]?.segments?.find((s) => s.segment === seg)?.n ?? ""}</td>
                {r.variants.flatMap((v) => metrics.map((m) => {
                  const x = v.segments?.find((s) => s.segment === seg && s.metric === m);
                  const tone = x ? (x.ci_low > 0 ? "var(--viz-pos-2)" : x.ci_high < 0 ? "var(--viz-neg-2)" : null) : null;
                  return (
                    <td key={`${v.name}-${m}`} className="px-2 text-right" title={x ? `95 % interval ${fmt(m, x.ci_low)} to ${fmt(m, x.ci_high)}` : undefined}
                      style={tone ? { background: `color-mix(in oklab, ${tone} 18%, transparent)` } : undefined}>
                      {x ? fmt(m, x.diff) : "–"}
                    </td>
                  );
                }))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** The written report: open (print to PDF), Markdown, and an optional model-written commentary. */
function ReportBar({ projectId, experimentId }: { projectId: string; experimentId: string }) {
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [model, setModel] = useState("");
  const write = useMutation({
    mutationFn: () => writeNarrative(projectId, experimentId, model),
    onSuccess: () => window.open(experimentReportUrl(projectId, experimentId), "_blank", "noopener"),
  });
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-2xl border bg-card px-3 py-2">
      <FileText className="size-4 text-primary" />
      <span className="mr-auto text-sm"><b>Report</b> <span className="text-muted-foreground">· summary, recommendation, charts, method — ready to share or print to PDF</span></span>
      <Button asChild size="sm"><a href={experimentReportUrl(projectId, experimentId)} target="_blank" rel="noopener">Open report</a></Button>
      <Button asChild variant="outline" size="sm"><a href={experimentMarkdownUrl(projectId, experimentId)} download>Markdown</a></Button>
      <select value={model} onChange={(e) => setModel(e.target.value)} className="h-8 max-w-[11rem] rounded-lg border bg-card/60 px-1.5 text-xs" aria-label="Model for the commentary">
        <option value="">App's text model</option>
        {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
      </select>
      <Button variant="outline" size="sm" disabled={write.isPending} onClick={() => write.mutate()} title="A language model writes a commentary from the report's numbers; it is added to the report, labelled">
        {write.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Add commentary
      </Button>
      {write.error && <p className="basis-full text-xs text-destructive">{write.error.message}</p>}
    </div>
  );
}

function Kpi({ label, value, delta, up, down }: { label: string; value: string; delta: string | null; up: boolean | null; down: boolean | null }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="flex items-baseline gap-1.5">
        <span className="num font-semibold">{value}</span>
        {delta && <span className={cn("num text-[0.7rem]", up ? "text-positive" : down ? "text-negative" : "text-muted-foreground")}>{up ? "▲ " : down ? "▼ " : ""}{delta}</span>}
      </dd>
    </div>
  );
}

function FocusTable({ variants, currency }: { variants: VariantResult[]; currency: string }) {
  const rows: (FocusOutcome & { arm: string })[] = variants.flatMap((v) => v.focus.filter((f) => f.metric !== "units").map((f) => ({ ...f, arm: v.name })));
  if (!rows.length) return null;
  const fmt = (f: FocusOutcome, v: number) => (f.metric === "spend" ? formatMoney(v * 100, currency) : `${(v * 100).toFixed(1)} %`);
  return (
    <details className="mt-4">
      <summary className="cursor-pointer text-xs text-muted-foreground">Spend and buyer share per product (table)</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr><th className="py-1 pr-3">Variant</th><th className="pr-3">Product</th><th className="pr-3">Measure</th><th className="pr-3 text-right">Control</th><th className="pr-3 text-right">Variant</th><th className="pr-3 text-right">95 % interval of the difference</th><th className="text-right">P(better)</th></tr>
          </thead>
          <tbody className="num">
            {rows.map((f) => (
              <tr key={`${f.arm}-${f.sku}-${f.metric}`} className="border-t border-foreground/[0.06]">
                <td className="py-1 pr-3">{f.arm}</td>
                <td className="pr-3">{f.name}</td>
                <td className="pr-3">{f.metric === "spend" ? "spend / 100 visitors" : "visitors who buy"}</td>
                <td className="pr-3 text-right">{fmt(f, f.control)}</td>
                <td className="pr-3 text-right">{fmt(f, f.variant)}</td>
                <td className="pr-3 text-right">{fmt(f, f.ci_low)} to {fmt(f, f.ci_high)}</td>
                <td className="text-right">{Math.round(f.prob_better * 100)} %</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
