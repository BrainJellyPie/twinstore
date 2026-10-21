// A/B test result: per-arm KPIs, paired lifts with 95 % CIs (same shoppers in every arm), the tracked products and
// what each variant changed. Everything can be downloaded as CSV for a deck or a client report.

import { Download, Info, Trophy, TriangleAlert } from "lucide-react";

import type { ExperimentReport as Report, FocusOutcome, VariantResult } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";

import { LiftChart, type LiftRow } from "./charts";

const pct = (v: number, digits = 1) => `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(digits)} %`;
const pp = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)} pt`;

function metric(v: VariantResult, name: string) {
  return v.vs_control.find((m) => m.metric === name);
}

function download(name: string, rows: (string | number)[][]) {
  const csv = rows.map((r) => r.map((c) => (typeof c === "string" && /[",\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : String(c))).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `${name}.csv` });
  a.click();
  URL.revokeObjectURL(url);
}

export function ExperimentReportView({ report: r, layoutName }: { report: Report; layoutName?: string }) {
  const money = (v: number) => formatMoney(v, r.currency);
  const signedMoney = (v: number) => `${v >= 0 ? "+" : "−"}${formatMoney(Math.abs(v), r.currency)}`;
  const arms = [r.control, ...r.variants];
  const winner = r.variants.find((v) => v.name === r.winner);
  const spendRows: LiftRow[] = r.variants.flatMap((v) => {
    const m = metric(v, "spend");
    return m ? [{
      key: v.name, label: v.name, sub: `${pct(m.rel_diff)} vs control`, diff: m.diff, lo: m.ci_low, hi: m.ci_high,
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
              {(() => { const m = metric(winner, "spend"); return m ? <> — <b className="num">{signedMoney(m.diff)}</b> per visitor ({pct(m.rel_diff)}), about <b className="num">{signedMoney(Math.round(m.diff * r.visitors_per_day))}</b> a day.</> : "."; })()}
            </p>
          ) : (
            <p className="text-sm">No variant beats the control on revenue per visitor beyond the noise of {r.panel_size} shoppers. Check the tracked products below — a change can move its own product without moving the basket.</p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={exportCsv}><Download className="size-4" /> CSV</Button>
      </div>

      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(arms.length, 4)}, minmax(0, 1fr))` }}>
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
                <Kpi label="Revenue / visitor" value={money(a.revenue_per_visitor)} delta={spend ? pct(spend.rel_diff) : null} up={spend ? spend.ci_low > 0 : null} down={spend ? spend.ci_high < 0 : null} />
                <Kpi label="Conversion" value={`${(a.conversion * 100).toFixed(1)} %`} delta={bought ? pp(bought.diff) : null} up={bought ? bought.ci_low > 0 : null} down={bought ? bought.ci_high < 0 : null} />
                <Kpi label="Units / visitor" value={a.units_per_visitor.toFixed(2)} delta={units ? pct(units.rel_diff) : null} up={units ? units.ci_low > 0 : null} down={units ? units.ci_high < 0 : null} />
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
        <p>{layoutName ? `Control: ${layoutName} · ` : ""}{r.engine === "vlm" ? `Vision shoppers${r.model ? ` (${r.model})` : ""}` : "Rule shoppers"} · {r.panel_size} shoppers per arm · ≈{Math.round(r.visitors_per_day)} visitors a day in this store · {r.seconds}s</p>
        {r.notes.map((n) => <p key={n}>{n}</p>)}
      </footer>
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
