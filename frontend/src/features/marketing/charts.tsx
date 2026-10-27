// Charts of the marketing studio: paired lifts with CIs, 1–5 answer distributions, preference shares and the
// Van Westendorp price curves. Marks use the --viz-* tokens; every value is also in a label, tooltip or table.

import { useState } from "react";
import { CartesianGrid, ErrorBar, Line, LineChart, ReferenceArea, ReferenceLine, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/shared/components/ui/chart";
import type { PriceRange, PriceResponse } from "@/shared/api/marketing";
import { cn } from "@/shared/utils/cn";
import { formatMoney, formatPercent, formatDecimal } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";

// ── Lift with confidence interval ─────────────────────────────────────────

export interface LiftRow {
  key: string;
  label: string;
  sub?: string;
  diff: number;
  lo: number;
  hi: number;
  /** Shown in the tooltip, e.g. "P(better) 97 %". */
  detail?: string;
}

/** Paired differences to control on one shared, zero-centred axis: dot = estimate, bar = 95 % CI. */
export function LiftChart({ rows, format, axisLabel }: { rows: LiftRow[]; format: (v: number) => string; axisLabel: string }) {
  const { t } = useI18n();
  const [hover, setHover] = useState<string | null>(null);
  const span = Math.max(1e-9, ...rows.flatMap((r) => [Math.abs(r.lo), Math.abs(r.hi), Math.abs(r.diff)])) * 1.12;
  const x = (v: number) => `${50 + (v / span) * 50}%`;
  return (
    <div className="space-y-1.5">
      {rows.map((r) => {
        const sure = r.lo > 0 ? "up" : r.hi < 0 ? "down" : "unsure";
        const active = hover === r.key;
        return (
          <div
            key={r.key}
            tabIndex={0}
            onPointerEnter={() => setHover(r.key)}
            onPointerLeave={() => setHover(null)}
            onFocus={() => setHover(r.key)}
            onBlur={() => setHover(null)}
            className="group grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-lg px-1.5 py-1 outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:grid-cols-[minmax(7rem,11rem)_1fr_6.5rem]"
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium" title={r.label}>{r.label}</div>
              {r.sub && <div className="truncate text-[0.7rem] text-muted-foreground" title={r.sub}>{r.sub}</div>}
            </div>
            <div className="relative order-last col-span-2 h-7 sm:order-none sm:col-span-1">
              <div className="absolute inset-y-0 left-1/2 w-px bg-foreground/25" aria-hidden />
              <div
                className={cn("absolute top-1/2 h-2 -translate-y-1/2 rounded-full transition-opacity", active ? "opacity-60" : "opacity-35")}
                style={{ left: x(Math.min(r.lo, r.hi)), width: `${(Math.abs(r.hi - r.lo) / span) * 50}%`, background: "var(--viz-1)" }}
              />
              <div
                className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
                style={{ left: x(r.diff), background: "var(--viz-1)" }}
              />
              {active && (
                <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded-lg border bg-popover px-2.5 py-1.5 text-xs shadow-lg">
                  <div className="num font-semibold">{format(r.diff)}</div>
                  <div className="text-muted-foreground">{t("studioCi95To", { low: format(r.lo), high: format(r.hi) })}</div>
                  {r.detail && <div className="text-muted-foreground">{r.detail}</div>}
                </div>
              )}
            </div>
            <div className="text-right">
              <div className="num text-sm font-semibold">{format(r.diff)}</div>
              <div className={cn("text-[0.68rem]", sure === "up" ? "text-positive" : sure === "down" ? "text-negative" : "text-muted-foreground")}>
                {sure === "up" ? t("mkClearlyUp") : sure === "down" ? t("mkClearlyDown") : t("mkWithinNoise")}
              </div>
            </div>
          </div>
        );
      })}
      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 px-1.5 text-[0.68rem] text-muted-foreground sm:grid-cols-[minmax(7rem,11rem)_1fr_6.5rem]">
        <span className="hidden sm:block" />
        <div className="relative col-span-2 h-4 sm:col-span-1">
          <span className="absolute left-0">{format(-span)}</span>
          <span className="absolute left-1/2 -translate-x-1/2">{t("mkZeroControl")}</span>
          <span className="absolute right-0">{format(span)}</span>
        </div>
        <span className="col-span-2 text-right sm:col-span-1">{axisLabel}</span>
      </div>
    </div>
  );
}

// ── 1–5 answers ────────────────────────────────────────────────────────────

const LIKERT = ["var(--viz-neg-2)", "var(--viz-neg-1)", "var(--viz-mid)", "var(--viz-pos-1)", "var(--viz-pos-2)"];
const LIKERT_INK = ["#fff", "var(--foreground)", "var(--foreground)", "var(--foreground)", "#fff"];

export function LikertLegend({ low, high }: { low: string; high: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.7rem] text-muted-foreground">
      {LIKERT.map((c, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          <span className="size-2.5 rounded-[3px]" style={{ background: c }} />
          {i === 0 ? `1 ${low}` : i === 4 ? `5 ${high}` : i + 1}
        </span>
      ))}
    </div>
  );
}

/** One respondent distribution as a 100 % bar; the percentage sits inside a segment only when it fits. */
export function LikertBar({ counts }: { counts: number[] }) {
  const { t } = useI18n();
  const [hover, setHover] = useState<number | null>(null);
  const n = counts.reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="relative flex h-5 w-full gap-[2px] overflow-visible">
      {counts.map((c, i) => {
        const share = c / n;
        if (share === 0) return null;
        return (
          <div
            key={i}
            tabIndex={0}
            onPointerEnter={() => setHover(i)}
            onPointerLeave={() => setHover(null)}
            onFocus={() => setHover(i)}
            onBlur={() => setHover(null)}
            className={cn("relative grid place-items-center text-[0.7rem] font-semibold outline-none first:rounded-l-[4px] last:rounded-r-[4px]",
              hover === i && "brightness-110")}
            style={{ flexGrow: share, flexBasis: 0, background: LIKERT[i], color: LIKERT_INK[i] }}
          >
            {share >= 0.09 && <span className="num">{Math.round(share * 100)}</span>}
            {hover === i && (
              <span className="pointer-events-none absolute bottom-full z-10 mb-1 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-[0.7rem] font-normal text-popover-foreground shadow-lg">
                <b className="num">{formatPercent(share, 0)}</b>{t("mkLikertAnswered", { value: i + 1, count: c })}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Preference shares ─────────────────────────────────────────────────────

export function ShareBars({ rows }: { rows: { label: string; share: number; lo: number; hi: number }[] }) {
  const { t } = useI18n();
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[minmax(5rem,9rem)_1fr_7.5rem] items-center gap-3" title={t("mkShareTitle", { label: r.label, share: formatDecimal(r.share * 100, 0), low: formatDecimal(r.lo * 100, 0), high: formatDecimal(r.hi * 100, 0) })}>
          <span className="truncate text-sm font-medium">{r.label}</span>
          <div className="relative h-6 rounded-[4px] bg-foreground/[0.04]">
            <div className="absolute inset-y-0.5 left-0 rounded-r-[4px]" style={{ width: `${r.share * 100}%`, maxWidth: "100%", background: "var(--viz-1)" }} />
            <div className="absolute top-1/2 h-3 -translate-y-1/2 border-x-2 border-foreground/55" style={{ left: `${r.lo * 100}%`, width: `${(r.hi - r.lo) * 100}%` }}>
              <div className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-foreground/55" />
            </div>
          </div>
          <span className="num text-right text-sm"><b>{formatPercent(r.share, 0)}</b> <span className="text-xs text-muted-foreground">{formatDecimal(r.lo * 100, 0)}–{formatDecimal(r.hi * 100, 0)}</span></span>
        </div>
      ))}
    </div>
  );
}

// ── Van Westendorp ────────────────────────────────────────────────────────

const VW_SERIES = ["too_cheap", "cheap", "expensive", "too_expensive"] as const;

export function VanWestendorpChart({ price, currency }: { price: PriceRange; currency: string }) {
  const { t } = useI18n();
  const vwConfig = {
    too_cheap: { label: t("mkVwTooCheap"), color: "var(--viz-1)" },
    cheap: { label: t("mkVwBargain"), color: "var(--viz-2)" },
    expensive: { label: t("mkVwExpensive"), color: "var(--viz-3)" },
    too_expensive: { label: t("mkVwTooExpensive"), color: "var(--viz-4)" },
  } satisfies ChartConfig;
  const data = price.curve.map(([p, tc, c, e, te]) => ({ price: p, too_cheap: tc * 100, cheap: c * 100, expensive: e * 100, too_expensive: te * 100 }));
  const money = (v: number) => formatMoney(v, currency);
  const lo = price.point_of_marginal_cheapness;
  const hi = price.point_of_marginal_expensiveness;
  return (
    <ChartContainer config={vwConfig} className="aspect-auto h-[260px] w-full">
      <LineChart data={data} margin={{ top: 18, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
        {lo != null && hi != null && <ReferenceArea x1={lo} x2={hi} fill="var(--viz-1)" fillOpacity={0.07} ifOverflow="hidden" />}
        {price.optimal_price_point != null && (
          <ReferenceLine x={price.optimal_price_point} stroke="var(--foreground)" strokeOpacity={0.55} strokeWidth={1}
            label={{ value: t("mkOptimalPrice", { price: money(price.optimal_price_point) }), position: "top", fontSize: 11, fill: "var(--foreground)" }} />
        )}
        <XAxis dataKey="price" type="number" domain={["dataMin", "dataMax"]} tickFormatter={money} tickLine={false} axisLine={false}
          tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} minTickGap={28} />
        <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v: number) => formatPercent(v / 100, 0)} tickLine={false} axisLine={false} width={40}
          tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
        <ChartTooltip cursor={{ stroke: "var(--foreground)", strokeOpacity: 0.3 }}
          content={<ChartTooltipContent indicator="line" labelFormatter={(_v, payload) => {
            const p = payload?.[0]?.payload?.price;
            return typeof p === "number" ? t("mkAtPrice", { price: money(p) }) : "";
          }} formatter={(value, name) => (
            <div className="flex w-full items-center justify-between gap-3">
              <span className="text-muted-foreground">{vwConfig[name as keyof typeof vwConfig]?.label ?? String(name)}</span>
              <span className="num font-semibold">{formatPercent(Number(value) / 100, 0)}</span>
            </div>
          )} />} />
        <ChartLegend itemSorter={null} content={<ChartLegendContent />} />
        {VW_SERIES.map((k) => (
          <Line key={k} dataKey={k} type="monotone" stroke={`var(--color-${k})`} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--card)" }} />
        ))}
      </LineChart>
    </ChartContainer>
  );
}

// ── Demand curve (price sweep) ────────────────────────────────────────────

/** Units of one product per 100 visitors at each tested price, with the arms' 95 % intervals. */
export function DemandChart({ response, currency, control }: { response: PriceResponse; currency: string; control: string }) {
  const { t } = useI18n();
  const demandConfig = { units: { label: t("mkColUnits100"), color: "var(--viz-1)" } } satisfies ChartConfig;
  const data = response.points.map((p) => ({
    price: p.price, units: p.units * 100, err: [(p.units - p.units_low) * 100, (p.units_high - p.units) * 100] as [number, number], arm: p.arm,
  }));
  const money = (v: number) => formatMoney(v, currency);
  return (
    <ChartContainer config={demandConfig} className="aspect-auto h-[220px] w-full">
      <LineChart data={data} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
        {response.best_price != null && <ReferenceLine x={response.best_price} stroke="var(--foreground)" strokeOpacity={0.25} />}
        <XAxis dataKey="price" type="number" domain={["dataMin", "dataMax"]} ticks={data.map((d) => d.price)} tickFormatter={money}
          tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
        <YAxis domain={[0, "auto"]} tickCount={5} allowDecimals tickLine={false} axisLine={false} width={36} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
        <ChartTooltip cursor={{ stroke: "var(--foreground)", strokeOpacity: 0.25 }}
          content={<ChartTooltipContent indicator="line" labelFormatter={(_v, payload) => {
            const d = payload?.[0]?.payload as { price?: number; arm?: string } | undefined;
            return d?.price != null ? `${d.arm === control ? t("mkControl") : d.arm} · ${money(d.price)}` : "";
          }} formatter={(value) => (
            <div className="flex w-full items-center justify-between gap-3">
              <span className="text-muted-foreground">{t("mkColUnits100")}</span>
              <span className="num font-semibold">{formatDecimal(Number(value), 1)}</span>
            </div>
          )} />} />
        <Line dataKey="units" type="monotone" stroke="var(--color-units)" strokeWidth={2}
          dot={(props: { cx?: number; cy?: number; index?: number; payload?: { price: number } }) => (
            <circle key={props.index} cx={props.cx} cy={props.cy} r={props.payload?.price === response.best_price ? 6 : 4} strokeWidth={2} stroke="var(--card)"
              fill={props.payload?.price === response.best_price ? "var(--viz-2)" : "var(--color-units)"} />
          )}>
          <ErrorBar dataKey="err" width={6} strokeWidth={2} stroke="var(--color-units)" opacity={0.45} direction="y" />
        </Line>
      </LineChart>
    </ChartContainer>
  );
}
