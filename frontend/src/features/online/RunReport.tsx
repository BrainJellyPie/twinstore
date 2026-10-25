// What virtual shoppers did on the stores of a run: conversion and money per variant, paired differences with
// intervals, the funnel, where they left, segments, what they searched and bought, where they clicked, and every
// shopper's visit.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2 } from "lucide-react";

import {
  clickstreamUrl, deleteRun, getRun, onlineKeys,
  type ClickPoint, type Device, type OnlineRunResult, type PageKind, type SegmentRow, type SessionOutcome, type VariantSummary,
} from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { currencyCode, formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { personaLabel } from "@/shared/i18n/personaLabels";

import { JourneyViewer } from "./JourneyViewer";
import {
  DELTA_LABELS, DEVICE_LABELS, FUNNEL_LABELS, MISSION_LABELS, OUTCOME_COLORS, OUTCOME_LABELS, PAGE_LABELS, POLICY_LABELS,
} from "./labels";

const DIMENSIONS: { id: SegmentRow["dimension"]; label: MessageKey }[] = [
  { id: "mission", label: "onSegMission" }, { id: "device", label: "onSegDevice" },
  { id: "age_group", label: "onSegAge" }, { id: "gender", label: "onSegGender" },
];
const SESSION_ROWS = 80;

export function RunReport({ projectId, runId, onDeleted }: { projectId: string; runId: string; onDeleted: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const run = useQuery({
    queryKey: onlineKeys.run(projectId, runId),
    queryFn: ({ signal }) => getRun(projectId, runId, signal),
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status.status) ? false : 1500),
  });
  const remove = useMutation({
    mutationFn: () => deleteRun(projectId, runId),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: onlineKeys.runs(projectId) }); onDeleted(); },
  });
  if (run.isPending) return <div className="panel rounded-[1.6rem] p-4 text-sm text-muted-foreground">{t("studioLoading")}</div>;
  if (run.isError) return <div role="alert" className="panel rounded-[1.6rem] p-4 text-sm text-destructive">{run.error.message}</div>;
  const { status, result } = run.data;
  const running = status.status === "pending" || status.status === "running";

  return (
    <div className="flex flex-col gap-3">
      <section className="panel flex flex-wrap items-start gap-3 rounded-[1.4rem] p-4 text-sm">
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-xl">{status.name || status.site_names.join(" vs ")}</h2>
          <p className="text-xs text-muted-foreground">
            {t(POLICY_LABELS[status.request.policy])}{result?.model ? ` · ${result.model}` : ""}
            {" · "}{t("onRunSummary", { shoppers: status.request.shoppers, stores: status.site_ids.length })}
            {result ? ` · ${t("onRunTook", { seconds: Math.round(result.seconds) })}` : ""}
          </p>
        </div>
        {status.status === "completed" && (
          <a className="inline-flex h-8 items-center gap-1.5 rounded-[0.7rem] border px-3 text-xs hover:bg-muted" href={clickstreamUrl(projectId, runId)} download>
            <Download className="size-3.5" aria-hidden /> {t("onDownloadClicks")}
          </a>
        )}
        {!running && (
          <Button variant="ghost" size="sm" onClick={() => remove.mutate()} disabled={remove.isPending}>
            <Trash2 aria-hidden /> {t("studioDelete")}
          </Button>
        )}
        {remove.error && <p role="alert" className="w-full text-xs text-destructive">{remove.error.message}</p>}
      </section>

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
      {result && <Report projectId={projectId} result={result} />}
    </div>
  );
}

function Report({ projectId, result }: { projectId: string; result: OnlineRunResult }) {
  const { t } = useI18n();
  const [journey, setJourney] = useState<{ variant: number; shopper: string } | null>(null);
  const code = currencyCode(result.currency);
  const money = (x: number) => formatMoney(Math.round(x), code);
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
  const v = result.variants;
  const rows: { label: MessageKey; value: (s: VariantSummary) => string }[] = [
    { label: "onKpiSessions", value: (s) => String(s.sessions) },
    { label: "onKpiConversion", value: (s) => pct(s.conversion) },
    { label: "onKpiRevenuePerSession", value: (s) => money(s.revenue_per_session) },
    { label: "onKpiAov", value: (s) => (s.purchases ? money(s.aov) : "—") },
    { label: "onKpiRevenue", value: (s) => money(s.revenue) },
    { label: "onKpiAddToCart", value: (s) => pct(s.add_to_cart_rate) },
    { label: "onKpiAbandonment", value: (s) => pct(s.cart_abandonment) },
    { label: "onKpiBounce", value: (s) => pct(s.bounce_rate) },
    { label: "onKpiSteps", value: (s) => s.avg_steps.toFixed(1) },
    { label: "onKpiSeconds", value: (s) => t("onSecondsShort", { seconds: Math.round(s.avg_seconds) }) },
    { label: "onKpiSearchShare", value: (s) => pct(s.search_share) },
    { label: "onKpiZeroResults", value: (s) => String(s.zero_result_searches) },
  ];

  return (
    <>
      {result.notes.length > 0 && (
        <ul className="panel list-disc space-y-0.5 rounded-[1.4rem] py-3 pr-4 pl-8 text-xs text-muted-foreground">
          {result.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}
      <Section title={t("onKpis")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead><tr className="text-left text-xs text-muted-foreground">
              <th className="py-1 pr-3 font-medium" />
              {v.map((s, i) => <th key={s.site_id} className="py-1 pr-3 font-medium">{s.site_name}{v.length > 1 && <span className="ml-1 rounded bg-muted px-1 text-[0.65rem]">{i === 0 ? t("onControl") : t("onVariantLetter", { letter: String.fromCharCode(65 + i) })}</span>}</th>)}
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
      </Section>

      {result.comparisons.length > 0 && (
        <Section title={t("onCompareTitle")} hint={t("onCompareHint")}>
          {result.comparisons.map((c) => (
            <div key={c.site_id} className="space-y-1">
              <div className="text-xs font-medium">{t("onCompareVs", { variant: c.site_name, control: v[0]?.site_name ?? "" })}</div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                {c.deltas.map((d) => {
                  const isMoney = d.metric === "revenue_per_session";
                  const isRate = d.metric === "conversion" || d.metric === "add_to_cart_rate";
                  const show = (x: number) => (isMoney ? money(x) : isRate ? `${(x * 100).toFixed(1)}` : x.toFixed(1));
                  const signed = (x: number) => `${x >= 0 ? "+" : "−"}${show(Math.abs(x))}${isRate ? t("onPointsSuffix") : ""}`;
                  const clear = d.ci_low !== null && d.ci_high !== null && (d.ci_low > 0 || d.ci_high < 0);
                  const good = d.metric === "seconds" || d.metric === "steps" ? null : d.diff > 0;
                  return (
                    <div key={d.metric} className={cn("rounded-xl border p-2 text-xs", clear && good === true && "tone-good", clear && good === false && "tone-bad")}>
                      <div className="text-muted-foreground">{t(DELTA_LABELS[d.metric])}</div>
                      <div className="text-base font-semibold tabular-nums">{signed(d.diff)}</div>
                      <div className="text-muted-foreground tabular-nums">
                        {d.ci_low !== null && d.ci_high !== null ? t("studioCi95", { low: signed(d.ci_low), high: signed(d.ci_high) }) : "—"}
                      </div>
                      <div className="text-muted-foreground">{clear ? t("onClearDiff") : t("onNoClearDiff")}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </Section>
      )}

      <div className="grid gap-3 xl:grid-cols-2">
        <Section title={t("onFunnel")}>
          {v.map((s) => (
            <div key={s.site_id} className="space-y-1">
              {v.length > 1 && <div className="text-xs font-medium">{s.site_name}</div>}
              {s.funnel.map((f) => (
                <div key={f.stage} className="grid grid-cols-[110px_minmax(0,1fr)_70px] items-center gap-2 text-xs">
                  <span className="text-muted-foreground">{t(FUNNEL_LABELS[f.stage])}</span>
                  <span className="h-3 rounded-full bg-muted"><span className="block h-3 rounded-full bg-primary" style={{ width: `${f.share * 100}%` }} /></span>
                  <span className="text-right tabular-nums">{f.sessions} · {pct(f.share)}</span>
                </div>
              ))}
            </div>
          ))}
        </Section>
        <Section title={t("onOutcomes")}>
          {v.map((s) => (
            <div key={s.site_id} className="space-y-1">
              {v.length > 1 && <div className="text-xs font-medium">{s.site_name}</div>}
              <div className="flex h-4 overflow-hidden rounded-full" role="img" aria-label={t("onOutcomes")}>
                {(Object.entries(s.outcomes) as [SessionOutcome, number][]).map(([o, n]) => (
                  <span key={o} className={OUTCOME_COLORS[o]} style={{ width: `${(n / s.sessions) * 100}%` }} title={`${t(OUTCOME_LABELS[o])}: ${n}`} />
                ))}
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
                {(Object.entries(s.outcomes) as [SessionOutcome, number][]).map(([o, n]) => (
                  <span key={o} className="flex items-center gap-1"><span className={cn("size-2 rounded-full", OUTCOME_COLORS[o])} />{t(OUTCOME_LABELS[o])}: {n}</span>
                ))}
              </div>
              <div className="pt-1 text-xs text-muted-foreground">{t("onExits")}: {s.exits.slice(0, 5).map((e) => `${t(PAGE_LABELS[e.page])} (${e.sessions})`).join(", ") || "—"}</div>
            </div>
          ))}
        </Section>
      </div>

      <Segments result={result} money={money} pct={pct} />

      <div className="grid gap-3 xl:grid-cols-2">
        <Section title={t("onSearches")} hint={t("onSearchesHint")}>
          {v.map((s) => (
            <div key={s.site_id}>
              {v.length > 1 && <div className="text-xs font-medium">{s.site_name}</div>}
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
        <Section title={t("onTopProducts")}>
          {v.map((s) => (
            <div key={s.site_id}>
              {v.length > 1 && <div className="text-xs font-medium">{s.site_name}</div>}
              <table className="w-full text-xs">
                <thead><tr className="text-left text-muted-foreground"><th className="font-medium">{t("onColProduct")}</th><th className="font-medium">{t("onColViews")}</th><th className="font-medium">{t("onColAdds")}</th><th className="font-medium">{t("onColUnits")}</th><th className="font-medium">{t("onKpiRevenue")}</th></tr></thead>
                <tbody>{s.products.slice(0, 10).map((p) => (
                  <tr key={p.product_id} className="border-t">
                    <td className="max-w-[14rem] truncate py-0.5 pr-2" title={p.name}>{p.name}</td>
                    <td className="tabular-nums">{p.views}</td><td className="tabular-nums">{p.adds}</td>
                    <td className="tabular-nums">{p.units}</td><td className="tabular-nums">{money(p.revenue)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ))}
        </Section>
      </div>

      <Heatmap variants={v} />

      <Section title={t("onSessions")} hint={t("onSessionsHint")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-xs">
            <thead><tr className="text-left text-muted-foreground">
              <th className="font-medium">{t("onColShopper")}</th><th className="font-medium">{t("onSegMission")}</th><th className="font-medium">{t("onSegDevice")}</th>
              {v.map((s) => <th key={s.site_id} className="font-medium">{s.site_name}</th>)}
            </tr></thead>
            <tbody>
              {result.shoppers.slice(0, SESSION_ROWS).map((sh) => (
                <tr key={sh.id} className="border-t align-top">
                  <td className="py-1 pr-2">
                    <div className="font-medium">{sh.identity}</div>
                    <div className="text-muted-foreground">{personaLabel(sh.age_group, t)} · {personaLabel(sh.gender, t)}</div>
                  </td>
                  <td className="py-1 pr-2">{t(MISSION_LABELS[sh.mission])}</td>
                  <td className="py-1 pr-2">{t(DEVICE_LABELS[sh.device])}</td>
                  {v.map((s, i) => (
                    <td key={s.site_id} className="py-1 pr-2">
                      <button type="button" className="rounded-md border px-2 py-0.5 hover:bg-muted" onClick={() => setJourney({ variant: i, shopper: sh.id })}>
                        {t("onOpenJourney")}
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {result.shoppers.length > SESSION_ROWS && <p className="text-xs text-muted-foreground">{t("onSessionsMore", { count: result.shoppers.length - SESSION_ROWS })}</p>}
      </Section>
      {journey && (
        <JourneyViewer projectId={projectId} runId={result.run_id} variant={journey.variant} shopperId={journey.shopper}
          variants={v.map((s) => s.site_name)} currency={result.currency}
          onVariant={(variant) => setJourney({ ...journey, variant })} onClose={() => setJourney(null)} />
      )}
    </>
  );
}

function Segments({ result, money, pct }: { result: OnlineRunResult; money: (x: number) => string; pct: (x: number) => string }) {
  const { t } = useI18n();
  const [dimension, setDimension] = useState<SegmentRow["dimension"]>("mission");
  const label = (value: string) => {
    if (dimension === "mission" && value in MISSION_LABELS) return t(MISSION_LABELS[value as keyof typeof MISSION_LABELS]);
    if (dimension === "device" && value in DEVICE_LABELS) return t(DEVICE_LABELS[value as Device]);
    return personaLabel(value, t);
  };
  const values = [...new Set(result.variants.flatMap((s) => s.segments.filter((r) => r.dimension === dimension).map((r) => r.value)))];
  return (
    <Section title={t("onSegments")}>
      <div className="inline-flex flex-wrap rounded-md border p-0.5 text-xs" role="group" aria-label={t("onSegments")}>
        {DIMENSIONS.map((d) => (
          <button key={d.id} type="button" aria-pressed={dimension === d.id} onClick={() => setDimension(d.id)}
            className={cn("rounded px-2 py-0.5", dimension === d.id ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>{t(d.label)}</button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-xs">
          <thead><tr className="text-left text-muted-foreground">
            <th className="font-medium" />
            {result.variants.map((s) => <th key={s.site_id} className="font-medium">{s.site_name}</th>)}
          </tr></thead>
          <tbody>
            {values.map((value) => (
              <tr key={value} className="border-t">
                <td className="py-1 pr-2">{label(value)}</td>
                {result.variants.map((s) => {
                  const row = s.segments.find((r) => r.dimension === dimension && r.value === value);
                  return (
                    <td key={s.site_id} className="py-1 pr-2 tabular-nums">
                      {row ? t("onSegmentCell", { sessions: row.sessions, conversion: pct(row.conversion), revenue: money(row.revenue_per_session) }) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
    return <Section title={t("onHeatmap")}><p className="text-xs text-muted-foreground">{t("onHeatmapNone")}</p></Section>;
  }
  return (
    <Section title={t("onHeatmap")} hint={t("onHeatmapHint")}>
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

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="panel flex min-w-0 flex-col gap-3 rounded-[1.4rem] p-4 text-sm">
      <div>
        <h3 className="font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  );
}
