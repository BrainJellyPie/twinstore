// Neighborhood workspace: generate a synthetic town or import a real map, try what-ifs (open a
// café next door, a rival store across the street), and see where our customers come from.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, Footprints, Globe2, Loader2, MapPinPlus, MousePointer2, Sparkles, Trash2, Users } from "lucide-react";

import * as api from "@/shared/api/client";
import { StorefrontCard } from "./StorefrontCard";
import { VlmSynergyDialog } from "./VlmSynergyDialog";
import type { SynergyRow, Town, TownArchetype, TownDayType, TownSpec, VenueCategory } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { useAssistStore } from "@/stores/assistStore";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { ModelWaiting } from "@/shared/components/ModelWaiting";

import { TownMap, type MapMode } from "./TownMap";
import { ARCHETYPE_LABELS, BUILDING_COLORS, BUILDING_LABELS, labelOf, SEGMENT_LABELS, VENUE_COLORS, VENUE_LABELS } from "./townStyle";
import { formatPercent } from "@/shared/utils/money";
import { revealOnMount } from "@/shared/utils/focusOnMount";

const NEIGHBOR_CHOICES: VenueCategory[] = ["cafe", "bakery", "pharmacy", "gym", "academy", "pc_room", "restaurant", "laundry"];
const DAY_LABELS: Record<TownDayType, MessageKey> = { weekday: "areaDayWeekday", weekend: "areaDayWeekend", holiday: "areaDayHoliday" };

export function TownPage({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [dayType, setDayType] = useState<TownDayType>("weekday");
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [mode, setMode] = useState<MapMode>("inspect");
  const [placeCategory, setPlaceCategory] = useState<VenueCategory>("cafe");
  const [vlmVenue, setVlmVenue] = useState<SynergyRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  const townQ = useQuery({ queryKey: queryKeys.town(projectId), queryFn: ({ signal }) => api.getTown(projectId, signal) });
  const town = townQ.data ?? null;
  const demandQ = useQuery({
    queryKey: queryKeys.townDemand(projectId, dayType, scenarioId),
    queryFn: ({ signal }) => api.getTownDemand(projectId, dayType, scenarioId, signal),
    enabled: !!town,
  });
  const { data: scenarios = [] } = useQuery({ queryKey: queryKeys.scenarios(), queryFn: ({ signal }) => api.getScenarios({}, signal), staleTime: Infinity });

  const setTown = (t: Town) => {
    qc.setQueryData(queryKeys.town(projectId), t);
    void qc.invalidateQueries({ queryKey: ["projects", projectId, "town", "demand"] });
    setVlmVenue(null);
    setError(null);
  };
  const onError = (e: unknown) => setError(e instanceof Error ? e.message.replace(/^\d+ [^:]*: /, "") : String(e));
  const place = useMutation({
    mutationFn: (p: { x: number; y: number }) => api.addTownVenue(projectId, { category: placeCategory, ...p }),
    onSuccess: setTown,
    onError,
  });
  const remove = useMutation({ mutationFn: (venueId: string) => api.removeTownVenue(projectId, venueId), onSuccess: setTown, onError });
  const analyze = useMutation({
    mutationFn: (context: { town: Town; dayType: TownDayType }) => api.getTownSynergy(projectId, context.dayType),
  });
  const currentAnalysis = analyze.variables?.town === town && analyze.variables?.dayType === dayType;
  const synergy = currentAnalysis ? analyze.data : undefined;
  const analysisPending = currentAnalysis && analyze.isPending;
  const analysisError = currentAnalysis ? analyze.error : null;
  const loadError = townQ.isError ? (
    <div role="alert" className="min-w-0 max-w-md space-y-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
      <p className="font-medium">{t("areaLoadError")}</p>
      <p className="break-words text-muted-foreground">{townQ.error.message}</p>
      <Button variant="outline" disabled={townQ.isFetching} onClick={() => void townQ.refetch()}>{t("studioRetry")}</Button>
    </div>
  ) : null;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto lg:flex-row">
      <h1 className="sr-only">{t("neighborhood")}</h1>
      <div className="relative m-3 h-[28rem] min-w-0 shrink-0 overflow-hidden rounded-[1.6rem] border border-glass-border bg-[var(--map-ground)] shadow-[var(--shadow-lift)] lg:mr-0 lg:h-auto lg:min-h-64 lg:flex-1">
        {town ? (
          <>
            <TownMap
              town={town}
              demand={demandQ.data}
              mode={mode}
              onPlace={(x, y) => place.mutate({ x, y })}
              onRemove={(v) => remove.mutate(v.id)}
            />
            <MapToolbar mode={mode} setMode={setMode} category={placeCategory} setCategory={setPlaceCategory} busy={place.isPending || remove.isPending} />
            <Legend />
          </>
        ) : loadError ? (
          <div className="flex h-full items-center justify-center p-4">{loadError}</div>
        ) : (
          <div className="dot-grid relative flex h-full flex-col items-center justify-center gap-5 text-center">
            <svg viewBox="0 0 220 140" className="w-72 opacity-90" aria-hidden>
              <defs>
                <linearGradient id="town-aurora" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0" stopColor="var(--heat-1)" /><stop offset="0.5" stopColor="var(--heat-2)" /><stop offset="1" stopColor="var(--heat-3)" />
                </linearGradient>
              </defs>
              <path d="M0 95 L220 60 M30 0 L80 140 M140 0 L170 140" stroke="var(--map-road)" strokeWidth="9" fill="none" strokeLinecap="round" />
              {[[20, 30], [100, 20], [180, 25], [40, 110], [120, 100], [195, 100]].map(([x, y], i) => (
                <rect key={i} x={x} y={y} width="22" height="16" rx="3" fill="var(--map-road-minor)" stroke="var(--map-building-stroke)" strokeOpacity="0.4" />
              ))}
              <circle cx="110" cy="72" r="40" fill="url(#town-aurora)" opacity="0.18" />
              <circle cx="110" cy="72" r="22" fill="url(#town-aurora)" opacity="0.3" />
              <rect x="101" y="63" width="18" height="18" rx="4" fill="var(--map-focal)" />
            </svg>
            <div>
              <div className="font-display text-2xl">{townQ.isLoading ? t("studioLoading") : t("areaEmptyTitle")}</div>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">{t("areaEmptyBody")}</p>
            </div>
          </div>
        )}
      </div>

      <aside className="panel m-3 mt-0 flex min-w-0 shrink-0 flex-col gap-4 rounded-[1.6rem] p-4 text-sm lg:mt-3 lg:w-[400px] lg:overflow-y-auto">
        <Link to="/projects/$pid" params={{ pid: projectId }} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3" /> {t("areaBackToStore")}
        </Link>
        {town && <TownSummary town={town} />}
        {town && loadError}
        {error && <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">{error}</p>}
        {(townQ.isSuccess || town) && <>
          <GeneratePanel projectId={projectId} onDone={setTown} onError={onError} hasTown={!!town} />
          <ImportPanel projectId={projectId} onDone={setTown} onError={onError} hasTown={!!town} />
        </>}

        {town && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{t("areaOurCustomers")}</h3>
              <div className="inline-flex rounded-md border p-0.5 text-xs">
                {(["weekday", "weekend", "holiday"] as TownDayType[]).map((d) => (
                  <button key={d} type="button" aria-pressed={dayType === d} onClick={() => { setDayType(d); setVlmVenue(null); }} className={cn("rounded px-2 py-0.5", dayType === d ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
                    {t(DAY_LABELS[d])}
                  </button>
                ))}
              </div>
            </div>
            <select className="h-8 w-full rounded-md border bg-background px-2 text-xs" value={scenarioId ?? ""} onChange={(e) => setScenarioId(e.target.value || null)} aria-label={t("areaSituation")}>
              <option value="">{t("areaOrdinaryDay")}</option>
              {scenarios.filter((s) => s.scenario.id !== "baseline").map((s) => (
                <option key={s.scenario.id} value={s.scenario.id}>{s.scenario.name}</option>
              ))}
            </select>
            {demandQ.data ? <DemandView demand={demandQ.data} /> : demandQ.isPending ? <p className="text-xs text-muted-foreground">{t("areaEstimating")}</p> : null}
            {demandQ.isError && <div role="alert" className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs">
              <p>{t("areaDemandError")}</p>
              <p className="break-words text-muted-foreground">{demandQ.error.message}</p>
              <Button size="sm" variant="outline" disabled={demandQ.isFetching} onClick={() => void demandQ.refetch()}>{t("areaRetryEstimate")}</Button>
            </div>}
          </section>
        )}

        {town && <StorefrontCard projectId={projectId} town={town} onTown={setTown} />}

        {town && (
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{t("areaSynergyTitle")}</h3>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => { setVlmVenue(null); analyze.mutate({ town, dayType }); }} disabled={analysisPending}>
                {analysisPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} {t("areaAnalyze")}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{t("areaSynergyHint")}</p>
            {analysisError && <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">{analysisError.message}</p>}
            {synergy && <SynergyTable rows={synergy} onAskShoppers={setVlmVenue} />}
          </section>
        )}
        <VlmSynergyDialog projectId={projectId} venue={vlmVenue && synergy?.includes(vlmVenue) ? vlmVenue : null} dayType={dayType} scenarioId={scenarioId}
          onOpenChange={(o) => { if (!o) setVlmVenue(null); }} />
      </aside>
    </div>
  );
}

function MapToolbar({
  mode, setMode, category, setCategory, busy,
}: { mode: MapMode; setMode: (m: MapMode) => void; category: VenueCategory; setCategory: (c: VenueCategory) => void; busy: boolean }) {
  const { t } = useI18n();
  const btn = (m: MapMode, Icon: typeof MousePointer2, label: string) => (
    <button type="button" aria-pressed={mode === m} onClick={() => setMode(m)} className={cn("flex items-center gap-1 rounded px-2 py-1", mode === m ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
      <Icon className="size-3.5" aria-hidden /> {label}
    </button>
  );
  return (
    <div className="absolute left-3 right-3 top-3 flex flex-wrap items-center gap-1 glass rounded-xl border p-1 text-sm shadow-float lg:left-6 lg:right-auto lg:top-6 lg:max-w-[calc(100%-3rem)]">
      {btn("inspect", MousePointer2, t("areaModeExplore"))}
      {btn("place", MapPinPlus, t("areaModeOpen"))}
      {mode === "place" && (
        <select className="h-7 max-w-full rounded border bg-background px-1" value={category} onChange={(e) => setCategory(e.target.value as VenueCategory)} aria-label={t("areaVenueType")}>
          {(Object.keys(VENUE_LABELS) as VenueCategory[]).map((c) => <option key={c} value={c}>{t(VENUE_LABELS[c])}</option>)}
        </select>
      )}
      {btn("remove", Trash2, t("areaModeClose"))}
      {busy && <Loader2 className="mx-1 size-3.5 animate-spin" />}
    </div>
  );
}

function Legend() {
  const { t } = useI18n();
  const venues: VenueCategory[] = ["convenience", "cafe", "bakery", "pharmacy", "gym", "academy", "restaurant", "supermarket"];
  return (
    <div className="absolute bottom-3 left-3 right-3 max-w-[560px] rounded-xl border bg-card/95 p-2.5 text-xs shadow-float backdrop-blur-md lg:bottom-6 lg:left-6 lg:right-6">
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        <span className="flex items-center gap-1"><span className="size-3 rounded-full bg-[var(--map-focal)] ring-2 ring-background" /> {t("areaOurStore")}</span>
        {venues.map((c) => (
          <span key={c} className="flex items-center gap-1"><span className="size-2.5 rounded-full" style={{ background: VENUE_COLORS[c] }} />{t(VENUE_LABELS[c])}</span>
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
        {["apartment", "house", "studio", "office", "school", "university", "station", "park"].map((k) => (
          <span key={k} className="flex items-center gap-1"><span className="size-2.5 rounded-sm" style={{ background: BUILDING_COLORS[k] }} />{labelOf(BUILDING_LABELS, k, t)}</span>
        ))}
        <span>{t("areaLegendRings")}</span>
      </div>
    </div>
  );
}

function TownSummary({ town }: { town: Town }) {
  const { t, locale } = useI18n();
  const sum = (f: (b: Town["buildings"][number]) => number) => town.buildings.reduce((a, b) => a + f(b), 0);
  const rivals = town.venues.filter((v) => v.category === "convenience" && !v.is_focal).length;
  return (
    <section className="rounded-lg border bg-card p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium">{town.name}</div>
          <div className="text-xs text-muted-foreground">
            {labelOf(ARCHETYPE_LABELS, town.archetype, t)} · {Math.round(town.size_m)} m · {town.source === "osm" ? "OpenStreetMap" : t("areaGenerated")}
          </div>
        </div>
        <Users className="size-4 text-muted-foreground" />
      </div>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
        {([
          ["areaResidents", sum((b) => b.residents)], ["areaWorkers", sum((b) => b.workers)], ["areaStudents", sum((b) => b.students)],
          ["areaBuildings", town.buildings.length], ["areaVenues", town.venues.length], ["areaRivalStores", rivals],
        ] as const).map(([k, v]) => (
          <div key={k}>
            <dt className="text-muted-foreground">{t(k)}</dt>
            <dd className="font-medium tabular-nums">{v.toLocaleString(locale)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function GeneratePanel({ projectId, onDone, onError, hasTown }: { projectId: string; onDone: (t: Town) => void; onError: (e: unknown) => void; hasTown: boolean }) {
  const { t } = useI18n();
  const [spec, setSpec] = useState<TownSpec>({ archetype: "residential", size_m: 800, density: 0.5, n_competitors: null, neighbor_categories: ["cafe"], seed: 1 });
  const gen = useMutation({ mutationFn: () => api.generateTown(projectId, spec), onSuccess: onDone, onError });
  const replace = useReplaceConfirm(hasTown);
  // "Describe the area": the text model fills the form below; generating stays a separate, explicit step.
  const [area, setArea] = useState("");
  const areaLength = Array.from(area.trim()).length;
  const [described, setDescribed] = useState<{
    text: string; projectId: string; spec: TownSpec; rationale: string;
  } | null>(null);
  const describe = useMutation({
    mutationFn: (text: string) => api.describeTown(projectId, { text: text.trim(), seed: spec.seed }),
  });
  const resetDescription = describe.reset;
  useLayoutEffect(() => {
    resetDescription();
  }, [area, spec, projectId, resetDescription]);
  const requestDescription = (text: string, replacePending = false) => {
    if (Array.from(text.trim()).length >= 5 && (!describe.isPending || replacePending)) describe.mutate(text, {
      onSuccess: (r) => {
        setDescribed({ ...r, text, projectId });
        setSpec(r.spec);
      },
    });
  };
  const rationale = described?.text === area && described.projectId === projectId
    && described.spec === spec ? described.rationale : "";
  // Routed descriptions use the same ownership rules as descriptions entered here.
  const panel = useRef<HTMLDetailsElement>(null);
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  const queueDescribe = useQueuedStart((text: string) => requestDescription(text, true));
  useEffect(() => {
    if (!pendingAsk) return;
    const routed = takeAsk(projectId, ["area"]);
    if (!routed) return;
    const text = Array.from(routed.text).slice(0, 800).join("");
    setArea(text);
    if (panel.current) {
      panel.current.open = true;
      panel.current.scrollIntoView?.({ block: "nearest" });
    }
    queueDescribe(text);
  }, [pendingAsk, projectId, takeAsk, queueDescribe]);
  const neighborChoices = [...new Set([...NEIGHBOR_CHOICES, ...spec.neighbor_categories])];
  return (
    <details ref={panel} className="rounded-lg border p-3" open={!hasTown}>
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium"><Sparkles className="size-4" /> {t("areaGenerateTitle")}</summary>
      <div className="mt-3 space-y-2 text-xs">
        <div className="space-y-1.5">
          <textarea value={area} onChange={(e) => setArea(Array.from(e.target.value).slice(0, 800).join(""))} rows={3} aria-label={t("areaDescribeLabel")}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) { e.preventDefault(); requestDescription(area); } }}
            placeholder={t("areaDescribePlaceholder")}
            className="block w-full resize-y rounded-lg border bg-background px-2.5 py-2 text-sm leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
          <div className="flex items-center justify-end gap-2">
            <span className="text-muted-foreground tabular-nums">{Array.from(area).length}/800</span>
            <Button type="button" size="sm" disabled={areaLength < 5 || describe.isPending} onClick={() => requestDescription(area)}>
              {describe.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} {t("areaSetUp")}
            </Button>
          </div>
        </div>
        {rationale && <p className="text-muted-foreground">{rationale} {t("areaCheckSettings")}</p>}
        {describe.error && <p role="alert" className="text-destructive">{describe.error.message}</p>}
        <select className="h-8 w-full rounded-md border bg-background px-2" value={spec.archetype} onChange={(e) => setSpec({ ...spec, archetype: e.target.value as TownArchetype })} aria-label={t("areaArchetype")}>
          {Object.entries(ARCHETYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
        </select>
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">{t("areaSize")}</span>
          <input type="range" min={200} max={3000} step={50} value={spec.size_m} onChange={(e) => setSpec({ ...spec, size_m: Number(e.target.value) })} className="flex-1 accent-primary" />
          <span className="w-14 text-right tabular-nums">{spec.size_m} m</span>
        </label>
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">{t("areaDensity")}</span>
          <input type="range" min={0} max={1} step={0.01} value={spec.density} onChange={(e) => setSpec({ ...spec, density: Number(e.target.value) })} className="flex-1 accent-primary"
            aria-valuetext={formatPercent(spec.density, 0)} />
          <span className="w-14 text-right tabular-nums">{formatPercent(spec.density, 0)}</span>
        </label>
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">{t("areaRivals")}</span>
          <Input type="number" min={0} max={60} placeholder={t("areaAuto")} aria-label={t("areaRivals")} value={spec.n_competitors ?? ""} onChange={(e) => setSpec({ ...spec, n_competitors: e.target.value === "" ? null : Math.min(60, Math.max(0, Math.trunc(Number(e.target.value)))) })} className="h-7 w-20 text-xs" />
          <span className="w-14 text-muted-foreground">{t("areaSeed")}</span>
          <Input type="number" aria-label={t("areaSeed")} value={spec.seed} onChange={(e) => setSpec({ ...spec, seed: Math.trunc(Number(e.target.value) || 0) })} className="h-7 w-20 text-xs" />
        </label>
        <div>
          <div className="mb-1 text-muted-foreground">{t("areaNextToUs")}</div>
          <div className="flex flex-wrap gap-1">
            {neighborChoices.map((c) => {
              const on = spec.neighbor_categories.includes(c);
              return (
                <button key={c} type="button" aria-pressed={on} onClick={() => setSpec({ ...spec, neighbor_categories: on ? spec.neighbor_categories.filter((x) => x !== c) : [...spec.neighbor_categories, c] })}
                  className={cn("rounded-full border px-2 py-0.5", on ? "border-primary bg-primary/10" : "hover:bg-muted")}>
                  {t(VENUE_LABELS[c])}
                </button>
              );
            })}
          </div>
        </div>
        <Button size="sm" className="w-full" variant={replace.armed ? "destructive" : "default"} onBlur={replace.disarm}
          onClick={() => replace.confirm(() => gen.mutate())} disabled={gen.isPending}>
          {gen.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}{" "}
          {replace.armed ? t("areaReplaceConfirm") : hasTown ? t("areaRegenerate") : t("areaGenerate")}
        </Button>
        {replace.armed && <p role="status" className="text-muted-foreground">{t("areaReplaceHint")}</p>}
      </div>
    </details>
  );
}

/** Replacing a neighborhood loses its what-if venues and storefront ratings: with one on the map, the first click
 * only asks (the button says so) and a second click replaces it; leaving the button cancels. */
function useReplaceConfirm(hasTown: boolean) {
  const [armed, setArmed] = useState(false);
  return {
    armed: armed && hasTown,
    disarm: () => setArmed(false),
    confirm: (run: () => void) => {
      if (hasTown && !armed) { setArmed(true); return; }
      setArmed(false);
      run();
    },
  };
}

function ImportPanel({ projectId, onDone, onError, hasTown }: { projectId: string; onDone: (t: Town) => void; onError: (e: unknown) => void; hasTown: boolean }) {
  const { t } = useI18n();
  const [address, setAddress] = useState("");
  const [radius, setRadius] = useState(600);
  const imp = useMutation({ mutationFn: () => api.importTownFromMap(projectId, { address, radius_m: radius }), onSuccess: onDone, onError });
  const replace = useReplaceConfirm(hasTown);
  return (
    <details className="rounded-lg border p-3">
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium"><Globe2 className="size-4" /> {t("areaRealMap")}</summary>
      <div className="mt-3 space-y-2 text-xs">
        <Input placeholder={t("areaAddressPlaceholder")} aria-label={t("address")} value={address} onChange={(e) => setAddress(e.target.value)} className="h-8 text-xs" />
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">{t("areaRadius")}</span>
          <input type="range" min={200} max={1500} step={50} value={radius} onChange={(e) => setRadius(Number(e.target.value))} className="flex-1 accent-primary" />
          <span className="w-14 text-right tabular-nums">{radius} m</span>
        </label>
        <Button size="sm" variant={replace.armed ? "destructive" : "outline"} className="w-full" onBlur={replace.disarm}
          onClick={() => replace.confirm(() => imp.mutate())} disabled={!address.trim() || imp.isPending}>
          {imp.isPending ? <Loader2 className="size-3 animate-spin" /> : <Globe2 className="size-3" />}{" "}
          {replace.armed ? t("areaReplaceConfirm") : t("areaImport")}
        </Button>
        {replace.armed && <p role="status" className="text-muted-foreground">{t("areaReplaceHint")}</p>}
        {imp.isPending && <p role="status"><ModelWaiting label={t("areaImporting")} hint={t("areaImportSlow")} /></p>}
        <p className="text-muted-foreground">{t("areaImportHint")}</p>
      </div>
    </details>
  );
}

function DemandView({ demand }: { demand: api.TownDemand }) {
  const { t, locale } = useI18n();
  const hours = demand.hourly_totals;
  const peak = Math.max(1, ...hours);
  const segments = Object.entries(demand.segment_totals).filter(([, v]) => v > 0.5).sort((a, b) => b[1] - a[1]);
  const segTotal = segments.reduce((a, [, v]) => a + v, 0) || 1;
  const rivals = demand.store_shares.filter((s) => !s.is_focal).sort((a, b) => b.expected_visitors - a.expected_visitors).slice(0, 5);
  // Zero visitors make every figure below read 0 m, "≈ 1 min" and an empty chart: say so once instead.
  if (Math.round(demand.total_daily_visitors) === 0) {
    return <p role="status" className="rounded-md border px-3 py-2 text-xs text-muted-foreground">{t("areaNoVisitors", { day: t(DAY_LABELS[demand.day_type]) })}</p>;
  }
  return (
    <div className="space-y-3 text-xs">
      <div className="grid grid-cols-2 gap-2">
        <Stat label={t("areaVisitorsPerDay")} value={Math.round(demand.total_daily_visitors).toLocaleString(locale)} hint={t("areaViaNearby", { count: Math.round(demand.linked_visitors) })} />
        <Stat label={t("areaMarketShare")} value={formatPercent(demand.market_share, 1)} hint={t("areaShareHint")} />
        <Stat label={t("areaHalfWithin")} value={`${Math.round(demand.catchment_radius_50_m)} m`} hint={t("areaEightyWithin", { distance: Math.round(demand.catchment_radius_80_m) })} />
        <Stat label={t("areaAvgWalk")} value={`${Math.round(demand.avg_walk_distance_m)} m`} hint={t("areaWalkMinutes", { minutes: Math.max(1, Math.round(demand.avg_walk_distance_m / 80)) })} icon={Footprints} />
      </div>
      <div>
        <div className="mb-1 text-muted-foreground">{t("areaByHour")}</div>
        <div className="flex h-16 items-end gap-px">
          {hours.map((v, h) => (
            <div key={h} className="flex-1 rounded-t bg-primary/70" style={{ height: `${(v / peak) * 100}%` }} title={t("areaHourTitle", { hour: h, count: Math.round(v) })} />
          ))}
        </div>
        <div className="flex justify-between text-[0.72rem] text-muted-foreground"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div>
      </div>
      <div>
        <div className="mb-1 text-muted-foreground">{t("areaWhoComes")}</div>
        {segments.map(([seg, v]) => (
          <div key={seg} className="mb-1 grid grid-cols-[110px_1fr_44px] items-center gap-2">
            <span>{labelOf(SEGMENT_LABELS, seg, t)}</span>
            <span className="h-1.5 rounded-full bg-muted"><span className="block h-1.5 rounded-full bg-primary" style={{ width: `${(v / segTotal) * 100}%` }} /></span>
            <span className="text-right tabular-nums">{Math.round((v / segTotal) * 100)}%</span>
          </div>
        ))}
      </div>
      {rivals.length > 0 && (
        <div>
          <div className="mb-1 text-muted-foreground">{t("areaRivalsTitle")}</div>
          {rivals.map((s) => (
            <div key={s.venue_id} className="flex justify-between gap-2">
              <span className="truncate" title={s.name}>{s.name}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">{t("areaRivalLine", { distance: Math.round(s.distance_m), count: Math.round(s.expected_visitors) })}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, hint, icon: Icon }: { label: string; value: string; hint: string; icon?: typeof Footprints }) {
  return (
    <div className="rounded-md border px-2 py-1.5">
      <div className="flex items-center gap-1 text-muted-foreground">{Icon && <Icon className="size-3" />}{label}</div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
      <div className="line-clamp-2 text-xs text-muted-foreground" title={hint}>{hint}</div>
    </div>
  );
}

function SynergyTable({ rows, onAskShoppers }: { rows: SynergyRow[]; onAskShoppers: (row: SynergyRow) => void }) {
  const { t } = useI18n();
  const sorted = [...rows].sort((a, b) => Math.abs(b.effect_on_focal_visitors) - Math.abs(a.effect_on_focal_visitors));
  return (
    <div ref={revealOnMount} tabIndex={-1} className="max-h-[22rem] overflow-y-auto rounded-md pr-1 outline-offset-4">
    <table className="w-full text-xs">
      <thead className="text-muted-foreground">
        <tr><th className="text-left font-normal">{t("areaColVenue")}</th><th className="text-right font-normal">{t("areaColDistance")}</th><th className="text-right font-normal">{t("areaColEffect")}</th><th /></tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.venue_id} className="border-t">
            <td className="max-w-[170px] truncate py-1" title={r.name}>
              <span className="mr-1 inline-block size-2 rounded-full" style={{ background: VENUE_COLORS[r.category] }} />{r.name}
            </td>
            <td className="text-right tabular-nums text-muted-foreground">{Math.round(r.distance_m)} m</td>
            <td className={cn("text-right tabular-nums", r.role === "complement" ? "text-positive" : r.role === "competitor" ? "text-negative" : "text-muted-foreground")}>
              {r.effect_on_focal_visitors > 0 ? "+" : ""}{Math.round(r.effect_on_focal_visitors)} ({r.effect_on_focal_pct > 0 ? "+" : ""}{formatPercent(r.effect_on_focal_pct / 100, 1)})
            </td>
            <td className="pl-1 text-right">
              <button type="button" onClick={() => onAskShoppers(r)} title={t("areaAskShoppers")}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" aria-label={t("areaVisionCheckFor", { name: r.name })}>
                <Eye className="size-3.5" />
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}
