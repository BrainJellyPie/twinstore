// The top of a run report: a dark stage with the run's verdict, every store's conversion as a glowing ring that fills
// as the numbers count up, and the shopper replay one click away.

import type { Ref } from "react";
import { ArrowDownRight, ArrowUpRight, Columns2, Download, FileText, Maximize2, Minimize2, Minus, Play, Scale, Trash2, Trophy, Users } from "lucide-react";

import type { OnlineRunResult, OnlineRunStatus } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { currencyCode, formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";

import { useCountUp } from "./useCountUp";
import { POLICY_LABELS, storeColor } from "./labels";

type Verdict =
  | { kind: "win"; index: number; diff: number }
  | { kind: "holds" }
  | { kind: "close" }
  | { kind: "single" };

/** A variant that clearly converts better wins (the largest gain); control holds if every variant is clearly worse. */
function verdict(result: OnlineRunResult): Verdict {
  if (result.comparisons.length === 0) return { kind: "single" };
  const clear = result.comparisons.map((c, i) => {
    const d = c.deltas.find((x) => x.metric === "conversion");
    const sure = d && d.ci_low !== null && d.ci_high !== null && (d.ci_low > 0 || d.ci_high < 0);
    return { index: i + 1, diff: d?.diff ?? 0, sure: !!sure };
  });
  const wins = clear.filter((c) => c.sure && c.diff > 0).sort((a, b) => b.diff - a.diff);
  if (wins[0]) return { kind: "win", index: wins[0].index, diff: wins[0].diff };
  if (clear.every((c) => c.sure && c.diff < 0)) return { kind: "holds" };
  return { kind: "close" };
}

export function RunHero({ status, result, heroRef, wide, onWide, onWatch, onCompare, csvUrl, reportUrl, onDelete, deleting, deleteError }: {
  status: OnlineRunStatus;
  result: OnlineRunResult | null;
  heroRef?: Ref<HTMLElement>;
  wide: boolean;
  onWide: () => void;
  onWatch: (() => void) | null;
  onCompare: (() => void) | null;
  csvUrl: string | null;
  /** The run's print-ready page to share. */
  reportUrl: string | null;
  onDelete: (() => void) | null;
  deleting: boolean;
  deleteError: string;
}) {
  const { t } = useI18n();
  const running = status.status === "pending" || status.status === "running";
  const v = result?.variants ?? [];
  const call = result ? verdict(result) : null;
  const points = (x: number) => `${x >= 0 ? "+" : "−"}${(Math.abs(x) * 100).toFixed(1)}${t("onPointsSuffix")}`;
  const chip = "rounded-full border border-white/15 bg-white/8 px-2.5 py-0.5 text-white/85 backdrop-blur";

  return (
    // Always the night palette: the stage is dark in both themes, so its tokens come from `.dark`.
    <section ref={heroRef} className="dark relative isolate overflow-hidden rounded-[2rem] bg-[#06070c] p-5 text-white shadow-[0_40px_120px_-40px_rgb(40_20_110/0.85)] sm:p-7">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
        <div className="absolute -top-1/2 -left-1/4 size-[38rem] rounded-full bg-heat-1/25 blur-[110px] animate-aurora" />
        <div className="absolute -right-1/4 -bottom-2/3 size-[44rem] rounded-full bg-heat-2/35 blur-[120px] animate-aurora-slow" />
        <div className="absolute top-1/4 left-1/2 size-[26rem] rounded-full bg-heat-3/20 blur-[100px] animate-aurora" />
        <div className="absolute inset-0 bg-[radial-gradient(rgb(255_255_255/0.08)_1px,transparent_1px)] [background-size:22px_22px] [mask-image:radial-gradient(ellipse_at_40%_40%,black,transparent_75%)]" />
      </div>

      <div className="flex flex-wrap items-start gap-3">
        {/* On a phone the title takes the whole row and the actions sit under it. */}
        <div className="min-w-0 flex-1 basis-full sm:basis-0">
          <div className="flex items-center gap-2 font-mono text-[0.7rem] tracking-[0.2em] text-white/60 uppercase">
            <span className={cn("size-2 rounded-full", running ? "animate-pulse-ring bg-volt" : status.status === "failed" ? "bg-negative" : "bg-positive shadow-[0_0_12px_var(--positive)]")} aria-hidden />
            {t("onHeroEyebrow")}
          </div>
          <h2 className="mt-2 bg-gradient-to-r from-white via-white to-white/60 bg-clip-text font-display text-[clamp(1.75rem,4vw,3.4rem)] leading-[1.02] tracking-[-0.035em] text-transparent">
            {status.name || status.site_names.join(" vs ")}
          </h2>
          <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
            <span className={chip}>{t(POLICY_LABELS[status.request.policy])}{result?.model ? ` · ${result.model}` : ""}</span>
            <span className={chip}>{t("onRunSummary", { shoppers: status.request.shoppers, stores: status.site_ids.length })}</span>
            {result && <span className={chip}>{t("onRunTook", { seconds: Math.round(result.seconds) })}</span>}
            {result?.rival_name && <span className={chip}>{t("onRivalTab", { rival: result.rival_name })}</span>}
          </div>
        </div>
        <div className="-ml-2.5 flex items-center gap-1 sm:ml-0">
          <Button variant="ghost" size="icon" className="size-10 rounded-2xl text-white/80 hover:bg-white/10 hover:text-white" onClick={onWide}
            aria-pressed={wide} aria-label={wide ? t("onWideOff") : t("onWideOn")} title={wide ? t("onWideOff") : t("onWideOn")}>
            {wide ? <Minimize2 aria-hidden /> : <Maximize2 aria-hidden />}
          </Button>
          {reportUrl && (
            <a href={reportUrl} target="_blank" rel="noopener" aria-label={t("onOpenReport")} title={t("onOpenReport")}
              className="grid size-10 place-items-center rounded-2xl text-white/80 transition-colors hover:bg-white/10 hover:text-white">
              <FileText className="size-4" aria-hidden />
            </a>
          )}
          {csvUrl && (
            <a href={csvUrl} download aria-label={t("onDownloadClicks")} title={t("onDownloadClicks")}
              className="grid size-10 place-items-center rounded-2xl text-white/80 transition-colors hover:bg-white/10 hover:text-white">
              <Download className="size-4" aria-hidden />
            </a>
          )}
          {onDelete && (
            <Button variant="ghost" size="icon" className="size-10 rounded-2xl text-white/80 hover:bg-white/10 hover:text-white" onClick={onDelete}
              disabled={deleting} aria-label={t("studioDelete")} title={t("studioDelete")}>
              <Trash2 aria-hidden />
            </Button>
          )}
        </div>
        {deleteError && <p role="alert" className="w-full text-xs text-negative">{deleteError}</p>}
      </div>

      {result && call && (
        <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-4">
          <Verdict call={call} result={result} points={points} />
          <div className="flex flex-wrap items-center gap-2">
            {onWatch && (
              <button type="button" onClick={onWatch} title={t("onWatchShopperHint")}
                className="group relative inline-flex h-12 items-center gap-2.5 overflow-hidden rounded-2xl bg-white px-5 text-sm font-semibold text-neutral-950 shadow-[0_0_0_1px_rgb(255_255_255/0.4),0_12px_40px_-8px_var(--heat-1)] transition-transform hover:scale-[1.03] active:scale-[0.98]">
                <span className="absolute inset-0 -z-0 bg-[linear-gradient(110deg,transparent_30%,rgb(255_255_255/0.0)_40%,color-mix(in_oklab,var(--heat-1)_35%,transparent)_50%,transparent_60%)] bg-[length:250%_100%] animate-shimmer" aria-hidden />
                <span className="relative grid size-7 place-items-center rounded-full heat-gradient text-white shadow-[0_0_18px_var(--heat-2)]"><Play className="size-3.5 fill-current" aria-hidden /></span>
                <span className="relative">{t("onWatchShopperCta")}</span>
              </button>
            )}
            {onCompare && (
              <button type="button" onClick={onCompare}
                className="inline-flex h-12 items-center gap-2 rounded-2xl border border-white/20 bg-white/8 px-4 text-sm font-medium text-white backdrop-blur transition-colors hover:bg-white/15">
                <Columns2 className="size-4" aria-hidden /> {t("onSideBySide")}
              </button>
            )}
          </div>
        </div>
      )}

      {result && v.length > 0 && (
        <div className={cn("mt-6 grid gap-3", v.length === 1 ? "sm:grid-cols-[minmax(0,22rem)]" : v.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 xl:grid-cols-4")}>
          {v.map((s, i) => {
            const d = i > 0 ? result.comparisons[i - 1]?.deltas.find((x) => x.metric === "conversion") : undefined;
            const sure = d && d.ci_low !== null && d.ci_high !== null && (d.ci_low > 0 || d.ci_high < 0);
            return (
              <StoreRing key={s.site_id} index={i} name={s.site_name} conversion={s.conversion} revenue={s.revenue} orders={s.purchases}
                visits={s.sessions} currency={result.currency} winner={call?.kind === "win" ? call.index === i : call?.kind === "holds" && i === 0}
                delta={d ? { text: points(d.diff), sure: !!sure, up: d.diff > 0 } : null} />
            );
          })}
        </div>
      )}
    </section>
  );
}

function Verdict({ call, result, points }: { call: Verdict; result: OnlineRunResult; points: (x: number) => string }) {
  const { t } = useI18n();
  const v = result.variants;
  const icon = call.kind === "win" || call.kind === "holds" ? Trophy : call.kind === "close" ? Scale : Users;
  const Icon = icon;
  const text = call.kind === "win" ? t("onVerdictWins", { store: v[call.index]?.site_name ?? "", diff: points(call.diff) })
    : call.kind === "holds" ? t("onVerdictHolds", { store: v[0]?.site_name ?? "" })
    : call.kind === "close" ? t("onVerdictClose")
    : t("onVerdictSingle", { orders: v[0]?.purchases ?? 0, visits: v[0]?.sessions ?? 0 });
  return (
    <div className="flex min-w-0 flex-1 basis-[22rem] items-center gap-3">
      <span className={cn("grid size-12 shrink-0 place-items-center rounded-2xl shadow-lg",
        call.kind === "win" || call.kind === "holds" ? "bg-gradient-to-br from-amber-300 to-amber-500 text-neutral-950 shadow-amber-500/30" : "heat-gradient text-white")} aria-hidden>
        <Icon className="size-6" />
      </span>
      <p className="min-w-0 text-[clamp(1.05rem,1.8vw,1.45rem)] font-semibold leading-snug tracking-[-0.015em]">{text}</p>
    </div>
  );
}

function StoreRing({ index, name, conversion, revenue, orders, visits, currency, winner, delta }: {
  index: number; name: string; conversion: number; revenue: number; orders: number; visits: number; currency: string;
  winner: boolean; delta: { text: string; sure: boolean; up: boolean } | null;
}) {
  const { t } = useI18n();
  const shown = useCountUp(conversion, 1400);
  const money = useCountUp(revenue, 1600);
  const r = 46;
  const around = 2 * Math.PI * r;
  const color = storeColor(index);
  const Arrow = !delta || !delta.sure ? Minus : delta.up ? ArrowUpRight : ArrowDownRight;
  return (
    <div className={cn("relative flex items-center gap-4 overflow-hidden rounded-3xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-md",
      winner && "border-amber-300/50 bg-amber-300/[0.06] shadow-[0_0_40px_-12px_rgb(252_211_77/0.6)]")}>
      <div className="pointer-events-none absolute -top-16 -right-16 size-40 rounded-full opacity-30 blur-3xl" style={{ background: color }} aria-hidden />
      <div className="relative size-28 shrink-0">
        <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden>
          <circle cx="60" cy="60" r={r} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth="10" />
          <circle cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
            strokeDasharray={`${around * Math.min(1, shown)} ${around}`} style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="text-2xl font-semibold tabular-nums tracking-tight" aria-hidden>{(shown * 100).toFixed(1)}%</div>
            <div className="text-[0.68rem] tracking-wide text-white/70 uppercase" aria-hidden>{t("onKpiConversion")}</div>
          </div>
        </div>
      </div>
      <div className="relative min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: color }} aria-hidden />
          <span className="truncate text-sm font-semibold">{name}</span>
          {winner && <Trophy className="size-3.5 shrink-0 text-amber-300" aria-label={t("onVerdictBest")} />}
        </div>
        <div className="text-xs text-white/65">{index === 0 ? t("onControl") : t("onVariantLetter", { letter: String.fromCharCode(65 + index) })}</div>
        <span className="sr-only">{t("onKpiConversion")}: {(conversion * 100).toFixed(1)}%</span>
        <div className="mt-2 text-xl font-semibold tabular-nums tracking-tight">{formatMoney(Math.round(money), currencyCode(currency))}</div>
        <div className="text-xs text-white/70">{t("onKpiRevenue")} · {t("onHeroOrders", { count: orders })} · {t("onHeroOfVisits", { visits })}</div>
        {delta && (
          <div className={cn("mt-2 inline-flex flex-wrap items-center gap-x-1 rounded-2xl px-2 py-0.5 text-xs font-semibold tabular-nums",
            !delta.sure ? "bg-white/10 text-white/80" : delta.up ? "bg-positive/30 text-white ring-1 ring-positive/60" : "bg-negative/30 text-white ring-1 ring-negative/60")}>
            <span className="inline-flex items-center gap-1 whitespace-nowrap">
              <Arrow className={cn("size-3.5", delta.sure && (delta.up ? "text-positive" : "text-negative"))} aria-hidden />{delta.text}
            </span>
            <span className="font-normal text-white/85">· {delta.sure ? (delta.up ? t("onClearlyBetter") : t("onClearlyWorse")) : t("onNoClearDiff")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
