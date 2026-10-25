// The first pages of every visit as a flow (Sankey) chart: one column per step, ribbons as wide as the visits that
// went from one page to the next, and on the right how the visits ended. Particles run along the ribbons; hovering
// a page or a ribbon follows its visitors.

import { useState } from "react";
import { Route } from "lucide-react";

import type { FlowLink, PageKind, SessionOutcome, VariantSummary } from "@/shared/api/online";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { Swatch } from "./charts";
import { OUTCOME_LABELS, PAGE_LABELS } from "./labels";

const W = 1000;
const H = 380;
const NODE = 14;
const GAP = 10;
const PAGE_ORDER: PageKind[] = ["home", "deals", "category", "search", "product", "wishlist", "cart", "sign_in", "checkout", "order_complete", "help", "settings"];
const OUTCOME_ORDER: SessionOutcome[] = ["purchased", "abandoned_cart", "left", "bounced", "timed_out", "step_limit"];

// Pages by what the shopper is doing there; the aurora hues are not the stores' colors, so a page never reads as a store.
const GROUPS: { label: MessageKey; color: string; pages: PageKind[] }[] = [
  { label: "onFlowBrowse", color: "var(--heat-1)", pages: ["home", "deals", "category", "search"] },
  { label: "onFlowProducts", color: "var(--heat-2)", pages: ["product", "wishlist"] },
  { label: "onFlowCheckout", color: "var(--heat-3)", pages: ["cart", "sign_in", "checkout"] },
  { label: "onFlowDone", color: "var(--positive)", pages: ["order_complete"] },
  { label: "onFlowOther", color: "var(--viz-other)", pages: ["help", "settings"] },
];
const pageColor = (page: PageKind) => GROUPS.find((g) => g.pages.includes(page))?.color ?? "var(--viz-other)";
const OUTCOME_FILL: Record<SessionOutcome, string> = {
  purchased: "fill-positive stroke-positive", abandoned_cart: "fill-amber-500 stroke-amber-500", left: "fill-slate-400 stroke-slate-400",
  bounced: "fill-negative stroke-negative", timed_out: "fill-violet-500 stroke-violet-500", step_limit: "fill-sky-500 stroke-sky-500",
};

interface Node { id: string; column: number; page: PageKind | null; outcome: SessionOutcome | null; value: number; y: number; h: number }
interface Ribbon { key: string; link: FlowLink; from: Node; to: Node; sy: number; ty: number; h: number }

function layout(flow: FlowLink[], sessions: number) {
  const last = Math.max(0, ...flow.map((l) => l.depth));
  const columns = last + 2;  // the step columns, then how visits ended
  const nodes = new Map<string, Node>();
  const node = (id: string, column: number, page: PageKind | null, outcome: SessionOutcome | null) => {
    let n = nodes.get(id);
    if (!n) nodes.set(id, n = { id, column, page, outcome, value: 0, y: 0, h: 0 });
    return n;
  };
  for (const l of flow) {
    node(`${l.depth}|${l.source}`, l.depth, l.source, null).value += l.sessions;
    if (l.target === null && l.outcome) node(`end|${l.outcome}`, columns - 1, null, l.outcome).value += l.sessions;
    else if (l.target) node(`${l.depth + 1}|${l.target}`, l.depth + 1, l.target, null);
  }
  const byColumn = Array.from({ length: columns }, (_, c) => [...nodes.values()].filter((n) => n.column === c)
    .sort((a, b) => a.page && b.page ? PAGE_ORDER.indexOf(a.page) - PAGE_ORDER.indexOf(b.page)
      : OUTCOME_ORDER.indexOf(a.outcome!) - OUTCOME_ORDER.indexOf(b.outcome!)));
  const crowded = Math.max(1, ...byColumn.map((c) => c.length));
  const scale = (H - GAP * (crowded - 1)) / Math.max(1, sessions);
  for (const column of byColumn) {
    const total = column.reduce((sum, n) => sum + Math.max(1.5, n.value * scale), 0) + GAP * (column.length - 1);
    let y = (H - total) / 2;
    for (const n of column) { n.h = Math.max(1.5, n.value * scale); n.y = y; y += n.h + GAP; }
  }
  const x = (column: number) => (column * (W - NODE)) / (columns - 1);
  const ribbons: Ribbon[] = flow.map((l, i) => {
    const from = nodes.get(`${l.depth}|${l.source}`)!;
    const to = l.target ? nodes.get(`${l.depth + 1}|${l.target}`)! : nodes.get(`end|${l.outcome}`)!;
    return { key: String(i), link: l, from, to, sy: 0, ty: 0, h: l.sessions * scale };
  });
  // Stack ribbons on each node in the order of what they connect to, so they cross as little as possible.
  const out = new Map<string, number>();
  const into = new Map<string, number>();
  for (const r of [...ribbons].sort((a, b) => a.to.column - b.to.column || a.to.y - b.to.y)) {
    r.sy = r.from.y + (out.get(r.from.id) ?? 0);
    out.set(r.from.id, (out.get(r.from.id) ?? 0) + r.h);
  }
  for (const r of [...ribbons].sort((a, b) => a.from.column - b.from.column || a.from.y - b.from.y)) {
    r.ty = r.to.y + (into.get(r.to.id) ?? 0);
    into.set(r.to.id, (into.get(r.to.id) ?? 0) + r.h);
  }
  return { nodes: [...nodes.values()], ribbons, columns, x };
}

/** The busiest route: from the busiest first page, always the widest ribbon on. */
function topRoute(flow: FlowLink[]): (PageKind | SessionOutcome)[] {
  const first = flow.filter((l) => l.depth === 0);
  const starts = new Map<PageKind, number>();
  for (const l of first) starts.set(l.source, (starts.get(l.source) ?? 0) + l.sessions);
  let page = [...starts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const route: (PageKind | SessionOutcome)[] = [];
  for (let depth = 0; page; depth++) {
    route.push(page);
    const best = flow.filter((l) => l.depth === depth && l.source === page).sort((a, b) => b.sessions - a.sessions)[0];
    if (!best) break;
    if (best.target === null) { if (best.outcome) route.push(best.outcome); break; }
    page = best.target;
  }
  return route;
}

export function PageFlow({ variants }: { variants: VariantSummary[] }) {
  const { t } = useI18n();
  const [store, setStore] = useState(0);
  const [focus, setFocus] = useState<{ node?: string; ribbon?: string } | null>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);
  const summary = variants[Math.min(store, variants.length - 1)]!;
  const flow = summary.flow ?? [];
  const { nodes, ribbons, columns, x } = layout(flow, summary.sessions);
  const name = (n: Node) => (n.page ? t(PAGE_LABELS[n.page]) : t(OUTCOME_LABELS[n.outcome!]));
  const lit = (r: Ribbon) => !focus || focus.ribbon === r.key || focus.node === r.from.id || focus.node === r.to.id;
  const share = (n: number) => `${summary.sessions ? Math.round((n / summary.sessions) * 100) : 0}%`;
  const route = topRoute(flow);
  const hovered = focus?.ribbon ? ribbons.find((r) => r.key === focus.ribbon) : null;
  const hoveredNode = focus?.node ? nodes.find((n) => n.id === focus.node) : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {variants.length > 1 && (
          <div className="inline-flex rounded-full border bg-card/60 p-0.5 text-xs" role="group" aria-label={t("onFlowStore")}>
            {variants.map((s, i) => (
              <button key={s.site_id} type="button" aria-pressed={store === i} onClick={() => { setStore(i); setFocus(null); }}
                className={cn("inline-flex max-w-52 items-center gap-1.5 rounded-full px-3 py-1", store === i ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-muted")}>
                <Swatch index={i} /><span className="truncate">{s.site_name}</span>
              </button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[0.7rem] text-muted-foreground">
          {GROUPS.map((g) => (
            <span key={g.label} className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-[3px]" style={{ background: g.color }} aria-hidden />{t(g.label)}</span>
          ))}
        </div>
      </div>

      {route.length > 1 && (
        <p className="flex flex-wrap items-center gap-1.5 text-xs">
          <Route className="size-3.5 text-primary" aria-hidden />
          <span className="font-medium">{t("onFlowTopRoute")}</span>
          {route.map((step, i) => (
            <span key={i} className="inline-flex items-center gap-1.5">
              {i > 0 && <span className="text-muted-foreground" aria-hidden>→</span>}
              <span className="rounded-full border bg-card/70 px-2 py-0.5">
                {step in PAGE_LABELS ? t(PAGE_LABELS[step as PageKind]) : t(OUTCOME_LABELS[step as SessionOutcome])}
              </span>
            </span>
          ))}
        </p>
      )}

      <div className="relative overflow-hidden rounded-3xl border bg-card/40 px-3 pt-8 pb-3 sm:px-5"
        onPointerMove={(e) => { const box = e.currentTarget.getBoundingClientRect(); setPointer({ x: e.clientX - box.left, y: e.clientY - box.top }); }}
        onPointerLeave={() => { setPointer(null); setFocus(null); }}>
        <div className="pointer-events-none absolute inset-x-3 top-2 h-5 sm:inset-x-5" aria-hidden>
          {Array.from({ length: columns }, (_, c) => (
            <span key={c} className={cn("absolute top-0 text-[0.65rem] font-semibold tracking-wide whitespace-nowrap text-muted-foreground uppercase", c === columns - 1 ? "-translate-x-full" : c > 0 && "-translate-x-1/3")}
              style={{ left: `${((x(c) + (c === columns - 1 ? NODE : 0)) / W) * 100}%` }}>
              {c === columns - 1 ? t("onFlowEnd") : t("onFlowStep", { step: c + 1 })}
            </span>
          ))}
        </div>
        <div className="relative" style={{ height: H }}>
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible" role="img"
            aria-label={t("onFlowAria", { store: summary.site_name })}>
            {ribbons.map((r) => {
              const x0 = x(r.from.column) + NODE, x1 = x(r.to.column), mid = (x0 + x1) / 2;
              const end = r.to.outcome;
              return (
                <path key={r.key} d={`M${x0},${r.sy} C${mid},${r.sy} ${mid},${r.ty} ${x1},${r.ty} L${x1},${r.ty + r.h} C${mid},${r.ty + r.h} ${mid},${r.sy + r.h} ${x0},${r.sy + r.h} Z`}
                  className={cn("transition-opacity duration-300", end && OUTCOME_FILL[end])}
                  style={{ fill: end ? undefined : pageColor(r.to.page!), opacity: lit(r) ? (focus ? 0.7 : 0.4) : 0.06 }}
                  onPointerEnter={() => setFocus({ ribbon: r.key })} />
              );
            })}
            {ribbons.filter((r) => r.h >= 5 && lit(r)).map((r) => {
              const x0 = x(r.from.column) + NODE, x1 = x(r.to.column), mid = (x0 + x1) / 2;
              const y0 = r.sy + r.h / 2, y1 = r.ty + r.h / 2;
              const end = r.to.outcome;
              return (
                <path key={`p${r.key}`} d={`M${x0},${y0} C${mid},${y0} ${mid},${y1} ${x1},${y1}`} fill="none" vectorEffect="non-scaling-stroke"
                  strokeLinecap="round" strokeDasharray="2 30" strokeWidth={Math.min(4, 1.5 + r.h / 14)}
                  className={cn("flow-particles pointer-events-none", end && OUTCOME_FILL[end])}
                  style={{ stroke: end ? undefined : pageColor(r.to.page!), fill: "none", animationDelay: `${-(Number(r.key) % 7) * 0.23}s` }} />
              );
            })}
            {nodes.map((n) => (
              <rect key={n.id} x={x(n.column)} y={n.y} width={NODE} height={n.h} rx={3}
                className={cn("cursor-pointer stroke-card", n.outcome && OUTCOME_FILL[n.outcome])} strokeWidth={1.5} vectorEffect="non-scaling-stroke"
                style={{ fill: n.page ? pageColor(n.page) : undefined, opacity: !focus || focus.node === n.id ? 1 : 0.55 }}
                onPointerEnter={() => setFocus({ node: n.id })} />
            ))}
          </svg>
          {nodes.filter((n) => n.h >= 16).map((n) => {
            const right = n.column === columns - 1;
            return (
              <span key={n.id} className={cn("pointer-events-none absolute z-[1] -translate-y-1/2 truncate rounded-md bg-card/80 px-1.5 py-px text-[0.65rem] leading-tight shadow-sm backdrop-blur",
                right ? "-translate-x-full" : "")}
                style={{ left: right ? `calc(${(x(n.column) / W) * 100}% - 4px)` : `calc(${((x(n.column) + NODE) / W) * 100}% + 4px)`, top: n.y + n.h / 2, maxWidth: "9rem" }}>
                <span className="font-medium">{name(n)}</span> <span className="tabular-nums text-muted-foreground">{n.value}</span>
              </span>
            );
          })}
        </div>
        {pointer && (hovered || hoveredNode) && (
          <div className="pointer-events-none absolute z-10 max-w-64 rounded-xl border bg-popover/95 px-3 py-2 text-xs shadow-xl backdrop-blur"
            style={{ left: pointer.x + 14, top: pointer.y + 14, transform: pointer.x > 520 ? "translateX(calc(-100% - 28px))" : undefined }}>
            {hovered ? (
              <>
                <div className="font-semibold">{name(hovered.from)} → {name(hovered.to)}</div>
                <div className="tabular-nums text-muted-foreground">{t("onFlowVisits", { count: hovered.link.sessions })} · {share(hovered.link.sessions)}</div>
                <div className="text-muted-foreground">{t("onFlowStep", { step: hovered.link.depth + 1 })}</div>
              </>
            ) : hoveredNode && (
              <>
                <div className="font-semibold">{name(hoveredNode)}</div>
                <div className="tabular-nums text-muted-foreground">{t("onFlowVisits", { count: hoveredNode.value })} · {share(hoveredNode.value)}</div>
                <div className="text-muted-foreground">{hoveredNode.page ? t("onFlowStep", { step: hoveredNode.column + 1 }) : t("onFlowEnd")}</div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
