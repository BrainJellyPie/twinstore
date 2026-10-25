// A/B test result: per-arm KPIs, paired lifts with 95 % CIs (same shoppers in every arm), the tracked products and
// what each variant changed. Everything can be downloaded as CSV for a deck or a client report.

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileText, Info, Loader2, Sparkles, Trophy, TriangleAlert } from "lucide-react";

import * as api from "@/shared/api/client";
import { experimentMarkdownUrl, experimentReportUrl, writeNarrative } from "@/shared/api/marketing";
import { queryKeys } from "@/shared/queries/keys";

import type { ExperimentReport as Report, FocusOutcome, Variant, VariantResult } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";
import { visitorsPerDayText } from "@/shared/utils/estimate";
import { useI18n } from "@/shared/i18n/i18n";
import { richText } from "@/shared/i18n/richText";

import { DemandChart, LiftChart, type LiftRow } from "./charts";
import { FactorialReview } from "./FactorialReview";
import { KeepAsLayout } from "./KeepAsLayout";
import { TestOnline } from "./TestOnline";
import { segmentLabel } from "@/shared/i18n/personaLabels";

const pct = (v: number, digits = 1) => `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(digits)}%`;

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

export function ExperimentReportView({ projectId, report: r, layoutName, variants }: {
  projectId: string; report: Report; layoutName?: string;
  /** What each variant changed, as requested (to carry a variant over to an online store). */
  variants?: Variant[];
}) {
  const { locale, t } = useI18n();
  const pp = (v: number) => t("studioPt", { value: `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)}` });
  const money = (v: number) => formatMoney(v, r.currency);
  const signedMoney = (v: number) => `${v >= 0 ? "+" : "−"}${formatMoney(Math.abs(v), r.currency)}`;
  const arms = [r.control, ...r.variants];
  const winner = r.variants.find((v) => v.name === r.winner);
  const spendRows: LiftRow[] = r.variants.flatMap((v) => {
    const m = metric(v, "spend");
    return m ? [{
      key: v.name, label: v.name, sub: m.mean_a === 0 ? t("mkFromZero") : t("mkVsControl", { change: pct(m.rel_diff) }), diff: m.diff, lo: m.ci_low, hi: m.ci_high,
      detail: t("mkPBetterDetail", { pct: Math.round(m.prob_b_greater * 100), amount: signedMoney(Math.round(m.diff * r.visitors_per_day)) }),
    }] : [];
  });
  const focusSkus = [...new Set(r.variants.flatMap((v) => v.focus.map((f) => f.sku)))];
  const focusName = (sku: string) => r.variants.flatMap((v) => v.focus).find((f) => f.sku === sku)?.name ?? sku;
  const unitRows = (sku: string): LiftRow[] => r.variants.flatMap((v) => {
    const f = v.focus.find((x) => x.sku === sku && x.metric === "units");
    return f ? [{
      key: `${sku}-${v.name}`, label: v.name, sub: f.control ? t("mkUnitsChange", { change: pct(f.rel_diff, 0) }) : t("mkNewSales"),
      diff: f.diff * 100, lo: f.ci_low * 100, hi: f.ci_high * 100, detail: t("mkPMoreUnits", { pct: Math.round(f.prob_better * 100) }),
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
            <p className="text-sm">{richText(t("mkWinnerLead"), { name: <b>{winner.name}</b> })}
              {(() => {
                const m = metric(winner, "spend");
                return m ? richText(t("mkWinnerDetail"), {
                  diff: <b className="num">{signedMoney(m.diff)}</b>, change: m.mean_a === 0 ? t("mkFromZero") : pct(m.rel_diff),
                  daily: <b className="num">{signedMoney(Math.round(m.diff * r.visitors_per_day))}</b>,
                }) : ".";
              })()}
            </p>
          ) : (
            <p className="text-sm">{t("mkNoWinner", { count: r.panel_size })}</p>
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
                <span className="truncate text-sm font-semibold">{i === 0 ? t("mkControl") : a.name}</span>
              </div>
              <dl className="space-y-1.5 text-sm">
                <Kpi label={t("mkRevenuePerVisitor")} value={money(a.revenue_per_visitor)} delta={spend ? spend.mean_a === 0 ? t("mkAmountFromZero", { amount: signedMoney(spend.diff) }) : pct(spend.rel_diff) : null} up={spend ? spend.ci_low > 0 : null} down={spend ? spend.ci_high < 0 : null} />
                <Kpi label={t("mkConversion")} value={`${(a.conversion * 100).toFixed(1)}%`} delta={bought ? pp(bought.diff) : null} up={bought ? bought.ci_low > 0 : null} down={bought ? bought.ci_high < 0 : null} />
                <Kpi label={t("mkUnitsPerVisitor")} value={a.units_per_visitor.toFixed(2)} delta={units ? units.mean_a === 0 ? t("mkAmountFromZero", { amount: `${units.diff >= 0 ? "+" : ""}${units.diff.toFixed(2)}` }) : pct(units.rel_diff) : null} up={units ? units.ci_low > 0 : null} down={units ? units.ci_high < 0 : null} />
              </dl>
              {r.operations && (
                <p className="mt-2 text-xs text-muted-foreground tabular-nums">
                  {t("mkSoldOutLine", { units: (a.lost_units ?? 0).toLocaleString(locale), left: (a.left_line ?? 0).toLocaleString(locale) })}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {r.operations && (
        <p className="text-xs text-muted-foreground">{t("mkSharedStoreNote", { stock: r.operations.stock_per_facing.toLocaleString(locale) })}</p>
      )}

      <section className="rounded-2xl border bg-card p-4">
        <h3 className="text-sm font-semibold">{t("mkRevenueVsControl")}</h3>
        <p className="mb-3 text-xs text-muted-foreground">{t("mkRevenueVsControlHint", { count: r.panel_size })}</p>
        <LiftChart rows={spendRows} format={signedMoney} axisLabel={t("mkPerVisitor")} />
      </section>

      {r.price_response && (
        <section className="rounded-2xl border bg-card p-4">
          <h3 className="text-sm font-semibold">{t("mkPriceResponse", { name: r.price_response.name })}</h3>
          <p className="mb-2 text-xs text-muted-foreground">
            {t("mkPriceResponseHint")}
            {r.price_response.elasticity != null && richText(t("mkElasticity"), { value: <b className="num text-foreground">{r.price_response.elasticity.toFixed(2)}</b> })}
          </p>
          <DemandChart response={r.price_response} currency={r.currency} />
          <table className="mt-2 w-full text-xs">
            <thead className="text-left text-muted-foreground"><tr><th className="py-1">{t("mkColArm")}</th><th className="text-right">{t("mkColPrice")}</th><th className="text-right">{t("mkColUnits100")}</th><th className="text-right">{t("mkColRevenue100")}</th></tr></thead>
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
          <h3 className="text-sm font-semibold">{t("mkTrackedProducts")}</h3>
          <p className="mb-3 text-xs text-muted-foreground">{t("mkTrackedHint")}</p>
          <div className={cn("grid gap-5", focusSkus.length > 1 && "lg:grid-cols-2")}>
            {focusSkus.map((sku) => (
              <div key={sku}>
                <div className="mb-1 text-sm font-medium">{sku === "*" ? t("mkAllTracked") : focusName(sku)}</div>
                <LiftChart rows={unitRows(sku)} format={(v) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}`} axisLabel={t("mkUnitsPer100Axis")} />
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
            <div className="mb-1.5 font-semibold">{t("mkChanged", { name: v.name })}</div>
            <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">{v.applied.map((a) => <li key={a}>{a}</li>)}</ul>
            {v.warnings.map((w) => <p key={w} className="mt-1.5 flex items-start gap-1.5 text-xs text-warn"><TriangleAlert className="mt-0.5 size-3.5 shrink-0" /> {w}</p>)}
            {(() => {
              const asked = variants?.find((x) => x.name === v.name);
              return asked && (
                <>
                  <KeepAsLayout projectId={projectId} setupId={r.setup_id} variant={asked} />
                  <TestOnline projectId={projectId} testName={r.name} variant={asked} currency={r.currency} />
                </>
              );
            })()}
          </div>
        ))}
      </section>

      <footer className="space-y-1 text-xs text-muted-foreground">
        <p>{layoutName ? t("mkFooterControl", { name: layoutName }) : ""}{r.engine === "vlm" ? r.model ? t("mkFooterVisionModel", { model: r.model }) : t("mkFooterVision") : t("mkFooterRule")} · {t("mkFooterPerArm", { count: r.panel_size })} · {visitorsPerDayText(locale, r.visitors_per_day, r.simulated_visitors_per_day)} · {r.seconds}s</p>
        {r.notes.map((n) => <p key={n}>{n}</p>)}
      </footer>
    </div>
  );
}

/** Paired differences by age group and gender; tinted when the 95 % interval clears zero. */
function SegmentTable({ report: r }: { report: Report }) {
  const { t } = useI18n();
  const metrics = (["spend", "focus_units"] as const).filter((m) => r.variants.some((v) => v.segments?.some((s) => s.metric === m)));
  const segments = [...new Set(r.variants.flatMap((v) => (v.segments ?? []).map((s) => s.segment)))];
  if (!segments.length) return null;
  const fmt = (m: string, d: number) => (m === "spend" ? `${d >= 0 ? "+" : "−"}${formatMoney(Math.abs(d), r.currency)}` : `${d >= 0 ? "+" : "−"}${Math.abs(d * 100).toFixed(1)}`);
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h3 className="text-sm font-semibold">{t("mkBySegment")}</h3>
      <p className="mb-2 text-xs text-muted-foreground">{t("mkSegmentHint")}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-1 pr-3">{t("mkColSegment")}</th><th className="pr-3 text-right">n</th>
              {r.variants.flatMap((v) => metrics.map((m) => <th key={`${v.name}-${m}`} className="px-2 text-right whitespace-nowrap">{v.name}<br /><span className="font-normal">{m === "spend" ? t("mkColRevenueVisitor") : t("mkUnitsPer100Axis")}</span></th>))}
            </tr>
          </thead>
          <tbody className="num">
            {segments.map((seg) => (
              <tr key={seg} className="border-t border-foreground/[0.06]">
                <td className="py-1 pr-3 whitespace-nowrap">{segmentLabel(seg, t)}</td>
                <td className="pr-3 text-right text-muted-foreground">{r.variants[0]?.segments?.find((s) => s.segment === seg)?.n ?? ""}</td>
                {r.variants.flatMap((v) => metrics.map((m) => {
                  const x = v.segments?.find((s) => s.segment === seg && s.metric === m);
                  const tone = x ? (x.ci_low > 0 ? "var(--viz-pos-2)" : x.ci_high < 0 ? "var(--viz-neg-2)" : null) : null;
                  return (
                    <td key={`${v.name}-${m}`} className="px-2 text-right" title={x ? t("mkInterval95To", { low: fmt(m, x.ci_low), high: fmt(m, x.ci_high) }) : undefined}
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
  const { t } = useI18n();
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [model, setModel] = useState("");
  const write = useMutation({
    mutationFn: () => writeNarrative(projectId, experimentId, model),
    onSuccess: () => window.open(experimentReportUrl(projectId, experimentId), "_blank", "noopener"),
  });
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-2xl border bg-card px-3 py-2">
      <FileText className="size-4 text-primary" />
      <span className="mr-auto text-sm"><b>{t("mkReportLead")}</b> <span className="text-muted-foreground">{t("mkReportBarHint")}</span></span>
      <Button asChild size="sm"><a href={experimentReportUrl(projectId, experimentId)} target="_blank" rel="noopener">{t("mkOpenReport")}</a></Button>
      <Button asChild variant="outline" size="sm"><a href={experimentMarkdownUrl(projectId, experimentId)} download>Markdown</a></Button>
      <select value={model} onChange={(e) => setModel(e.target.value)} className="h-8 max-w-[11rem] rounded-lg border bg-card/60 px-1.5 text-xs" aria-label={t("mkCommentaryModel")}>
        <option value="">{t("studioAppTextModel")}</option>
        {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
      </select>
      <Button variant="outline" size="sm" disabled={write.isPending} onClick={() => write.mutate()} title={t("mkCommentaryTitle")}>
        {write.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {t("mkAddCommentary")}
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
  const { t } = useI18n();
  const rows: (FocusOutcome & { arm: string })[] = variants.flatMap((v) => v.focus.filter((f) => f.metric !== "units").map((f) => ({ ...f, arm: v.name })));
  if (!rows.length) return null;
  const fmt = (f: FocusOutcome, v: number) => (f.metric === "spend" ? formatMoney(v * 100, currency) : `${(v * 100).toFixed(1)}%`);
  return (
    <details className="mt-4">
      <summary className="cursor-pointer text-xs text-muted-foreground">{t("mkFocusTableSummary")}</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr><th className="py-1 pr-3">{t("mkColVariant")}</th><th className="pr-3">{t("mkColProduct")}</th><th className="pr-3">{t("mkColMeasure")}</th><th className="pr-3 text-right">{t("mkColControl")}</th><th className="pr-3 text-right">{t("mkColVariant")}</th><th className="pr-3 text-right">{t("mkColInterval")}</th><th className="text-right">{t("mkColPBetter")}</th></tr>
          </thead>
          <tbody className="num">
            {rows.map((f) => (
              <tr key={`${f.arm}-${f.sku}-${f.metric}`} className="border-t border-foreground/[0.06]">
                <td className="py-1 pr-3">{f.arm}</td>
                <td className="pr-3">{f.name}</td>
                <td className="pr-3">{f.metric === "spend" ? t("mkMeasureSpend") : t("mkMeasureBuyers")}</td>
                <td className="pr-3 text-right">{fmt(f, f.control)}</td>
                <td className="pr-3 text-right">{fmt(f, f.variant)}</td>
                <td className="pr-3 text-right">{t("mkRangeTo", { low: fmt(f, f.ci_low), high: fmt(f, f.ci_high) })}</td>
                <td className="text-right">{Math.round(f.prob_better * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
