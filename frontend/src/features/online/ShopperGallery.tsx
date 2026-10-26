// Every virtual shopper of a run as a card: who they are, how their visit to each store ended, and one click to
// watch a visit play back or two stores side by side.

import { useState } from "react";
import { Columns2, ListOrdered, Play, Search } from "lucide-react";

import type { OnlineRunResult, OnlineShopper, VisitBrief } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { personaLabel } from "@/shared/i18n/personaLabels";

import { Swatch } from "./charts";
import { DEVICE_LABELS, MISSION_LABELS, OUTCOME_COLORS, OUTCOME_LABELS } from "./labels";

type Filter = "all" | "bought" | "left" | "changed" | "rival";
const FILTERS: { id: Filter; label: MessageKey; test: (visits: VisitBrief[]) => boolean }[] = [
  { id: "all", label: "onCardsAll", test: () => true },
  { id: "bought", label: "onCardsBought", test: (v) => v.some((x) => x.outcome === "purchased") },
  { id: "left", label: "onCardsLeft", test: (v) => v.some((x) => x.outcome !== "purchased") },
  { id: "changed", label: "onCardsChanged", test: (v) => new Set(v.map((x) => x.outcome)).size > 1 },
  { id: "rival", label: "onCardsRival", test: (v) => v.some((x) => x.rival !== null) },
];
const PAGE = 12;

function initials(identity: string): string {
  return identity.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
}

export function ShopperGallery({ result, money, onWatch, onCompare, onSteps }: {
  result: OnlineRunResult;
  money: (amount: number) => string;
  onWatch: (variant: number, shopperId: string) => void;
  onCompare: (variant: number, shopperId: string) => void;
  onSteps: (variant: number, shopperId: string) => void;
}) {
  const { t } = useI18n();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const visits = result.visits ?? {};
  const known = Object.keys(visits).length > 0;
  const stores = result.variants.map((s) => s.site_name);
  const words = query.trim().toLowerCase();
  const describe = (sh: OnlineShopper) =>
    [sh.identity, sh.id, t(MISSION_LABELS[sh.mission]), personaLabel(sh.age_group, t), personaLabel(sh.gender, t), t(DEVICE_LABELS[sh.device])]
      .join(" ").toLowerCase();
  const passes = (sh: OnlineShopper, f: Filter) => f === "all" || (known && FILTERS.find((x) => x.id === f)!.test(visits[sh.id] ?? []));
  const found = result.shoppers.filter((sh) => !words || describe(sh).includes(words));
  const shown = found.filter((sh) => passes(sh, filter));
  const filters = FILTERS.filter((f) => f.id === "all" || (known && (f.id !== "changed" || stores.length > 1) && (f.id !== "rival" || result.rival_name)));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex flex-wrap gap-1" role="group" aria-label={t("onCardsFilter")}>
          {filters.map((f) => (
            <button key={f.id} type="button" aria-pressed={filter === f.id} onClick={() => { setFilter(f.id); setLimit(PAGE); }}
              className={cn("rounded-full border px-3 py-1 text-xs transition-colors",
                filter === f.id ? "border-primary bg-primary text-primary-foreground shadow-sm" : "bg-card/60 hover:bg-muted")}>
              {t(f.label)} <span className="ml-1 rounded-full bg-current/10 px-1.5 tabular-nums">{found.filter((sh) => passes(sh, f.id)).length}</span>
            </button>
          ))}
        </div>
        <label className="relative ml-auto w-full max-w-60">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={query} onChange={(e) => { setQuery(e.target.value); setLimit(PAGE); }} placeholder={t("onCardsSearch")}
            aria-label={t("onCardsSearch")} className="h-8 pl-8 text-xs" />
        </label>
      </div>

      {shown.length === 0 ? <p className="text-xs text-muted-foreground">{t("onCardsNone")}</p> : (
        // On a phone the cards are one swipeable row, so the rest of the report is not thousands of pixels away.
        <ul className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2 sm:grid sm:snap-none sm:grid-cols-2 sm:overflow-visible sm:pb-0 xl:grid-cols-3">
          {shown.slice(0, limit).map((sh) => {
            const v = visits[sh.id];
            const differs = v ? v.findIndex((x, i) => i > 0 && x.outcome !== v[0]!.outcome) : -1;
            return (
              <li key={sh.id} className="group relative flex w-[85%] shrink-0 snap-start flex-col gap-2.5 overflow-hidden rounded-2xl border bg-card/70 p-3 shadow-sm transition-[transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:shadow-lg sm:w-auto">
                <div className="pointer-events-none absolute -top-10 -right-10 size-28 rounded-full opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-40 heat-gradient" aria-hidden />
                <div className="flex items-center gap-2.5">
                  <span className="heat-gradient grid size-10 shrink-0 place-items-center rounded-full text-sm font-semibold text-white shadow-inner" aria-hidden>{initials(sh.identity)}</span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold" title={sh.identity}>{sh.identity}</div>
                    <div className="truncate text-[0.7rem] text-muted-foreground">
                      {personaLabel(sh.age_group, t)} · {personaLabel(sh.gender, t)} · {t(DEVICE_LABELS[sh.device])}
                    </div>
                  </div>
                  <span className="hidden shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[0.7rem] font-medium text-primary sm:inline">{t(MISSION_LABELS[sh.mission])}</span>
                </div>
                {/* On a phone card the mission leads the goal line, leaving the name the header's width. */}
                <p className="line-clamp-2 text-xs text-muted-foreground" title={sh.goal}>
                  <span className="mr-1.5 rounded-full bg-primary/10 px-2 py-0.5 text-[0.7rem] font-medium text-primary sm:hidden">{t(MISSION_LABELS[sh.mission])}</span>
                  {sh.goal}
                </p>
                <ul className="space-y-1">
                  {stores.map((store, i) => (
                    <li key={i} className="flex items-center gap-2 rounded-lg bg-muted/40 px-2 py-1 text-xs">
                      <Swatch index={i} />
                      <span className="min-w-0 flex-1 truncate">{store}</span>
                      {v?.[i] && <Outcome brief={v[i]} rival={result.rival_name ?? ""} money={money} />}
                      <button type="button" onClick={() => onWatch(i, sh.id)} aria-label={t("onCardsWatchStore", { store })}
                        className="grid size-6 shrink-0 place-items-center rounded-full border bg-card transition-colors hover:border-primary hover:text-primary">
                        <Play className="size-3" aria-hidden />
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="mt-auto flex flex-wrap gap-1.5">
                  <Button size="sm" className="gap-1.5" onClick={() => onWatch(0, sh.id)} aria-label={t("onCardsWatch", { shopper: sh.identity })}>
                    <Play aria-hidden /> {t("onCardsWatchShort")}
                  </Button>
                  {stores.length > 1 && (
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={() => onCompare(differs > 0 ? differs : 1, sh.id)}>
                      <Columns2 aria-hidden /> {t("onSideBySide")}
                    </Button>
                  )}
                  <Button size="icon-sm" variant="ghost" className="ml-auto" onClick={() => onSteps(0, sh.id)} aria-label={t("onPlaySteps")} title={t("onPlaySteps")}>
                    <ListOrdered aria-hidden />
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {shown.length > limit && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => setLimit((n) => n + PAGE * 2)}>{t("onCardsMore", { count: Math.min(PAGE * 2, shown.length - limit) })}</Button>
        </div>
      )}
    </div>
  );
}

function Outcome({ brief, rival, money }: { brief: VisitBrief; rival: string; money: (amount: number) => string }) {
  const { t } = useI18n();
  const title = brief.rival && rival ? t("onRivalThen", { rival, outcome: t(OUTCOME_LABELS[brief.rival]) }) : undefined;
  return (
    <span className="inline-flex shrink-0 items-center gap-1" title={title}>
      <span className={cn("size-2 rounded-full", OUTCOME_COLORS[brief.outcome])} aria-hidden />
      <span>{t(OUTCOME_LABELS[brief.outcome])}</span>
      {brief.order_total > 0 && <span className="text-muted-foreground tabular-nums">· {money(brief.order_total)}</span>}
      {brief.rival && <span className="rounded bg-amber-500/15 px-1 text-[0.68rem]">→ {t(OUTCOME_LABELS[brief.rival])}</span>}
    </span>
  );
}
