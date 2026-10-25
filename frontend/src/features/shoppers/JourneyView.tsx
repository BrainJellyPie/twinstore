// One shopper's trip: a mini floor map with the walked path and numbered stops, and the steps with the
// thought recorded at each one. Steps cited by an interview answer are highlighted.

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { DoorClosed, DoorOpen, Footprints, Eye, ShoppingBasket, CreditCard, Shuffle, X } from "lucide-react";

import { shelfFaceUrl, type Journey, type JourneyAction, type JourneyStep } from "@/shared/api/interview";
import type { Store } from "@/shared/types/domain";
import { cn } from "@/shared/utils/cn";
import { rackBounds } from "@/shared/utils/grid";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const ICON: Record<JourneyAction, typeof Eye> = {
  enter: DoorOpen, move: Footprints, browse: Eye, buy: ShoppingBasket, pay: CreditCard, wander: Shuffle, exit: DoorClosed,
};
const VERB: Record<JourneyAction, MessageKey> = {
  enter: "journeyEnter", move: "journeyMove", browse: "journeyBrowse", buy: "journeyBuy", pay: "journeyPay", wander: "journeyWander", exit: "journeyExit",
};
const SIDE: Record<string, MessageKey> = { N: "dirNorth", S: "dirSouth", E: "dirEast", W: "dirWest" };
const VERB_AT: Partial<Record<JourneyAction, MessageKey>> = {
  enter: "journeyEnterAt", move: "journeyMoveAt", browse: "journeyBrowseAt", buy: "journeyBuyAt", pay: "journeyPayAt", wander: "journeyWanderAt", exit: "journeyExitAt",
};

export function JourneyMap({ journey, store, active, onHover }: { journey: Journey; store: Store; active: Set<number>; onHover: (i: number | null) => void }) {
  const { t } = useI18n();
  const [w, h] = store.grid_size;
  const points = journey.path.map(([, x, y]) => `${x + 0.5},${y + 0.5}`).join(" ");
  // One marker per spot: a shopper often browses and buys several times without moving.
  const spots = new Map<string, JourneyStep[]>();
  for (const s of journey.steps) {
    if (s.action !== "browse" && s.action !== "buy") continue;
    const key = `${s.x},${s.y}`;
    spots.set(key, [...(spots.get(key) ?? []), s]);
  }
  return (
    <svg viewBox={`-0.3 -0.3 ${w + 0.6} ${h + 0.6}`} className="w-full rounded-xl border bg-foreground/[0.025]" role="img" aria-label={t("journeyPath")}>
      {store.racks.map((r) => {
        const b = rackBounds(r);
        return (
          <rect key={r.id} x={r.position[0] + 0.08} y={r.position[1] + 0.08} width={b.w - 0.16} height={b.d - 0.16} rx={0.12}
            className={cn(journey.shelves[r.id] ? "fill-foreground/25" : "fill-foreground/10")}>
            <title>{r.rack_name || r.type}</title>
          </rect>
        );
      })}
      <polyline points={points} fill="none" stroke="var(--viz-1)" strokeWidth={0.09} strokeLinejoin="round" strokeLinecap="round" opacity={0.85} />
      {[...spots.values()].map((group) => {
        const s = group[0]!;
        const bought = group.some((g) => g.action === "buy");
        const on = group.some((g) => active.has(g.index));
        const label = group.length > 1 ? `${s.index}+` : String(s.index);
        return (
          <g key={s.index} onPointerEnter={() => onHover(s.index)} onPointerLeave={() => onHover(null)} className="cursor-default">
            <title>{group.map((g) => `${g.index}. ${g.action}${g.product_name ? ` ${g.product_name}` : ""}`).join("\n")}</title>
            <circle cx={s.x + 0.5} cy={s.y + 0.5} r={on ? 0.44 : 0.34}
              fill={bought ? "var(--viz-2)" : "var(--viz-1)"} stroke="var(--card)" strokeWidth={0.08} />
            <text x={s.x + 0.5} y={s.y + 0.5} textAnchor="middle" dominantBaseline="central" fontSize={label.length > 2 ? 0.27 : 0.33} fill="#fff" fontWeight={700}>{label}</text>
          </g>
        );
      })}
      {journey.path[0] && <circle cx={journey.path[0][1] + 0.5} cy={journey.path[0][2] + 0.5} r={0.2} fill="var(--positive)" />}
    </svg>
  );
}

export function JourneySteps({ projectId, journey, active, onHover }: {
  projectId: string; journey: Journey; active: Set<number>; onHover: (i: number | null) => void;
}) {
  const { locale, t } = useI18n();
  const [zoom, setZoom] = useState<{ url: string; title: string } | null>(null);
  // The first browse/buy step at each shelf face shows what the shopper saw there.
  const firstAtFace = new Set<number>();
  const seen = new Set<string>();
  for (const s of journey.steps) {
    const key = `${s.rack_id}:${s.face}`;
    if ((s.action === "browse" || s.action === "buy") && s.rack_id && s.face && s.sees_products && !seen.has(key)) {
      seen.add(key);
      firstAtFace.add(s.index);
    }
  }
  return (
    <>
      <ol className="relative space-y-1 before:absolute before:top-2 before:bottom-2 before:left-[0.95rem] before:w-px before:bg-foreground/10">
        {journey.steps.map((s) => (
          <Step key={s.index} step={s} currency={journey.currency} active={active.has(s.index)} onHover={onHover}
            shelf={firstAtFace.has(s.index) ? shelfFaceUrl(projectId, journey.run_id, s.rack_id, s.face) : null}
            onZoom={(url) => setZoom({ url, title: t("journeyShelfTitle", { rack: s.rack, time: s.time,
              side: locale !== "en" && SIDE[s.face] ? t(SIDE[s.face]!) : s.face }) })} />
        ))}
      </ol>
      {zoom && <Lightbox {...zoom} onClose={() => setZoom(null)} />}
    </>
  );
}

function Lightbox({ url, title, onClose }: { url: string; title: string; onClose: () => void }) {
  const { t } = useI18n();
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  // Portal: the side panel's backdrop filter would otherwise contain the fixed overlay.
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-6 backdrop-blur-sm" onClick={onClose} role="dialog" aria-label={title}>
      <figure className="max-w-4xl overflow-hidden rounded-2xl bg-card shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <img src={url} alt={title} className="max-h-[75vh] w-full object-contain" />
        <figcaption className="flex items-center gap-2 px-4 py-2.5 text-sm">
          <span className="flex-1 text-muted-foreground">{title}</span>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-foreground/[0.06]" aria-label={t("close")}><X className="size-4" /></button>
        </figcaption>
      </figure>
    </div>,
    document.body,
  );
}

function Step({ step: s, currency, active, onHover, shelf, onZoom }: {
  step: JourneyStep; currency: string; active: boolean; onHover: (i: number | null) => void; shelf: string | null; onZoom: (url: string) => void;
}) {
  const { t } = useI18n();
  const Icon = ICON[s.action] ?? Footprints;
  const at = VERB_AT[s.action];
  const verb = s.rack && at ? t(at, { rack: s.rack }) : VERB[s.action] ? t(VERB[s.action]) : `${s.action}${s.rack ? ` ${s.rack}` : ""}`;
  const buy = s.action === "buy";
  return (
    <li
      onPointerEnter={() => onHover(s.index)}
      onPointerLeave={() => onHover(null)}
      className={cn("relative flex gap-2.5 rounded-xl py-1.5 pr-2 pl-0.5 transition-colors", active && "bg-primary/[0.08] ring-1 ring-primary/30")}
    >
      <span className={cn("relative z-[1] grid size-7 shrink-0 place-items-center rounded-full border bg-card", buy && "border-transparent text-white")}
        style={buy ? { background: "var(--viz-2)" } : undefined}>
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-1.5 text-[0.78rem]">
          <span className="num font-semibold text-muted-foreground">{s.index}</span>
          <span className="font-medium">{verb}</span>
          <span className="num ml-auto shrink-0 text-[0.7rem] text-muted-foreground">{s.time}</span>
        </div>
        {s.product_name && (
          <div className="text-[0.78rem]">
            <b>{s.product_name}</b>{s.quantity > 1 ? ` ×${s.quantity}` : ""} · <span className="num">{formatMoney(s.price * s.quantity, currency)}</span>
            {s.origin === "impulse" && <span className="ml-1.5 rounded-full bg-[color-mix(in_oklab,var(--viz-2)_18%,transparent)] px-1.5 py-px text-[0.7rem] font-semibold">{t("journeyImpulse")}</span>}
          </div>
        )}
        {s.thought && <p className="mt-0.5 text-[0.76rem] leading-snug text-muted-foreground italic">“{s.thought}”</p>}
        {shelf && (
          <button type="button" onClick={() => onZoom(shelf)} className="mt-1 block overflow-hidden rounded-lg border transition-shadow hover:shadow-md" title={t("journeyShelfHint")}>
            <img src={shelf} alt={t("journeyShelfAlt", { rack: s.rack })} loading="lazy" className="h-16 w-auto" />
          </button>
        )}
      </div>
    </li>
  );
}
