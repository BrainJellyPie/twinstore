// Conjoint result: what drives the choice (attribute importance), part-worths with willingness to pay, a market
// simulator for line-ups of the tested levels, importance by segment and verbatims; HTML report and CSV export.

import { useState } from "react";
import { Download, FileText, Plus, Quote, X } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";

import { conjointCsvUrl, conjointReportUrl, type ConjointReport as Report, type PartWorth } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/shared/components/ui/chart";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { richText } from "@/shared/i18n/richText";

import { ShareBars } from "./charts";
import { defaultLineup, shareCurve, shares, type SimProduct } from "./conjoint";
import { segmentLabel } from "@/shared/i18n/personaLabels";
import { StudyReading } from "./StudyReading";

const LETTERS = "ABCD";
type Translate = ReturnType<typeof useI18n>["t"];
/** "Price" is the report's key for the price attribute; only its label is translated. */
const attributeLabel = (name: string, t: Translate) => (name === "Price" ? t("mkPrice") : name);

export function ConjointReportView({ projectId, report: r }: { projectId: string; report: Report }) {
  const { t, locale } = useI18n();
  const money = (v: number) => formatMoney(v, r.currency);
  const ranked = [...r.importances].sort((a, b) => b.importance - a.importance);
  const levels = (attribute: string) => r.part_worths.filter((p) => p.attribute === attribute);
  const span = Math.max(1e-6, ...r.part_worths.flatMap((p) => [Math.abs(p.ci_low), Math.abs(p.ci_high)]));
  const noSlope = r.prices.length > 0 && (r.price_slope == null || r.price_slope >= 0);
  const leads = r.attributes.map((a) => {
    const best = levels(a.name).reduce((x, y) => (y.utility > x.utility ? y : x));
    return { attribute: a.name, best, base: a.levels[0]! };
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <section className="rounded-2xl border bg-card p-4">
          <h3 className="mb-3 text-sm font-semibold">{t("mkDrivers")} <span className="font-normal text-muted-foreground">{t("mkDriversHint")}</span></h3>
          <ShareBars rows={ranked.map((i) => ({ label: attributeLabel(i.attribute, t), share: i.importance, lo: i.ci_low, hi: i.ci_high }))} />
        </section>
        <div className="flex flex-col gap-2 rounded-2xl border bg-card p-4">
          <div className="grid grid-cols-4 gap-2">
            <Stat label={t("mkRespondents")} value={r.respondents.toLocaleString(locale)} />
            <Stat label={t("mkChoices")} value={(r.fit?.choices ?? 0).toLocaleString(locale)} />
            <Stat label={t("mkHitRate")} value={r.fit ? `${Math.round(r.fit.hit_rate * 100)}%` : "–"} sub={r.fit ? t("mkChance", { pct: Math.round(r.fit.chance_rate * 100) }) : ""} />
            <Stat label={t("mkNone")} value={r.none_option ? `${Math.round(r.none_share * 100)}%` : "–"} sub={r.none_option ? t("mkOfChoices") : t("mkNotOffered")} />
          </div>
          <ul className="mt-1 space-y-1 text-sm">
            {leads.map(({ attribute, best, base }) => (
              <li key={attribute}>
                {richText(t("mkPreferred"), { attribute, level: <b>{best.level}</b> })}
                {best.wtp != null && best.wtp > 0 && richText(t("mkWorthMore"), { amount: <b className="num">{money(best.wtp)}</b>, base })}
              </li>
            ))}
            {noSlope && <li className="text-muted-foreground">{t("mkNoSlope")}</li>}
          </ul>
          <div className="mt-auto flex flex-wrap gap-2 pt-2">
            <Button asChild size="sm"><a href={conjointReportUrl(projectId, r.conjoint_id)} target="_blank" rel="noopener"><FileText className="size-4" /> {t("studioReport")}</a></Button>
            <Button asChild variant="outline" size="sm"><a href={conjointCsvUrl(projectId, r.conjoint_id)} download><Download className="size-4" /> {t("mkChoicesCsv")}</a></Button>
          </div>
        </div>
      </div>

      <StudyReading projectId={projectId} study="conjoints" jobId={r.conjoint_id} answers={r.answers.filter((a) => a.why && !a.error).length} />

      <section className="rounded-2xl border bg-card p-4">
        <h3 className="mb-3 text-sm font-semibold">{t("mkPartWorths")} <span className="font-normal text-muted-foreground">{t("mkPartWorthsHint")}</span></h3>
        <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
          {[...r.attributes.map((a) => a.name), ...(r.prices.length ? ["Price"] : [])].map((name) => (
            <div key={name}>
              <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{attributeLabel(name, t)}</h4>
              <div className="space-y-1">{levels(name).map((p) => <PartWorthRow key={p.level} p={p} span={span} money={money} />)}</div>
            </div>
          ))}
        </div>
      </section>

      <Simulator key={`${projectId}:${r.conjoint_id}`} report={r} />

      {r.segments.length > 0 && <Segments report={r} />}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {r.verbatims.length > 0 && <Verbatims items={r.verbatims} />}
        <section className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">{t("mkReadWithCare")}</h3>
          <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          <p className="mt-2 text-xs text-muted-foreground">{t("mkConjointFooter", { model: r.model, options: r.options })}{r.none_option ? t("mkPlusNone") : ""}{t("mkSeconds", { seconds: r.seconds.toFixed(0) })}</p>
        </section>
      </div>
    </div>
  );
}

function PartWorthRow({ p, span, money }: { p: PartWorth; span: number; money: (v: number) => string }) {
  const { t } = useI18n();
  const x = (v: number) => `${50 + (Math.max(-span, Math.min(span, v)) / span) * 50}%`;
  const left = Math.min(0, p.utility);
  const right = Math.max(0, p.utility);
  const wtp = p.wtp != null ? `${p.wtp >= 0 ? "+" : "−"}${money(Math.abs(p.wtp))}` : "";
  return (
    <div className="grid grid-cols-[minmax(5rem,8rem)_1fr_3.2rem_5.5rem] items-center gap-2"
      title={t("mkPartWorthTitle", { level: p.level, utility: p.utility.toFixed(2), low: p.ci_low.toFixed(2), high: p.ci_high.toFixed(2) }) + (wtp ? t("mkWtp", { amount: wtp }) : "")}>
      <span className="truncate text-sm">{p.level}</span>
      <div className="relative h-5 rounded-[4px] bg-foreground/[0.035]">
        <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/25" />
        <div className="absolute inset-y-1" style={{ left: x(left), right: `calc(100% - ${x(right)})`, background: p.utility >= 0 ? "var(--viz-pos-2)" : "var(--viz-neg-2)", borderRadius: 3 }} />
        <div className="absolute top-1/2 h-px -translate-y-1/2 bg-foreground/60" style={{ left: x(p.ci_low), right: `calc(100% - ${x(p.ci_high)})` }} />
      </div>
      <span className="num text-right text-xs">{p.utility >= 0 ? "+" : "−"}{Math.abs(p.utility).toFixed(2)}</span>
      <span className="num truncate text-right text-xs text-muted-foreground">{wtp}</span>
    </div>
  );
}

function Simulator({ report: r }: { report: Report }) {
  const { t } = useI18n();
  const curveConfig = { share: { label: t("mkShareOfA"), color: "var(--viz-1)" } } satisfies ChartConfig;
  const [products, setProducts] = useState<SimProduct[]>(() => defaultLineup(r));
  const money = (v: number) => formatMoney(v, r.currency);
  const lo = r.prices.length ? Math.min(...r.prices) : 0;
  const hi = r.prices.length ? Math.max(...r.prices) : 0;
  const result = shares(r, products);
  const curve = shareCurve(r, products);
  const update = (i: number, change: Partial<SimProduct>) => setProducts((ps) => ps.map((p, j) => (j === i ? { ...p, ...change } : p)));
  const rows = [...products.map((_, i) => t("mkProductLetter", { letter: LETTERS[i]! })), ...(result.length > products.length ? [t("mkNoneOfThese")] : [])];

  return (
    <section className="rounded-2xl border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{t("mkSimulator")} <span className="font-normal text-muted-foreground">{t("mkSimulatorHint")}</span></h3>
        {products.length < 4 && (
          <button type="button" onClick={() => setProducts((ps) => [...ps, { levels: r.attributes.map(() => 0), price: lo }])}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-foreground/[0.05] hover:text-foreground">
            <Plus className="size-3.5" /> {t("mkAddProduct")}
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <div className="grid grid-cols-1 items-start gap-2 sm:grid-cols-2">
          {products.map((p, i) => (
            <div key={i} className="space-y-1.5 rounded-xl border bg-background/50 p-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-medium">
                  <span className="grid size-6 place-items-center rounded-md text-xs font-bold text-white" style={{ background: `var(--viz-${(i % 4) + 1})` }}>{LETTERS[i]}</span>
                  <span className="num">{Math.round((result[i] ?? 0) * 100)}%</span>
                </span>
                {products.length > 1 && (
                  <button type="button" onClick={() => setProducts((ps) => ps.filter((_, j) => j !== i))} aria-label={t("mkRemoveProductLetter", { letter: LETTERS[i]! })}
                    className="rounded p-0.5 text-muted-foreground hover:text-destructive"><X className="size-3.5" /></button>
                )}
              </div>
              {r.attributes.map((a, k) => (
                <label key={a.name} className="grid grid-cols-[4.5rem_1fr] items-center gap-2 text-xs">
                  <span className="truncate text-muted-foreground" title={a.name}>{a.name}</span>
                  <select value={p.levels[k] ?? 0} onChange={(e) => update(i, { levels: p.levels.map((l, m) => (m === k ? Number(e.target.value) : l)) })}
                    className="h-7 rounded-md border bg-card/60 px-1.5 text-xs text-foreground">
                    {a.levels.map((l, m) => <option key={l} value={m}>{l}</option>)}
                  </select>
                </label>
              ))}
              {r.prices.length > 0 && (
                <label className="grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-2 text-xs">
                  <span className="text-muted-foreground">{t("mkPrice")}</span>
                  <input type="range" min={lo} max={hi} step={Math.max(1, Math.round((hi - lo) / 100))} value={p.price}
                    onChange={(e) => update(i, { price: Number(e.target.value) })} aria-label={t("mkPriceOfProduct", { letter: LETTERS[i]! })} />
                  <span className="num text-right">{money(p.price)}</span>
                </label>
              )}
            </div>
          ))}
        </div>
        <div className="space-y-3">
          <div className="space-y-1.5">
            {rows.map((label, i) => (
              <div key={label} className="grid grid-cols-[6.5rem_1fr_3rem] items-center gap-2">
                <span className="truncate text-sm">{label}</span>
                <div className="h-5 rounded-[4px] bg-foreground/[0.04]">
                  <div className="h-full rounded-r-[4px] transition-[width]" style={{ width: `${(result[i] ?? 0) * 100}%`, background: i < products.length ? `var(--viz-${(i % 4) + 1})` : "var(--viz-mid)" }} />
                </div>
                <span className="num text-right text-sm font-semibold">{Math.round((result[i] ?? 0) * 100)}%</span>
              </div>
            ))}
          </div>
          {curve.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-muted-foreground">{t("mkShareCurveHint")}</p>
              <ChartContainer config={curveConfig} className="aspect-auto h-[150px] w-full">
                <LineChart data={curve} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                  <ReferenceLine x={products[0]!.price} stroke="var(--foreground)" strokeOpacity={0.3} strokeDasharray="3 3" />
                  <XAxis dataKey="price" type="number" domain={[lo, hi]} tickFormatter={money} tickCount={4}
                    tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                  <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tickCount={3} tickLine={false} axisLine={false} width={36}
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                  <ChartTooltip cursor={{ stroke: "var(--foreground)", strokeOpacity: 0.25 }}
                    content={<ChartTooltipContent indicator="line" labelFormatter={(_v, payload) => {
                      const d = payload?.[0]?.payload as { price?: number } | undefined;
                      return d?.price != null ? money(d.price) : "";
                    }} formatter={(value) => (
                      <div className="flex w-full items-center justify-between gap-3">
                        <span className="text-muted-foreground">{t("mkShareOfA")}</span>
                        <span className="num font-semibold">{Math.round(Number(value) * 100)}%</span>
                      </div>
                    )} />} />
                  <Line dataKey="share" type="monotone" stroke="var(--color-share)" strokeWidth={2} dot={false} />
                </LineChart>
              </ChartContainer>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function Segments({ report: r }: { report: Report }) {
  const { t } = useI18n();
  const names = r.importances.map((i) => i.attribute);
  const overall = Object.fromEntries(r.importances.map((i) => [i.attribute, i.importance]));
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h3 className="mb-2 text-sm font-semibold">{t("mkBySegment")} <span className="font-normal text-muted-foreground">{t("mkConjointSegmentHint")}</span></h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr><th className="py-1">{t("mkColSegment")}</th><th className="text-right">n</th>{names.map((n) => <th key={n} className="text-right">{attributeLabel(n, t)}</th>)}{r.none_option && <th className="text-right">{t("mkNone")}</th>}</tr>
          </thead>
          <tbody className="num">
            {r.segments.map((s) => (
              <tr key={s.segment} className="border-t border-foreground/[0.06]">
                <td className="py-1">{segmentLabel(s.segment, t)}</td><td className="text-right">{s.n}</td>
                {names.map((n) => {
                  const d = (s.importances[n] ?? 0) - (overall[n] ?? 0);
                  return (
                    <td key={n} className="text-right">
                      <span className={cn("rounded px-1", Math.abs(d) >= 0.03 && (d > 0 ? "bg-[color-mix(in_oklab,var(--viz-pos-2)_18%,transparent)]" : "bg-[color-mix(in_oklab,var(--viz-neg-2)_18%,transparent)]"))}>
                        {Math.round((s.importances[n] ?? 0) * 100)}%
                      </span>
                    </td>
                  );
                })}
                {r.none_option && <td className="text-right">{Math.round(s.none_share * 100)}%</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Verbatims({ items }: { items: string[] }) {
  const { t } = useI18n();
  const [all, setAll] = useState(false);
  const counted = [...items.reduce((m, v) => m.set(v, (m.get(v) ?? 0) + 1), new Map<string, number>())].sort((a, b) => b[1] - a[1]);
  const shown = all ? counted : counted.slice(0, 6);
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h3 className="mb-2 text-sm font-semibold">{t("mkWhatMattered")} <span className="font-normal text-muted-foreground">· {items.length}</span></h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {shown.map(([v, k]) => (
          <blockquote key={v} className="rounded-xl bg-foreground/[0.035] px-3 py-2 text-sm">
            <Quote className="mb-1 size-3.5 text-muted-foreground" aria-hidden />{v}
            {k > 1 && <span className="num ml-1.5 text-xs text-muted-foreground">×{k}</span>}
          </blockquote>
        ))}
      </div>
      {counted.length > 6 && (
        <button type="button" onClick={() => setAll((a) => !a)} className="mt-2 text-xs text-muted-foreground underline-offset-2 hover:underline">
          {all ? t("studioShowFewer") : t("studioShowAll", { count: counted.length })}
        </button>
      )}
    </section>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-foreground/[0.035] px-3 py-2">
      <div className="text-[0.7rem] text-muted-foreground">{label}</div>
      <div className="num truncate text-xl font-semibold" title={value}>{value}</div>
      {sub && <div className="text-[0.7rem] text-muted-foreground">{sub}</div>}
    </div>
  );
}
