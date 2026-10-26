// What virtual shoppers did on the stores of a run: conversion and money per variant, paired differences with
// intervals, the funnel, where they left, segments, what they searched and bought, where they clicked, and every
// shopper's visit.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart3, ChartPie, ClipboardList, Columns2, Filter, GitCompareArrows, Grid3x3, MailCheck, Megaphone, MessageSquareText,
  MousePointerClick, Play, Route, Search, ShoppingBag, Store, Swords, TriangleAlert, Users, Waves,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import {
  clickstreamUrl, deleteRun, getRun, onlineKeys, runReportUrl,
  type ClickPoint, type Device, type OnlineRunResult, type PageKind, type PairedDelta, type SegmentRow, type VariantSummary,
} from "@/shared/api/online";
import { ApiError } from "@/shared/api/errors";
import { cn } from "@/shared/utils/cn";
import { currencyCode, formatMoney, formatPercent, formatDecimal } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { ChannelMix } from "./ChannelMix";
import { DiffForest, FunnelChart, OutcomeBars, SegmentHeat, StatTiles, StoreKey, Swatch, type HeatCell, type StatMetric } from "./charts";
import { JourneyViewer } from "./JourneyViewer";
import { OnlineAnalyst } from "./OnlineAnalyst";
import {
  AD_PLACEMENT_LABELS, DELTA_LABELS, FRICTION_HARMS, FRICTION_LABELS, PAGE_LABELS, segmentValueLabel, storeColor,
} from "./labels";
import { PageFlow } from "./PageFlow";
import { PricesToStore } from "./PricesToStore";
import { RunHero } from "./RunHero";
import { ShopperGallery } from "./ShopperGallery";
import { ShopperRiver } from "./ShopperRiver";
import { WhoChanged } from "./WhoChanged";

const DIMENSIONS: { id: SegmentRow["dimension"]; label: MessageKey }[] = [
  { id: "mission", label: "onSegMission" }, { id: "device", label: "onSegDevice" },
  { id: "age_group", label: "onSegAge" }, { id: "gender", label: "onSegGender" }, { id: "vision", label: "onSegVision" },
  { id: "arrival", label: "onSegArrival" },
];

export function RunReport({ projectId, runId, onDeleted, wide = false, onWide = () => {}, initialJourney, onTry }: {
  projectId: string; runId: string; onDeleted: () => void;
  /** The report fills the page (the store list is hidden). */
  wide?: boolean; onWide?: () => void;
  /** A shopper's visit to play as soon as the report opens (a link from another tab). */
  initialJourney?: Journey;
  /** Open a store's run form with these quick experiments ticked (suggested by the analyst). */
  onTry?: (siteId: string, experiments: string[]) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [journey, setJourney] = useState<Journey | null>(initialJourney ?? null);
  const [heroGone, setHeroGone] = useState(false);
  // Once the hero's buttons scroll away, a dock keeps the shopper replay one click away.
  const watchHero = (el: HTMLElement | null) => {
    if (!el || typeof IntersectionObserver === "undefined") return;
    // Only once it has scrolled up out of view: a hero still below the fold (narrow screens) needs no dock yet.
    const io = new IntersectionObserver(([entry]) => setHeroGone(entry ? !entry.isIntersecting && entry.boundingClientRect.top < 0 : false));
    io.observe(el);
    return () => io.disconnect();
  };
  const run = useQuery({
    queryKey: onlineKeys.run(projectId, runId),
    queryFn: ({ signal }) => getRun(projectId, runId, signal),
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status.status) ? false : 1500),
  });
  const remove = useMutation({
    mutationFn: () => deleteRun(projectId, runId),
    onSuccess: () => {
      // Drop the deleted run and its replays rather than refetching them into 404s; only the list changes.
      onDeleted();
      qc.removeQueries({ queryKey: onlineKeys.run(projectId, runId) });
      void qc.invalidateQueries({ queryKey: onlineKeys.runs(projectId), exact: true });
    },
  });
  if (run.isPending) return <div className="panel rounded-[1.6rem] p-4 text-sm text-muted-foreground">{t("studioLoading")}</div>;
  if (run.isError && run.error instanceof ApiError && run.error.status === 404) {
    // An old link to a deleted run: say so and offer the way back to the list.
    return (
      <div role="alert" className="panel flex flex-wrap items-center gap-3 rounded-[1.6rem] p-4 text-sm">
        <span className="min-w-0 flex-[1_1_14rem]"><b className="font-medium">{t("onRunMissing")}</b> <span className="text-muted-foreground">{t("onRunMissingHint")}</span></span>
        <button type="button" onClick={onDeleted} className="rounded-xl border px-3 py-1.5 text-sm font-medium hover:bg-muted">{t("onRunMissingClose")}</button>
      </div>
    );
  }
  if (run.isError) return <div role="alert" className="panel rounded-[1.6rem] p-4 text-sm text-destructive">{run.error.message}</div>;
  const { status, result } = run.data;
  const running = status.status === "pending" || status.status === "running";
  // The shopper who says most about the run: one whose visit ended differently between the stores, else a buyer.
  const featured = result && (result.comparisons.flatMap((c, i) => c.switches.map((sw) => ({ variant: i + 1, shopper: sw.shopper_id })))[0]
    ?? { variant: 0, shopper: Object.entries(result.visits ?? {}).find(([, v]) => v[0]?.outcome === "purchased")?.[0] ?? result.shoppers[0]?.id ?? "" });

  const watch = result && featured?.shopper ? () => setJourney({ variant: featured.variant, shopper: featured.shopper, play: true }) : null;
  const compare = result && result.variants.length > 1 && featured?.shopper
    ? () => setJourney({ variant: featured.variant || 1, shopper: featured.shopper, compare: true }) : null;

  return (
    <div className="flex flex-col gap-4">
      <RunHero status={status} result={result} heroRef={watchHero} wide={wide} onWide={onWide} onWatch={watch} onCompare={compare}
        csvUrl={status.status === "completed" ? clickstreamUrl(projectId, runId) : null}
        reportUrl={status.status === "completed" ? runReportUrl(projectId, runId) : null} onDelete={running ? null : () => remove.mutate()}
        deleting={remove.isPending} deleteError={remove.error?.message ?? ""} />

      {running && (
        <section className="panel space-y-2 rounded-[1.4rem] p-4 text-sm" aria-live="polite">
          <div className="font-medium">{status.phase ? t("onRunPhase", { phase: status.phase }) : t("onRunQueued")}</div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="heat-gradient h-full transition-[width]" style={{ width: `${(status.total ? status.done / status.total : 0.02) * 100}%` }} />
          </div>
          <div className="text-xs text-muted-foreground">{t("onRunProgress", { done: status.done, total: status.total })}</div>
        </section>
      )}
      {status.status === "failed" && <section role="alert" className="panel rounded-[1.4rem] p-4 text-sm text-destructive">{status.error}</section>}
      {result && <Report projectId={projectId} result={result} onJourney={setJourney} onTry={onTry}
        customers={status.request.source === "project"} />}
      {result && heroGone && !journey && (watch || compare) && (
        <div className="pointer-events-none fixed inset-x-0 bottom-5 z-40 flex justify-center px-4">
          <div className="dark pointer-events-auto flex items-center gap-1 rounded-full border border-white/15 bg-[#0b0c14]/90 p-1.5 text-white shadow-[0_20px_60px_-15px_rgb(40_20_110/0.9)] backdrop-blur-xl animate-in fade-in slide-in-from-bottom-4"
            role="toolbar" aria-label={t("onDockLabel")}>
            {watch && (
              <button type="button" onClick={watch} className="inline-flex h-10 items-center gap-2 rounded-full bg-white pr-4 pl-1.5 text-sm font-semibold text-neutral-950 transition-transform hover:scale-[1.03]">
                <span className="grid size-7 place-items-center rounded-full heat-gradient text-white dark:text-neutral-950"><Play className="size-3.5 fill-current" aria-hidden /></span>
                {t("onWatchShopperCta")}
              </button>
            )}
            {compare && (
              <button type="button" onClick={compare} className="inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm hover:bg-white/10">
                <Columns2 className="size-4" aria-hidden /> {t("onSideBySide")}
              </button>
            )}
            <a href="#online-stream" onClick={(e) => { e.preventDefault(); jumpTo("online-stream"); }}
              className="inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm hover:bg-white/10">
              <Users className="size-4" aria-hidden /> {t("onRiverTitle")}
            </a>
            <a href="#online-ask" onClick={(e) => { e.preventDefault(); jumpTo("online-ask"); }}
              className="inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm hover:bg-white/10">
              <MessageSquareText className="size-4" aria-hidden /> {t("analystAsk")}
            </a>
          </div>
        </div>
      )}
      {result && journey && (
        <JourneyViewer projectId={projectId} runId={result.run_id} variant={journey.variant} shopperId={journey.shopper}
          variants={result.variants.map((s) => s.site_name)} rival={result.rival_name ?? ""} currency={result.currency} play={journey.play}
          compare={journey.compare}
          onVariant={(variant) => setJourney({ ...journey, variant })} onClose={() => setJourney(null)} />
      )}
    </div>
  );
}

export interface Journey { variant: number; shopper: string; play?: boolean; compare?: boolean }

function Report({ projectId, result, onJourney, onTry, customers }: {
  projectId: string; result: OnlineRunResult; onJourney: (journey: Journey) => void;
  onTry?: (siteId: string, experiments: string[]) => void;
  /** The shoppers are the store's own customers, so they can be read next to a store run. */
  customers: boolean;
}) {
  const { t } = useI18n();
  const code = currencyCode(result.currency);
  const money = (x: number) => formatMoney(Math.round(x), code);
  const pct = (x: number) => formatPercent(x, 1);
  const v = result.variants;
  const names = v.map((s) => s.site_name);
  const rows: { label: MessageKey; value: (s: VariantSummary) => string }[] = [
    { label: "onKpiSessions", value: (s) => String(s.sessions) },
    { label: "onKpiConversion", value: (s) => pct(s.conversion) },
    { label: "onKpiRevenuePerSession", value: (s) => money(s.revenue_per_session) },
    { label: "onKpiAov", value: (s) => (s.purchases ? money(s.aov) : "—") },
    { label: "onKpiRevenue", value: (s) => money(s.revenue) },
    { label: "onKpiAddToCart", value: (s) => pct(s.add_to_cart_rate) },
    { label: "onKpiAbandonment", value: (s) => pct(s.cart_abandonment) },
    { label: "onKpiBounce", value: (s) => pct(s.bounce_rate) },
    { label: "onKpiSteps", value: (s) => formatDecimal(s.avg_steps, 1) },
    { label: "onKpiSeconds", value: (s) => t("onSecondsShort", { seconds: Math.round(s.avg_seconds) }) },
    { label: "onKpiSearchShare", value: (s) => pct(s.search_share) },
    { label: "onKpiZeroResults", value: (s) => String(s.zero_result_searches) },
  ];
  const points = (a: number, b: number) => `${a - b >= 0 ? "+" : "−"}${formatDecimal(Math.abs(a - b) * 100, 1)}${t("onPointsSuffix")}`;
  const moneyDelta = (a: number, b: number) => `${a - b >= 0 ? "+" : "−"}${money(Math.abs(a - b))}`;
  const tiles: StatMetric[] = [
    { key: "conversion", label: t("onKpiConversion"), values: v.map((s) => s.conversion), format: pct, delta: points, better: "up" },
    { key: "revenue", label: t("onKpiRevenuePerSession"), values: v.map((s) => s.revenue_per_session), format: money, delta: moneyDelta, better: "up" },
    { key: "aov", label: t("onKpiAov"), values: v.map((s) => (s.purchases ? s.aov : null)), format: money, delta: moneyDelta, better: "up" },
    { key: "cart", label: t("onKpiAddToCart"), values: v.map((s) => s.add_to_cart_rate), format: pct, delta: points, better: "up" },
    { key: "abandon", label: t("onKpiAbandonment"), values: v.map((s) => s.cart_abandonment), format: pct, delta: points, better: "down" },
    { key: "bounce", label: t("onKpiBounce"), values: v.map((s) => s.bounce_rate), format: pct, delta: points, better: "down" },
  ];
  const sections: { id: string; label: string; show: boolean }[] = [
    { id: "online-stream", label: t("onRiverTitle"), show: Object.keys(result.visits ?? {}).length > 0 },
    { id: "online-shoppers", label: t("onCardsTitle"), show: true },
    { id: "online-kpis", label: t("onKpis"), show: true },
    { id: "online-compare", label: t("onCompareTitle"), show: result.comparisons.length > 0 },
    { id: "online-ask", label: t("analystTitle"), show: true },
    { id: "online-channels", label: t("onChNav"), show: customers },
    { id: "online-funnel", label: t("onFunnel"), show: true },
    { id: "online-flow", label: t("onFlowTitle"), show: v.some((s) => (s.flow ?? []).length > 0) },
    { id: "online-ads", label: t("onAds"), show: v.some((s) => s.ads.length > 0) },
    { id: "online-rival", label: t("onRivalNav"), show: !!result.rival_name },
    { id: "online-frictions", label: t("onFrictions"), show: true },
    { id: "online-surveys", label: t("onSurveys"), show: v.some((s) => s.survey) },
    { id: "online-segments", label: t("onSegments"), show: true },
    { id: "online-products", label: t("onTopProducts"), show: true },
    { id: "online-clicks", label: t("onHeatmap"), show: v.some((s) => s.clicks.length > 0) },
  ];

  return (
    <>
      <SectionNav label={t("onNavLabel")} sections={sections.filter((x) => x.show)} />
      {result.notes.length > 0 && (
        <ul className="panel list-disc space-y-0.5 rounded-[1.4rem] py-3 pr-4 pl-8 text-xs text-muted-foreground">
          {result.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}

      {Object.keys(result.visits ?? {}).length > 0 && (
        <Section id="online-stream" icon={Waves} title={t("onRiverTitle")} hint={t("onRiverHint")}>
          <ShopperRiver result={result} money={money} onWatch={(variant, shopper) => onJourney({ variant, shopper, play: true })} />
        </Section>
      )}

      <Section id="online-shoppers" icon={Users} title={t("onCardsTitle")} hint={t("onCardsHint")}>
        <ShopperGallery result={result} money={money}
          onWatch={(variant, shopper) => onJourney({ variant, shopper, play: true })}
          onCompare={(variant, shopper) => onJourney({ variant, shopper, compare: true })}
          onSteps={(variant, shopper) => onJourney({ variant, shopper })} />
      </Section>

      <Section id="online-kpis" icon={BarChart3} title={t("onKpis")}>
        {v.length > 1 && <StoreKey names={names} />}
        <StatTiles metrics={tiles} names={names} />
        <details className="group rounded-xl border bg-card/40 px-3 py-2">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground group-open:mb-2">{t("onAllNumbers")}</summary>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground">
                <th className="py-1 pr-3 font-medium" />
                {v.map((s, i) => <th key={s.site_id} className="py-1 pr-3 font-medium">{s.site_name}{v.length > 1 && <span className="ml-1 rounded bg-muted px-1 text-[0.7rem]">{i === 0 ? t("onControl") : t("onVariantLetter", { letter: String.fromCharCode(65 + i) })}</span>}</th>)}
              </tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.label} className="border-t">
                    <td className="py-1 pr-3 text-xs text-muted-foreground">{t(row.label)}</td>
                    {v.map((s) => <td key={s.site_id} className="py-1 pr-3 tabular-nums">{row.value(s)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </Section>

      {result.comparisons.length > 0 && (
        <Section id="online-compare" icon={GitCompareArrows} title={t("onCompareTitle")} hint={t("onCompareHint")}>
          {result.comparisons.map((c, ci) => (
            <div key={c.site_id} className="space-y-1 rounded-2xl border bg-card/40 p-2">
              <div className="flex items-center gap-1.5 px-1.5 text-xs font-medium"><Swatch index={ci + 1} />{t("onCompareVs", { variant: c.site_name, control: v[0]?.site_name ?? "" })}</div>
              <DiffForest rows={c.deltas.map((d) => {
                const isMoney = d.metric === "revenue_per_session" || d.metric === "rival_revenue_per_session";
                const isRate = d.metric === "conversion" || d.metric === "add_to_cart_rate";
                const clear = d.ci_low !== null && d.ci_high !== null && (d.ci_low > 0 || d.ci_high < 0);
                return {
                  key: d.metric, label: t(DELTA_LABELS[d.metric]), diff: d.diff, low: d.ci_low, high: d.ci_high,
                  format: (x: number) => (isMoney ? money(x) : isRate ? `${formatDecimal(x * 100, 1)}${t("onPointsSuffix")}`
                    : d.metric === "seconds" ? t("onSecondsShort", { seconds: Math.round(x) }) : formatDecimal(x, 1)),
                  // Less taken by the rival is good for the store; time and clicks are neither.
                  upIsGood: d.metric === "seconds" || d.metric === "steps" ? null : d.metric !== "rival_revenue_per_session",
                  note: clear ? undefined : <Needed delta={d} />,
                };
              })} />
              <PricesToStore projectId={projectId} runId={result.run_id} variant={ci + 1} />
            </div>
          ))}
        </Section>
      )}

      <div id="online-changed" className="scroll-mt-16 empty:hidden"><WhoChanged result={result} money={money} onReplay={(variant, shopper) => onJourney({ variant, shopper })}
        onCompare={(variant, shopper) => onJourney({ variant, shopper, compare: true })} /></div>

      {customers && (
        <Section id="online-channels" icon={Store} title={t("onChTitle")} hint={t("onChHint")}>
          <ChannelMix projectId={projectId} runId={result.run_id} />
        </Section>
      )}

      <Section id="online-ask" icon={MessageSquareText} title={t("analystTitle")} hint={t("onAnalystHint")}>
        <OnlineAnalyst projectId={projectId} runId={result.run_id} compared={result.comparisons.length > 0}
          controlSiteId={result.variants[0]?.site_id} onTry={onTry} />
      </Section>

      <div id="online-funnel" tabIndex={-1} className="grid grid-cols-1 scroll-mt-16 gap-3 outline-none xl:grid-cols-2">
        <Section icon={Filter} title={t("onFunnel")}>
          {v.length > 1 && <StoreKey names={names} />}
          <FunnelChart variants={v} />
        </Section>
        <Section icon={ChartPie} title={t("onOutcomes")}>
          <OutcomeBars variants={v} />
          <div className="space-y-0.5 text-xs text-muted-foreground">
            {v.map((s, i) => (
              <div key={s.site_id} className="flex items-start gap-1.5">
                <Swatch index={i} className="mt-1" />
                <span>{t("onExits")}: {s.exits.slice(0, 5).map((e) => `${t(PAGE_LABELS[e.page])} (${e.sessions})`).join(", ") || "—"}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>

      {v.some((s) => (s.flow ?? []).length > 0) && (
        <Section id="online-flow" icon={Route} title={t("onFlowTitle")} hint={t("onFlowHint")}>
          <PageFlow variants={v} />
        </Section>
      )}

      <div id="online-ads" tabIndex={-1} className="scroll-mt-16 outline-none empty:hidden"><Ads result={result} money={money} pct={pct} /></div>
      <div id="online-recovery" className="scroll-mt-16 empty:hidden"><Recovery variants={v} money={money} pct={pct} /></div>
      <div id="online-rival" tabIndex={-1} className="scroll-mt-16 outline-none empty:hidden"><Rival result={result} money={money} pct={pct} /></div>
      <div id="online-frictions" tabIndex={-1} className="scroll-mt-16 outline-none empty:hidden"><Frictions variants={v} money={money} pct={pct} /></div>
      <div id="online-surveys" tabIndex={-1} className="scroll-mt-16 outline-none empty:hidden"><Surveys variants={v} pct={pct} /></div>
      <div id="online-segments" tabIndex={-1} className="scroll-mt-16 outline-none empty:hidden"><Segments result={result} money={money} pct={pct} /></div>

      <div id="online-products" tabIndex={-1} className="grid grid-cols-1 scroll-mt-16 gap-3 outline-none xl:grid-cols-2">
        <Section icon={Search} title={t("onSearches")} hint={t("onSearchesHint")}>
          {v.map((s, si) => (
            <div key={s.site_id}>
              {v.length > 1 && <div className="flex items-center gap-1.5 text-xs font-medium"><Swatch index={si} />{s.site_name}</div>}
              {s.searches.length === 0 ? <p className="text-xs text-muted-foreground">{t("onNoSearches")}</p> : (
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-muted-foreground"><th className="font-medium">{t("onColQuery")}</th><th className="font-medium">{t("onColCount")}</th><th className="font-medium">{t("onColZero")}</th><th className="font-medium">{t("onColBought")}</th></tr></thead>
                  <tbody>{s.searches.slice(0, 12).map((q) => (
                    <tr key={q.query} className="border-t">
                      <td className="py-0.5 pr-2">{q.query}</td><td className="tabular-nums">{q.count}</td>
                      <td className={cn("tabular-nums", q.zero_results > 0 && "font-semibold text-destructive")}>{q.zero_results}</td>
                      <td className="tabular-nums">{q.purchases}</td>
                    </tr>
                  ))}</tbody>
                </table>
              )}
            </div>
          ))}
        </Section>
        <Section icon={ShoppingBag} title={t("onTopProducts")}>
          {v.map((s, si) => {
            const top = s.products.slice(0, 10);
            const best = Math.max(1e-9, ...top.map((p) => p.revenue));
            return (
              <div key={s.site_id} className="space-y-1">
                {v.length > 1 && <div className="flex items-center gap-1.5 text-xs font-medium"><Swatch index={si} />{s.site_name}</div>}
                {top.map((p) => (
                  <div key={p.product_id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-xs" title={`${p.name}: ${t("onColViews")} ${p.views} · ${t("onColAdds")} ${p.adds} · ${t("onColUnits")} ${p.units}`}>
                    <div className="min-w-0">
                      <div className="truncate" title={p.name}>{p.name}</div>
                      <div className="mt-0.5 h-1.5 rounded-r-[4px] bg-[var(--viz-grid)]"><div className="h-full rounded-r-[4px]" style={{ width: `${Math.max(1, (p.revenue / best) * 100)}%`, background: storeColor(si) }} /></div>
                    </div>
                    <span className="tabular-nums">{money(p.revenue)} <span className="text-muted-foreground">· {p.units}</span></span>
                  </div>
                ))}
              </div>
            );
          })}
        </Section>
      </div>

      <div id="online-clicks" tabIndex={-1} className="scroll-mt-16 outline-none empty:hidden"><Heatmap variants={v} /></div>
    </>
  );
}

function Ads({ result, money, pct }: { result: OnlineRunResult; money: (x: number) => string; pct: (x: number) => string }) {
  const { t } = useI18n();
  const variants = result.variants;
  if (variants.every((s) => s.ads.length === 0)) return null;
  const signedMoney = (x: number) => `${x >= 0 ? "+" : "−"}${money(Math.abs(x))}`;
  return (
    <Section icon={Megaphone} title={t("onAds")} hint={t("onAdsHint")}>
      {variants.map((s) => s.ads.length > 0 && (
        <div key={s.site_id} className="space-y-1">
          {variants.length > 1 && <div className="text-xs font-medium">{s.site_name}</div>}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-xs">
              <thead><tr className="text-left text-muted-foreground">
                <th className="font-medium">{t("onAdName")}</th><th className="font-medium">{t("onAdImpressions")}</th>
                <th className="font-medium">{t("onAdReach")}</th><th className="font-medium">{t("onAdClicks")}</th>
                <th className="font-medium">{t("onAdCtr")}</th><th className="font-medium">{t("onAdClickConversions")}</th>
                <th className="font-medium">{t("onAdViewConversions")}</th><th className="font-medium">{t("onAdAttributed")}</th>
                <th className="font-medium">{t("onAdCost")}</th><th className="font-medium">{t("onAdRoas")}</th>
              </tr></thead>
              <tbody>
                {s.ads.map((ad) => (
                  <tr key={ad.ad_id} className="border-t align-top">
                    <td className="py-1 pr-2">
                      <div className="font-medium">{ad.name}</div>
                      <div className="text-muted-foreground">{t(AD_PLACEMENT_LABELS[ad.placement])} · {ad.product_name}</div>
                    </td>
                    <td className="tabular-nums">{ad.impressions}</td><td className="tabular-nums">{ad.reach}</td>
                    <td className="tabular-nums">{ad.clicks}</td><td className="tabular-nums">{pct(ad.ctr)}</td>
                    <td className="tabular-nums">{ad.click_conversions}</td><td className="tabular-nums">{ad.view_conversions}</td>
                    <td className="tabular-nums">{money(ad.attributed_revenue)}</td><td className="tabular-nums">{money(ad.cost)}</td>
                    <td className="tabular-nums">{ad.roas === null ? "—" : `${formatDecimal(ad.roas, 2)}×`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {result.comparisons.some((c) => c.ad_lifts.length > 0) && (
        <div className="space-y-2">
          <div>
            <div className="text-sm font-semibold">{t("onAdLift")}</div>
            <p className="text-xs text-muted-foreground">{t("onAdLiftHint")}</p>
          </div>
          {result.comparisons.map((c) => c.ad_lifts.map((lift) => (
            <div key={`${c.site_id}:${lift.ad_id}`} className="grid grid-cols-1 gap-2 rounded-xl border p-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
              <div className="sm:col-span-2 lg:col-span-4">
                <div className="font-medium">{lift.name}</div>
                <div className="text-muted-foreground">
                  {t("onAdLiftStores", lift.site_id === c.site_id
                    ? { withAd: c.site_name, withoutAd: result.variants[0]?.site_name ?? "" }
                    : { withAd: result.variants[0]?.site_name ?? "", withoutAd: c.site_name })}
                </div>
              </div>
              <Stat label={t("onAdUnitsDiff")} value={`${lift.units_diff >= 0 ? "+" : "−"}${Math.abs(lift.units_diff)}`} />
              <Stat label={t("onAdRevenueDiff")} value={signedMoney(lift.revenue_diff)} />
              <Stat label={t("onAdOtherDiff")} value={signedMoney(lift.other_revenue_diff)} />
              <Stat label={t("onAdIroas")} value={lift.iroas === null ? "—" : `${formatDecimal(lift.iroas, 2)}×`} />
              <div className="text-muted-foreground sm:col-span-2 lg:col-span-4">
                {t("onAdUnitsLine", { withoutAd: lift.units_without, withAd: lift.units_with })} · {t("onAdCost")}: {money(lift.cost)}
              </div>
            </div>
          )))}
        </div>
      )}
    </Section>
  );
}

// The interval narrows with the square root of the shoppers, so this many paired shoppers would make a difference of
// the size seen about as wide as the interval's half-width (a rough guide, not a power analysis).
const MAX_SHOPPERS = 500;

function Needed({ delta }: { delta: PairedDelta }) {
  const { t } = useI18n();
  if (delta.ci_low === null || delta.ci_high === null || delta.diff === 0 || delta.n < 2) return null;
  const half = (delta.ci_high - delta.ci_low) / 2;
  const needed = Math.max(Math.ceil(delta.n * (half / Math.abs(delta.diff)) ** 2), delta.n + 1);
  return (
    <div className="mt-1 text-[0.7rem] text-muted-foreground" title={t("onNeedHint")}>
      {needed > MAX_SHOPPERS ? t("onNeedMany", { max: MAX_SHOPPERS }) : t("onNeedShoppers", { count: needed })}
    </div>
  );
}

function Recovery({ variants, money, pct }: { variants: VariantSummary[]; money: (x: number) => string; pct: (x: number) => string }) {
  const { t } = useI18n();
  if (variants.every((s) => !s.recovery)) return null;
  return (
    <Section icon={MailCheck} title={t("onRecovery")} hint={t("onRecoveryHint")}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-xs">
          <thead><tr className="text-left text-muted-foreground">
            <th className="font-medium">{t("onRecoveryStore")}</th><th className="font-medium">{t("onRecoveryEmails")}</th>
            <th className="font-medium">{t("onRecoveryReturned")}</th><th className="font-medium">{t("onRecoveryRecovered")}</th>
            <th className="font-medium">{t("onRecoveryRevenue")}</th><th className="font-medium">{t("onRecoveryDiscount")}</th>
            <th className="font-medium">{t("onRecoveryPerEmail")}</th>
          </tr></thead>
          <tbody>
            {variants.map((s) => (
              <tr key={s.site_id} className="border-t">
                <td className="py-1 pr-2 font-medium">{s.site_name}</td>
                {s.recovery ? (
                  <>
                    <td className="tabular-nums">{s.recovery.emails}</td>
                    <td className="tabular-nums">{s.recovery.returned} · {pct(s.recovery.emails ? s.recovery.returned / s.recovery.emails : 0)}</td>
                    <td className="tabular-nums">{s.recovery.recovered} · {pct(s.recovery.emails ? s.recovery.recovered / s.recovery.emails : 0)}</td>
                    <td className="tabular-nums">{money(s.recovery.revenue)}</td>
                    <td className="tabular-nums">{money(s.recovery.discount)}</td>
                    <td className="tabular-nums">{money(s.recovery.emails ? Math.round(s.recovery.revenue / s.recovery.emails) : 0)}</td>
                  </>
                ) : <td colSpan={6} className="text-muted-foreground">{t("onRecoveryOff")}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function Rival({ result, money, pct }: { result: OnlineRunResult; money: (x: number) => string; pct: (x: number) => string }) {
  const { t } = useI18n();
  if (!result.rival_name) return null;
  return (
    <Section icon={Swords} title={t("onRival", { rival: result.rival_name })} hint={t("onRivalHint")}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-xs">
          <thead><tr className="text-left text-muted-foreground">
            <th className="font-medium">{t("onRecoveryStore")}</th><th className="font-medium">{t("onRivalLeft")}</th>
            <th className="font-medium">{t("onRivalWent")}</th><th className="font-medium">{t("onRivalBought")}</th>
            <th className="font-medium">{t("onRivalRevenue")}</th>
          </tr></thead>
          <tbody>
            {result.variants.map((s) => s.rival && (
              <tr key={s.site_id} className="border-t">
                <td className="py-1 pr-2 font-medium">{s.site_name}</td>
                <td className="tabular-nums">{s.rival.left} · {pct(s.sessions ? s.rival.left / s.sessions : 0)}</td>
                <td className="tabular-nums">{s.rival.went} · {pct(s.rival.left ? s.rival.went / s.rival.left : 0)}</td>
                <td className="tabular-nums">{s.rival.bought} · {pct(s.rival.went ? s.rival.bought / s.rival.went : 0)}</td>
                <td className="tabular-nums">{money(s.rival.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function Frictions({ variants, money, pct }: { variants: VariantSummary[]; money: (x: number) => string; pct: (x: number) => string }) {
  const { t } = useI18n();
  const codes = [...new Set(variants.flatMap((s) => s.frictions.map((f) => f.code)))];
  return (
    <Section icon={TriangleAlert} title={t("onFrictions")} hint={t("onFrictionsHint")}>
      {codes.length === 0 ? <p className="text-xs text-muted-foreground">{t("onFrictionsNone")}</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-xs">
            <thead><tr className="text-left text-muted-foreground">
              <th className="font-medium" />
              {variants.map((s) => <th key={s.site_id} className="font-medium">{s.site_name}</th>)}
            </tr></thead>
            <tbody>
              {codes.map((code) => (
                <tr key={code} className="border-t">
                  <td className={cn("py-1 pr-2", FRICTION_HARMS.has(code) && "font-medium text-destructive")}>{t(FRICTION_LABELS[code])}</td>
                  {variants.map((s) => {
                    const row = s.frictions.find((f) => f.code === code);
                    return (
                      <td key={s.site_id} className="py-1 pr-2 tabular-nums">
                        {row ? `${row.sessions} · ${pct(row.share)}${row.amount ? ` · ${money(row.amount)}` : ""}` : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function Surveys({ variants, pct }: { variants: VariantSummary[]; pct: (x: number) => string }) {
  const { t } = useI18n();
  if (variants.every((s) => !s.survey)) return null;
  return (
    <Section icon={ClipboardList} title={t("onSurveys")} hint={t("onSurveysHint")}>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {variants.map((s) => s.survey && (
          <div key={s.site_id} className="space-y-2 rounded-xl border p-3 text-xs">
            {variants.length > 1 && <div className="font-medium">{s.site_name}</div>}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label={t("onSurveySatisfaction")} value={`${formatDecimal(s.survey.satisfaction, 1)} / 7`} />
              <Stat label={t("onSurveyEase")} value={`${formatDecimal(s.survey.ease, 1)} / 7`} />
              <Stat label={t("onSurveyNps")} value={`${s.survey.nps >= 0 ? "+" : ""}${formatDecimal(s.survey.nps, 0)}`} />
              <Stat label={t("onSurveyReturn")} value={pct(s.survey.would_return)} />
            </div>
            <div className="text-muted-foreground">{t("onSurveyResponses", { count: s.survey.responses })}</div>
            {s.survey.frustrations.length > 0 && (
              <div><div className="font-medium">{t("onSurveyFrustrations")}</div>
                <ul className="list-disc pl-4">{s.survey.frustrations.map((f) => <li key={f}>{f}</li>)}</ul></div>
            )}
            {s.survey.improvements.length > 0 && (
              <div><div className="font-medium">{t("onSurveyImprovements")}</div>
                <ul className="list-disc pl-4">{s.survey.improvements.map((f) => <li key={f}>{f}</li>)}</ul></div>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border px-2 py-1.5">
      <div className="text-muted-foreground">{label}</div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Segments({ result, money, pct }: { result: OnlineRunResult; money: (x: number) => string; pct: (x: number) => string }) {
  const { t } = useI18n();
  const [dimension, setDimension] = useState<SegmentRow["dimension"]>("mission");
  const label = (value: string) => segmentValueLabel(dimension, value, t);
  const values = [...new Set(result.variants.flatMap((s) => s.segments.filter((r) => r.dimension === dimension).map((r) => r.value)))];
  const cells: HeatCell[][] = values.map((value) => result.variants.map((s) => {
    const row = s.segments.find((r) => r.dimension === dimension && r.value === value);
    return row ? {
      value: row.conversion, label: pct(row.conversion), sub: `${row.sessions} · ${money(row.revenue_per_session)}`,
      title: t("onSegmentCell", { sessions: row.sessions, conversion: pct(row.conversion), revenue: money(row.revenue_per_session),
        bounce: row.bounce_rate == null ? "—" : pct(row.bounce_rate) }),
    } : { value: null, label: "—", sub: "", title: "" };
  }));
  return (
    <Section icon={Grid3x3} title={t("onSegments")} hint={t("onSegmentsHint")}>
      <div className="inline-flex flex-wrap rounded-md border p-0.5 text-xs" role="group" aria-label={t("onSegments")}>
        {DIMENSIONS.map((d) => (
          <button key={d.id} type="button" aria-pressed={dimension === d.id} onClick={() => setDimension(d.id)}
            className={cn("rounded px-2 py-0.5", dimension === d.id ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>{t(d.label)}</button>
        ))}
      </div>
      <SegmentHeat rows={values.map(label)} columns={result.variants.map((s) => s.site_name)} cells={cells} />
    </Section>
  );
}

function Heatmap({ variants }: { variants: VariantSummary[] }) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  const [device, setDevice] = useState<Device>("desktop");
  const clicks = variants[index]?.clicks ?? [];
  const pages = [...new Set(clicks.filter((c) => c.device === device).map((c) => c.page))];
  const [page, setPage] = useState<PageKind | null>(null);
  const current = page && pages.includes(page) ? page : pages[0] ?? null;
  const shown: ClickPoint[] = clicks.filter((c) => c.device === device && c.page === current);
  if (variants.every((s) => s.clicks.length === 0)) {
    return <Section icon={MousePointerClick} title={t("onHeatmap")}><p className="text-xs text-muted-foreground">{t("onHeatmapNone")}</p></Section>;
  }
  return (
    <Section icon={MousePointerClick} title={t("onHeatmap")} hint={t("onHeatmapHint")}>
      <div className="flex flex-wrap gap-2 text-xs">
        {variants.length > 1 && (
          <select className="h-8 rounded-md border bg-background px-2" value={index} onChange={(e) => setIndex(Number(e.target.value))} aria-label={t("onRunStores")}>
            {variants.map((s, i) => <option key={s.site_id} value={i}>{s.site_name}</option>)}
          </select>
        )}
        <select className="h-8 rounded-md border bg-background px-2" value={device} onChange={(e) => setDevice(e.target.value as Device)} aria-label={t("onDevice")}>
          <option value="desktop">{t("onDeviceDesktop")}</option><option value="mobile">{t("onDeviceMobile")}</option>
        </select>
        <select className="h-8 rounded-md border bg-background px-2" value={current ?? ""} onChange={(e) => setPage(e.target.value as PageKind)} aria-label={t("onHeatmapPage")}>
          {pages.map((p) => <option key={p} value={p}>{t(PAGE_LABELS[p])}</option>)}
        </select>
      </div>
      <div className={cn("relative mx-auto w-full overflow-hidden rounded-xl border bg-[repeating-linear-gradient(0deg,transparent,transparent_39px,var(--border)_40px)]", device === "mobile" ? "aspect-[430/1600] max-w-[260px]" : "aspect-[1024/1300] max-w-[520px]")}
        role="img" aria-label={t("onHeatmapAlt", { count: shown.length })}>
        {shown.map((c, i) => (
          <span key={i} className="absolute size-5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-rose-500/30 blur-[2px]" style={{ left: `${c.x * 100}%`, top: `${c.y * 100}%` }} />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{t("onHeatmapCount", { count: shown.length })}</p>
    </Section>
  );
}

// The report's table of contents: the section being read is highlighted and kept in view, and a fade at either end
// shows that more sections are hidden off the strip.
function SectionNav({ label, sections }: { label: string; sections: { id: string; label: string }[] }) {
  const strip = useRef<HTMLElement>(null);
  const [active, setActive] = useState<string | null>(null);
  const [more, setMore] = useState({ left: false, right: false });
  // After a click the highlight stays on the chosen section while the page scrolls past the ones before it.
  const jumpUntil = useRef(0);
  const ids = sections.map((x) => x.id).join(" ");
  useEffect(() => {
    const el = strip.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const order = ids.split(" ");
    const showing = new Set<string>();
    // A section is being read while it crosses a reading line a third of the way down the screen.
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) showing.add(e.target.id);
        else showing.delete(e.target.id);
      }
      const first = order.find((id) => showing.has(id));
      if (first && Date.now() > jumpUntil.current) setActive(first);
    }, { rootMargin: "-30% 0px -65% 0px" });
    for (const id of order) {
      const section = document.getElementById(id);
      if (section) io.observe(section);
    }
    const measure = () => setMore({ left: el.scrollLeft > 4, right: el.scrollLeft + el.clientWidth < el.scrollWidth - 4 });
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    ro?.observe(el);
    el.addEventListener("scroll", measure, { passive: true });
    return () => { io.disconnect(); ro?.disconnect(); el.removeEventListener("scroll", measure); };
  }, [ids]);
  useEffect(() => {
    const el = strip.current;
    const chip = el?.querySelector<HTMLElement>(`[data-section="${active}"]`);
    if (el && chip && (chip.offsetLeft < el.scrollLeft || chip.offsetLeft + chip.offsetWidth > el.scrollLeft + el.clientWidth)) {
      el.scrollTo?.({ left: chip.offsetLeft - el.clientWidth / 3, behavior: "smooth" });
    }
  }, [active]);
  const fade = more.left && more.right ? "[mask-image:linear-gradient(90deg,transparent,#000_2.5rem,#000_calc(100%-2.5rem),transparent)]"
    : more.right ? "[mask-image:linear-gradient(90deg,#000_calc(100%-2.5rem),transparent)]"
    : more.left ? "[mask-image:linear-gradient(90deg,transparent,#000_2.5rem)]" : "";
  return (
    <div className="sticky top-0 z-20 rounded-2xl border bg-background/80 shadow-sm backdrop-blur-xl">
      <nav ref={strip} aria-label={label} className={cn("relative flex gap-1 overflow-x-auto p-1 text-xs [scrollbar-width:none]", fade)}>
        {sections.map((x) => (
          <a key={x.id} href={`#${x.id}`} data-section={x.id} aria-current={active === x.id ? "location" : undefined}
            onClick={(e) => { e.preventDefault(); setActive(x.id); jumpUntil.current = Date.now() + 1200; jumpTo(x.id); }}
            className={cn("shrink-0 rounded-xl px-3 py-1.5 whitespace-nowrap transition-colors",
              active === x.id ? "bg-foreground font-medium text-background shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>{x.label}</a>
        ))}
      </nav>
    </div>
  );
}

// Like following an in-page link: bring the section into view and let the next Tab continue inside it.
function jumpTo(id: string) {
  const section = document.getElementById(id);
  section?.scrollIntoView({ behavior: "smooth", block: "start" });
  section?.focus({ preventScroll: true });
}

function Section({ id, icon: Icon, title, hint, children }: { id?: string; icon?: LucideIcon; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section id={id} tabIndex={id ? -1 : undefined} className="reveal panel flex min-w-0 scroll-mt-16 flex-col gap-3 rounded-[1.6rem] p-4 text-sm outline-none sm:p-5">
      <div className="flex items-start gap-3">
        {Icon && (
          <span className="grid size-9 shrink-0 place-items-center rounded-xl heat-gradient text-white dark:text-neutral-950 shadow-[0_8px_24px_-8px_var(--heat-2)]" aria-hidden>
            <Icon className="size-4.5" />
          </span>
        )}
        <div className="min-w-0">
          <h3 className="font-display text-lg leading-tight tracking-[-0.02em]">{title}</h3>
          {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}
