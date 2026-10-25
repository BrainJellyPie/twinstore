// Every shopper of a run as a dot that streams into each store, travels the funnel and settles under the stage where
// their visit stopped; buyers reach the end and glow. The same shoppers enter every store at the same moment, so the
// stores' piles compare like for like. Hover a dot to find that shopper in the other stores; click it to watch.

import { useState } from "react";
import { MousePointerClick, RotateCcw } from "lucide-react";

import type { FunnelStage, OnlineRunResult, OnlineShopper, SessionOutcome, VisitBrief } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import { Swatch } from "./charts";
import { FUNNEL_LABELS, MISSION_LABELS, OUTCOME_COLORS, OUTCOME_LABELS, storeColor } from "./labels";

const PER_ROW = 10;
const PITCH_Y = 10;
const PIPE = 12;
const STAGES: FunnelStage[] = ["visit", "product_view", "add_to_cart", "checkout", "payment", "purchase"];
const OUTCOME_ORDER: SessionOutcome[] = ["purchased", "abandoned_cart", "left", "bounced", "timed_out", "step_limit"];

interface Dot { shopper: OnlineShopper; arrival: number; brief: VisitBrief; stage: number; x: number; y: number }

function lanes(result: OnlineRunResult): { dots: Dot[]; rows: number; counts: number[] }[] {
  const visits = result.visits ?? {};
  const columns = STAGES.length;
  return result.variants.map((_, lane) => {
    const buckets: { shopper: OnlineShopper; arrival: number; brief: VisitBrief; stage: number }[][] = Array.from({ length: columns }, () => []);
    result.shoppers.forEach((shopper, arrival) => {
      const brief = visits[shopper.id]?.[lane];
      if (!brief) return;
      const stage = Math.max(0, STAGES.indexOf(brief.furthest ?? (brief.outcome === "purchased" ? "purchase" : "visit")));
      buckets[stage]!.push({ shopper, arrival, brief, stage });
    });
    const dots: Dot[] = [];
    let rows = 1;
    buckets.forEach((bucket, stage) => {
      bucket.sort((a, b) => OUTCOME_ORDER.indexOf(a.brief.outcome) - OUTCOME_ORDER.indexOf(b.brief.outcome) || a.arrival - b.arrival);
      bucket.forEach((d, slot) => {
        const col = slot % PER_ROW;
        const row = Math.floor(slot / PER_ROW);
        rows = Math.max(rows, row + 1);
        const width = 100 / columns;
        dots.push({ ...d, x: (stage + 0.5) * width + (col - (PER_ROW - 1) / 2) * (width / (PER_ROW + 2)), y: PIPE + 18 + row * PITCH_Y });
      });
    });
    return { dots, rows, counts: buckets.map((b) => b.length) };
  });
}

export function ShopperRiver({ result, money, onWatch }: {
  result: OnlineRunResult;
  money: (amount: number) => string;
  onWatch: (variant: number, shopperId: string) => void;
}) {
  const { t } = useI18n();
  const [round, setRound] = useState(0);
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === "undefined");
  const [hover, setHover] = useState<{ lane: number; dot: Dot } | null>(null);
  const layout = lanes(result);
  const n = result.shoppers.length;
  const stagger = Math.min(30, 2400 / Math.max(1, n));
  const outcomes = OUTCOME_ORDER.filter((o) => result.variants.some((s) => (s.outcomes[o] ?? 0) > 0));
  // Start when the stream first scrolls into view, so it plays where it can be seen.
  const watch = (el: HTMLDivElement | null) => {
    if (!el || seen || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => { if (entry?.isIntersecting) { setSeen(true); io.disconnect(); } }, { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  };

  return (
    <div ref={watch} className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[0.7rem] text-muted-foreground">
        {outcomes.map((o) => (
          <span key={o} className="inline-flex items-center gap-1.5">
            <span className={cn("size-2.5 rounded-full", OUTCOME_COLORS[o], o === "purchased" && "shadow-[0_0_8px_var(--positive)]")} aria-hidden />{t(OUTCOME_LABELS[o])}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5"><MousePointerClick className="size-3.5" aria-hidden />{t("onRiverClick")}</span>
        <Button size="sm" variant="outline" className="ml-auto h-7 gap-1.5 rounded-full text-xs" onClick={() => { setRound((r) => r + 1); setHover(null); }}>
          <RotateCcw className="size-3.5" aria-hidden /> {t("onRiverReplay")}
        </Button>
      </div>

      <div className="overflow-hidden rounded-3xl border bg-[radial-gradient(120%_80%_at_0%_0%,color-mix(in_oklab,var(--heat-1)_8%,transparent),transparent_60%),radial-gradient(100%_80%_at_100%_100%,color-mix(in_oklab,var(--heat-3)_7%,transparent),transparent_60%)] p-3 sm:p-4">
        <div className="grid grid-cols-6 pb-2 text-center text-[0.7rem] font-semibold tracking-wide text-muted-foreground uppercase" aria-hidden>
          {STAGES.map((stage) => <span key={stage} className="truncate px-0.5">{t(FUNNEL_LABELS[stage])}</span>)}
        </div>
        <div key={round} className="space-y-4">
          {layout.map((lane, i) => {
            const s = result.variants[i]!;
            const height = PIPE + 18 + lane.rows * PITCH_Y + 22;
            return (
              <div key={s.site_id} role="group" aria-label={t("onRiverLane", { store: s.site_name, orders: s.purchases, visits: s.sessions })}>
                <div className="mb-1 flex items-center gap-2 text-xs">
                  <Swatch index={i} />
                  <span className="truncate font-semibold">{s.site_name}</span>
                  <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">{t("onHeroOrders", { count: s.purchases })} · {(s.conversion * 100).toFixed(1)}%</span>
                </div>
                <div className="relative [container-type:inline-size]" style={{ height }}>
                  {/* The pipe every shopper travels, a node at each stage. */}
                  <div className="absolute inset-x-[8.33%] h-[3px] -translate-y-1/2 rounded-full opacity-60"
                    style={{ top: PIPE, background: `linear-gradient(90deg, ${storeColor(i)}, color-mix(in oklab, ${storeColor(i)} 30%, var(--positive)))` }} aria-hidden />
                  {STAGES.map((stage, k) => (
                    <span key={stage} className="absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-card"
                      style={{ left: `${(k + 0.5) * (100 / 6)}%`, top: PIPE, borderColor: k === 5 ? "var(--positive)" : storeColor(i) }} aria-hidden />
                  ))}
                  {seen && lane.dots.map((d) => {
                    const lit = hover?.dot.shopper.id === d.shopper.id;
                    return (
                      <button key={d.shopper.id} type="button" tabIndex={-1}
                        aria-label={t("onRiverDot", { shopper: d.shopper.identity, outcome: t(OUTCOME_LABELS[d.brief.outcome]) })}
                        onPointerEnter={() => setHover({ lane: i, dot: d })} onPointerLeave={() => setHover(null)}
                        onClick={() => onWatch(i, d.shopper.id)}
                        className={cn("crowd-dot absolute size-[min(8px,1cqw)] min-h-[4px] min-w-[4px] -translate-x-1/2 -translate-y-1/2 rounded-full transition-[scale,box-shadow] hover:scale-[2.2]",
                          OUTCOME_COLORS[d.brief.outcome], d.brief.outcome === "purchased" && "crowd-bought",
                          d.brief.rival && "ring-2 ring-amber-400/80", lit && "z-10 scale-[2.2] ring-2 ring-foreground")}
                        style={{
                          left: `${d.x}%`, top: d.y,
                          ["--x" as string]: `${d.x}%`, ["--y" as string]: `${d.y}px`, ["--pipe" as string]: `${PIPE}px`,
                          ["--delay" as string]: `${Math.round(d.arrival * stagger)}ms`, ["--dur" as string]: `${700 + d.stage * 260}ms`,
                        }} />
                    );
                  })}
                  {lane.counts.map((count, k) => count > 0 && (
                    <span key={k} className="absolute bottom-0 -translate-x-1/2 text-[0.7rem] font-semibold tabular-nums text-muted-foreground"
                      style={{ left: `${(k + 0.5) * (100 / 6)}%` }}>{count}</span>
                  ))}
                  {hover?.lane === i && (
                    <div className="pointer-events-none absolute z-20 w-56 -translate-x-1/2 rounded-xl border bg-popover/95 p-2.5 text-xs shadow-xl backdrop-blur"
                      style={{ left: `clamp(7rem, ${hover.dot.x}%, calc(100% - 7rem))`, top: hover.dot.y + 12 }}>
                      <div className="truncate font-semibold">{hover.dot.shopper.identity}</div>
                      <div className="truncate text-muted-foreground">{t(MISSION_LABELS[hover.dot.shopper.mission])} · {hover.dot.shopper.goal}</div>
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className={cn("size-2 rounded-full", OUTCOME_COLORS[hover.dot.brief.outcome])} aria-hidden />
                        {t(OUTCOME_LABELS[hover.dot.brief.outcome])}{hover.dot.brief.order_total > 0 && ` · ${money(hover.dot.brief.order_total)}`}
                        <span className="ml-auto text-muted-foreground">{t(FUNNEL_LABELS[STAGES[hover.dot.stage]!])}</span>
                      </div>
                      <div className="mt-1 text-[0.7rem] text-primary">{t("onRiverWatch")}</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
