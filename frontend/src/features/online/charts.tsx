// Charts of the online run report. Each compared store keeps one color everywhere (the validated --viz-* slots, the
// rival in a neutral gray); marks carry color, text stays in text tokens, and every value is also written out.

import { useState, type ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import type { FunnelRow, SessionOutcome, VariantSummary } from "@/shared/api/online";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import { FUNNEL_LABELS, OUTCOME_COLORS, OUTCOME_LABELS, storeColor } from "./labels";
import { formatPercent } from "@/shared/utils/money";

export function Swatch({ index, className }: { index: number; className?: string }) {
  return <span className={cn("inline-block size-2.5 shrink-0 rounded-[3px]", className)} style={{ background: storeColor(index) }} aria-hidden />;
}

/** Which color is which store: always shown next to multi-store charts. */
export function StoreKey({ names, rival }: { names: string[]; rival?: string }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {names.map((name, i) => (
        <span key={i} className="inline-flex min-w-0 items-center gap-1.5">
          <Swatch index={i} />
          <span className="truncate text-foreground" title={name}>{name}</span>
          <span>{i === 0 ? t("onControl") : t("onVariantLetter", { letter: String.fromCharCode(65 + i) })}</span>
        </span>
      ))}
      {rival && <span className="inline-flex items-center gap-1.5"><Swatch index={99} />{t("onRivalTab", { rival })}</span>}
    </div>
  );
}

export interface StatMetric {
  key: string;
  label: string;
  values: (number | null)[];
  format: (value: number) => string;
  /** Signed difference to the first store, written for this measure (points, money, seconds…). */
  delta: (variant: number, control: number) => string;
  /** Which direction is good for the store; null when neither is. */
  better: "up" | "down" | null;
}

/** One tile per measure: every store's value as a bar on the measure's own scale, and its difference to control. */
export function StatTiles({ metrics, names }: { metrics: StatMetric[]; names: string[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {metrics.map((m) => {
        const max = Math.max(...m.values.map((v) => v ?? 0), 1e-9);
        const control = m.values[0];
        return (
          <div key={m.key} className="rounded-2xl border bg-card/60 p-3">
            <div className="text-xs text-muted-foreground">{m.label}</div>
            <div className="mt-0.5 text-3xl font-semibold tracking-tight">{control === null || control === undefined ? "—" : m.format(control)}</div>
            <div className="mt-2 space-y-1.5">
              {m.values.map((value, i) => {
                const diff = value !== null && control !== null && control !== undefined ? value - control : 0;
                const good = m.better === null || diff === 0 ? null : (diff > 0) === (m.better === "up");
                return (
                  <div key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 text-xs" title={`${names[i]}: ${value === null ? "—" : m.format(value)}`}>
                    <div className="flex min-w-0 items-center gap-2">
                      <div className="h-2.5 min-w-0 flex-1 rounded-r-[4px] bg-[var(--viz-grid)]">
                        <div className="h-full rounded-r-[4px]" style={{ width: `${value === null ? 0 : Math.max(1.5, (value / max) * 100)}%`, background: storeColor(i) }} />
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 tabular-nums">
                      <span>{value === null ? "—" : m.format(value)}</span>
                      {i > 0 && value !== null && control !== null && control !== undefined && (
                        <span className={cn("rounded px-1 text-[0.7rem]", good === true ? "tone-good" : good === false ? "tone-bad" : "bg-muted text-muted-foreground")}>
                          {m.delta(value, control)}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export interface ForestRow {
  key: string;
  label: string;
  diff: number;
  low: number | null;
  high: number | null;
  format: (value: number) => string;
  /** Whether a clearly positive difference is good (false: lower is better; null: neither). */
  upIsGood: boolean | null;
  note?: ReactNode;
}

/** Paired differences to control, one measure per row on its own zero-centred scale: dot = estimate, bar = 95 % CI. */
export function DiffForest({ rows }: { rows: ForestRow[] }) {
  const { t } = useI18n();
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div className="space-y-1">
      {rows.map((r) => {
        const low = r.low ?? r.diff, high = r.high ?? r.diff;
        const span = Math.max(1e-9, Math.abs(low), Math.abs(high), Math.abs(r.diff)) * 1.15;
        const x = (v: number) => `${50 + (v / span) * 50}%`;
        const clear = r.low !== null && r.high !== null && (r.low > 0 || r.high < 0);
        const good = !clear || r.upIsGood === null ? null : (r.diff > 0) === r.upIsGood;
        const tone = good === true ? "var(--positive)" : good === false ? "var(--destructive)" : clear ? "var(--viz-1)" : "var(--viz-other)";
        const signed = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${r.format(Math.abs(v))}`;
        const Icon = !clear ? Minus : r.diff > 0 ? ArrowUpRight : ArrowDownRight;
        return (
          <div key={r.key} tabIndex={0} onPointerEnter={() => setHover(r.key)} onPointerLeave={() => setHover(null)}
            onFocus={() => setHover(r.key)} onBlur={() => setHover(null)}
            className="grid grid-cols-[minmax(6.5rem,10rem)_minmax(0,1fr)_minmax(6rem,8.5rem)] items-center gap-3 rounded-lg px-1.5 py-1 outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring/50">
            <div className="line-clamp-2 min-w-0 text-xs leading-tight font-medium" title={r.label}>{r.label}</div>
            <div className="relative h-7">
              <div className="absolute inset-y-1 left-1/2 w-px bg-foreground/25" aria-hidden />
              {r.low !== null && r.high !== null && (
                <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full opacity-45"
                  style={{ left: x(Math.min(low, high)), width: `${(Math.abs(high - low) / span) * 50}%`, background: tone }} />
              )}
              <div className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card" style={{ left: x(r.diff), background: tone }} />
              {hover === r.key && (
                <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded-lg border bg-popover px-2.5 py-1.5 text-xs shadow-lg">
                  <div className="font-semibold tabular-nums">{signed(r.diff)}</div>
                  {r.low !== null && r.high !== null && <div className="text-muted-foreground">{t("studioCi95", { low: signed(r.low), high: signed(r.high) })}</div>}
                </div>
              )}
            </div>
            <div className="text-right">
              <div className="text-sm font-semibold tabular-nums">{signed(r.diff)}</div>
              <div className={cn("inline-flex items-center gap-0.5 text-[0.68rem]", good === true ? "text-positive" : good === false ? "text-destructive" : "text-muted-foreground")}>
                <Icon className="size-3" aria-hidden />
                {good === true ? t("onClearlyBetter") : good === false ? t("onClearlyWorse") : clear ? t("onClearDiff") : t("onNoClearDiff")}
              </div>
            </div>
            {r.note && <div className="col-span-3 -mt-1 text-right [&>*]:mt-0">{r.note}</div>}
          </div>
        );
      })}
    </div>
  );
}

/** Each funnel stage as a row of bars, one per store, sized by the share of visits that got that far. */
export function FunnelChart({ variants }: { variants: VariantSummary[] }) {
  const { t } = useI18n();
  const stages = variants[0]?.funnel.map((f) => f.stage) ?? [];
  const at = (s: VariantSummary, stage: FunnelRow["stage"]) => s.funnel.find((f) => f.stage === stage);
  return (
    <div className="space-y-2.5">
      {stages.map((stage, row) => (
        <div key={stage} className="grid grid-cols-[minmax(5.5rem,8rem)_minmax(0,1fr)] items-center gap-3">
          <div className="text-xs">
            <div className="font-medium">{t(FUNNEL_LABELS[stage])}</div>
            <div className="text-[0.7rem] text-muted-foreground">{row + 1}/{stages.length}</div>
          </div>
          <div className="space-y-[2px]">
            {variants.map((s, i) => {
              const f = at(s, stage);
              const previous = row > 0 ? at(s, stages[row - 1]!) : undefined;
              const kept = f && previous && previous.sessions ? f.sessions / previous.sessions : null;
              return (
                <div key={s.site_id} className="flex items-center gap-2" title={`${s.site_name} · ${t(FUNNEL_LABELS[stage])}: ${f?.sessions ?? 0}`}>
                  <div className="h-3.5 min-w-0 flex-1">
                    <div className="h-full rounded-r-[4px] transition-[width] duration-700" style={{ width: `${Math.max(0.8, (f?.share ?? 0) * 100)}%`, background: storeColor(i) }} />
                  </div>
                  <span className="w-28 shrink-0 text-right text-[0.7rem] tabular-nums">
                    {f?.sessions ?? 0} · {formatPercent(f?.share ?? 0, 0)}
                    {kept !== null && kept < 1 && <span className="ml-1 text-muted-foreground">↓{formatPercent(1 - kept, 0)}</span>}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// White reads on the deep fills, near-black on the light ones (amber, slate, sky).
const OUTCOME_INK: Record<SessionOutcome, string> = {
  // The positive and negative colours turn light in dark mode, and white on violet stays under 4.5:1.
  purchased: "text-white dark:text-neutral-950", bounced: "text-white dark:text-neutral-950", timed_out: "text-neutral-950",
  abandoned_cart: "text-neutral-950", left: "text-neutral-950", step_limit: "text-neutral-950",
};

/** How visits ended, as one 100 % bar per store; a share is written inside its segment only when it fits. */
export function OutcomeBars({ variants }: { variants: VariantSummary[] }) {
  const { t } = useI18n();
  const outcomes = [...new Set(variants.flatMap((s) => Object.keys(s.outcomes)))] as SessionOutcome[];
  return (
    <div className="space-y-3">
      {variants.map((s, i) => (
        <div key={s.site_id} className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-medium"><Swatch index={i} /><span className="truncate">{s.site_name}</span></div>
          <div className="flex h-6 gap-[2px] overflow-hidden rounded-md" role="img" aria-label={`${s.site_name}: ${outcomes.map((o) => `${t(OUTCOME_LABELS[o])} ${s.outcomes[o] ?? 0}`).join(", ")}`}>
            {outcomes.map((o) => {
              const n = s.outcomes[o] ?? 0;
              const share = s.sessions ? n / s.sessions : 0;
              if (!n) return null;
              return (
                <span key={o} className={cn("flex items-center justify-center text-[0.7rem] font-semibold", OUTCOME_INK[o], OUTCOME_COLORS[o])}
                  style={{ width: `${share * 100}%` }} title={`${t(OUTCOME_LABELS[o])}: ${n} (${formatPercent(share, 1)})`}>
                  {share >= 0.09 ? formatPercent(share, 0) : ""}
                </span>
              );
            })}
          </div>
        </div>
      ))}
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[0.7rem] text-muted-foreground">
        {outcomes.map((o) => (
          <span key={o} className="inline-flex items-center gap-1"><span className={cn("size-2.5 rounded-[3px]", OUTCOME_COLORS[o])} />{t(OUTCOME_LABELS[o])}</span>
        ))}
      </div>
    </div>
  );
}

export interface HeatCell { value: number | null; label: string; sub: string; title: string }

/** Segments × stores, shaded by conversion in one hue (darker = higher), the figures written in every cell. */
export function SegmentHeat({ rows, columns, cells }: { rows: string[]; columns: string[]; cells: HeatCell[][] }) {
  const max = Math.max(1e-9, ...cells.flat().map((c) => c.value ?? 0));
  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[420px] gap-[2px]" style={{ gridTemplateColumns: `minmax(7rem,10rem) repeat(${columns.length}, minmax(6rem,1fr))` }}>
        <span />
        {columns.map((c, i) => (
          <span key={i} className="flex min-w-0 items-center gap-1.5 px-2 pb-1 text-[0.7rem] font-medium"><Swatch index={i} /><span className="truncate">{c}</span></span>
        ))}
        {rows.map((r, ri) => (
          <div key={r} className="contents">
            <span className="flex items-center pr-2 text-xs">{r}</span>
            {cells[ri]!.map((cell, ci) => (
              <span key={ci} className="rounded-md px-2 py-1.5" title={cell.title}
                style={{ background: cell.value === null ? "var(--muted)" : `color-mix(in oklab, var(--viz-1) ${Math.round(6 + (cell.value / max) * 52)}%, var(--card))` }}>
                <span className="block text-sm font-semibold tabular-nums">{cell.label}</span>
                <span className="block text-[0.7rem] tabular-nums text-foreground/70">{cell.sub}</span>
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
