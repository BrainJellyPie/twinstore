// Neighborhood workspace: generate a synthetic town or import a real map, try what-ifs (open a
// café next door, a rival store across the street), and see where our customers come from.

import { useLayoutEffect, useState } from "react";
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

import { TownMap, type MapMode } from "./TownMap";
import { ARCHETYPE_LABELS, BUILDING_COLORS, BUILDING_LABELS, SEGMENT_LABELS, VENUE_COLORS, VENUE_LABELS } from "./townStyle";

const NEIGHBOR_CHOICES: VenueCategory[] = ["cafe", "bakery", "pharmacy", "gym", "academy", "pc_room", "restaurant", "laundry"];

export function TownPage({ projectId }: { projectId: string }) {
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
  const { data: scenarios = [] } = useQuery({ queryKey: queryKeys.scenarios(), queryFn: ({ signal }) => api.getScenarios(signal), staleTime: Infinity });

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
      <p className="font-medium">Could not load neighborhood.</p>
      <p className="break-words text-muted-foreground">{townQ.error.message}</p>
      <Button variant="outline" disabled={townQ.isFetching} onClick={() => void townQ.refetch()}>Retry</Button>
    </div>
  ) : null;

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto lg:flex-row">
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
              <div className="font-display text-2xl">{townQ.isLoading ? "Loading…" : "Place the store in its neighborhood"}</div>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">Generate a town or import a real OpenStreetMap area — homes, offices, schools, stations and rivals — to see who walks in, from where and when.</p>
            </div>
          </div>
        )}
      </div>

      <aside className="panel m-3 mt-0 flex min-w-0 shrink-0 flex-col gap-4 rounded-[1.6rem] p-4 text-sm lg:mt-3 lg:w-[400px] lg:overflow-y-auto">
        <Link to="/projects/$pid" params={{ pid: projectId }} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3" /> Back to store
        </Link>
        {town && <TownSummary town={town} />}
        {town && loadError}
        {error && <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">{error}</p>}
        {analysisError && <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">{analysisError.message}</p>}
        {(townQ.isSuccess || town) && <>
          <GeneratePanel projectId={projectId} onDone={setTown} onError={onError} hasTown={!!town} />
          <ImportPanel projectId={projectId} onDone={setTown} onError={onError} />
        </>}

        {town && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Our store's customers</h3>
              <div className="inline-flex rounded-md border p-0.5 text-xs">
                {(["weekday", "weekend", "holiday"] as TownDayType[]).map((d) => (
                  <button key={d} type="button" onClick={() => { setDayType(d); setVlmVenue(null); }} className={cn("rounded px-2 py-0.5", dayType === d ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
                    {d}
                  </button>
                ))}
              </div>
            </div>
            <select className="h-8 w-full rounded-md border bg-background px-2 text-xs" value={scenarioId ?? ""} onChange={(e) => setScenarioId(e.target.value || null)} aria-label="Situation">
              <option value="">Ordinary day</option>
              {scenarios.filter((s) => s.scenario.id !== "baseline").map((s) => (
                <option key={s.scenario.id} value={s.scenario.id}>{s.scenario.name}</option>
              ))}
            </select>
            {demandQ.data ? <DemandView demand={demandQ.data} /> : demandQ.isPending ? <p className="text-xs text-muted-foreground">Estimating…</p> : null}
            {demandQ.isError && <div role="alert" className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs">
              <p>Could not estimate customer demand.</p>
              <p className="break-words text-muted-foreground">{demandQ.error.message}</p>
              <Button size="sm" variant="outline" disabled={demandQ.isFetching} onClick={() => void demandQ.refetch()}>Retry estimate</Button>
            </div>}
          </section>
        )}

        {town && <StorefrontCard projectId={projectId} town={town} onTown={setTown} />}

        {town && (
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Neighbor synergy</h3>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => { setVlmVenue(null); analyze.mutate({ town, dayType }); }} disabled={analysisPending}>
                {analysisPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} Analyze
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Removes each venue in turn and re-estimates our visitors: complements bring us customers (linked trips), competitors take them.
            </p>
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
  const btn = (m: MapMode, Icon: typeof MousePointer2, label: string) => (
    <button type="button" onClick={() => setMode(m)} className={cn("flex items-center gap-1 rounded px-2 py-1", mode === m ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
      <Icon className="size-3.5" /> {label}
    </button>
  );
  return (
    <div className="absolute left-3 right-3 top-3 flex flex-wrap items-center gap-1 glass rounded-xl border p-1 text-sm shadow-float lg:left-6 lg:right-auto lg:top-6 lg:max-w-[calc(100%-3rem)]">
      {btn("inspect", MousePointer2, "Explore")}
      {btn("place", MapPinPlus, "Open venue")}
      {mode === "place" && (
        <select className="h-7 max-w-full rounded border bg-background px-1" value={category} onChange={(e) => setCategory(e.target.value as VenueCategory)} aria-label="Venue type">
          {(Object.keys(VENUE_LABELS) as VenueCategory[]).map((c) => <option key={c} value={c}>{VENUE_LABELS[c]}</option>)}
        </select>
      )}
      {btn("remove", Trash2, "Close venue")}
      {busy && <Loader2 className="mx-1 size-3.5 animate-spin" />}
    </div>
  );
}

function Legend() {
  const venues: VenueCategory[] = ["convenience", "cafe", "bakery", "pharmacy", "gym", "academy", "restaurant", "supermarket"];
  return (
    <div className="absolute bottom-3 left-3 right-3 max-w-[560px] glass rounded-xl border p-2.5 text-xs shadow-float lg:bottom-6 lg:left-6 lg:right-6">
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        <span className="flex items-center gap-1"><span className="size-3 rounded-full bg-[var(--map-focal)] ring-2 ring-background" /> Our store</span>
        {venues.map((c) => (
          <span key={c} className="flex items-center gap-1"><span className="size-2.5 rounded-full" style={{ background: VENUE_COLORS[c] }} />{VENUE_LABELS[c]}</span>
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
        {["apartment", "house", "studio", "office", "school", "university", "station", "park"].map((k) => (
          <span key={k} className="flex items-center gap-1"><span className="size-2.5 rounded-sm" style={{ background: BUILDING_COLORS[k] }} />{BUILDING_LABELS[k]}</span>
        ))}
        <span>· rings: 50 % / 80 % of customers · lines: where they come from</span>
      </div>
    </div>
  );
}

function TownSummary({ town }: { town: Town }) {
  const sum = (f: (b: Town["buildings"][number]) => number) => town.buildings.reduce((a, b) => a + f(b), 0);
  const rivals = town.venues.filter((v) => v.category === "convenience" && !v.is_focal).length;
  return (
    <section className="rounded-lg border bg-card p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium">{town.name}</div>
          <div className="text-xs text-muted-foreground">
            {ARCHETYPE_LABELS[town.archetype] ?? town.archetype} · {Math.round(town.size_m)} m · {town.source === "osm" ? "OpenStreetMap" : "generated"}
          </div>
        </div>
        <Users className="size-4 text-muted-foreground" />
      </div>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
        {[
          ["Residents", sum((b) => b.residents)], ["Workers", sum((b) => b.workers)], ["Students", sum((b) => b.students)],
          ["Buildings", town.buildings.length], ["Venues", town.venues.length], ["Rival stores", rivals],
        ].map(([k, v]) => (
          <div key={k as string}>
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="font-medium tabular-nums">{(v as number).toLocaleString()}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function GeneratePanel({ projectId, onDone, onError, hasTown }: { projectId: string; onDone: (t: Town) => void; onError: (e: unknown) => void; hasTown: boolean }) {
  const [spec, setSpec] = useState<TownSpec>({ archetype: "residential", size_m: 800, density: 0.5, n_competitors: null, neighbor_categories: ["cafe"], seed: 1 });
  const gen = useMutation({ mutationFn: () => api.generateTown(projectId, spec), onSuccess: onDone, onError });
  // "Describe the area": the text model fills the form below; generating stays a separate, explicit step.
  const [area, setArea] = useState("");
  const areaLength = Array.from(area.trim()).length;
  const [described, setDescribed] = useState<{
    text: string; projectId: string; spec: TownSpec; rationale: string;
  } | null>(null);
  const describe = useMutation({
    mutationFn: () => api.describeTown(projectId, { text: area.trim(), seed: spec.seed }),
  });
  const resetDescription = describe.reset;
  useLayoutEffect(() => {
    resetDescription();
  }, [area, spec, projectId, resetDescription]);
  const requestDescription = () => {
    if (areaLength >= 5 && !describe.isPending) describe.mutate(undefined, {
      onSuccess: (r) => {
        setDescribed({ ...r, text: area, projectId });
        setSpec(r.spec);
      },
    });
  };
  const rationale = described?.text === area && described.projectId === projectId
    && described.spec === spec ? described.rationale : "";
  const neighborChoices = [...new Set([...NEIGHBOR_CHOICES, ...spec.neighbor_categories])];
  return (
    <details className="rounded-lg border p-3" open={!hasTown}>
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium"><Sparkles className="size-4" /> Generate a neighborhood</summary>
      <div className="mt-3 space-y-2 text-xs">
        <div className="flex items-start gap-1.5">
          <textarea value={area} onChange={(e) => setArea(Array.from(e.target.value).slice(0, 800).join(""))} rows={2} aria-label="Describe the area"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) { e.preventDefault(); requestDescription(); } }}
            placeholder="Describe the area: a busy campus street, two rival stores nearby, a café next door…"
            className="min-h-[2.4rem] flex-1 resize-none rounded-md border bg-background px-2 py-1.5 outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
          <Button type="button" size="sm" variant="outline" className="h-[2.4rem] shrink-0" disabled={areaLength < 5 || describe.isPending} onClick={requestDescription}>
            {describe.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} Set up
          </Button>
        </div>
        {rationale && <p className="text-muted-foreground">{rationale} Check the settings, then generate.</p>}
        {describe.error && <p role="alert" className="text-destructive">{describe.error.message}</p>}
        <select className="h-8 w-full rounded-md border bg-background px-2" value={spec.archetype} onChange={(e) => setSpec({ ...spec, archetype: e.target.value as TownArchetype })} aria-label="Archetype">
          {Object.entries(ARCHETYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">Size</span>
          <input type="range" min={200} max={3000} step={50} value={spec.size_m} onChange={(e) => setSpec({ ...spec, size_m: Number(e.target.value) })} className="flex-1 accent-primary" />
          <span className="w-14 text-right tabular-nums">{spec.size_m} m</span>
        </label>
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">Density</span>
          <input type="range" min={0} max={1} step={0.01} value={spec.density} onChange={(e) => setSpec({ ...spec, density: Number(e.target.value) })} className="flex-1 accent-primary" />
          <span className="w-14 text-right tabular-nums">{Math.round(spec.density * 100)} %</span>
        </label>
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">Rivals</span>
          <Input type="number" min={0} max={60} placeholder="auto" value={spec.n_competitors ?? ""} onChange={(e) => setSpec({ ...spec, n_competitors: e.target.value === "" ? null : Number(e.target.value) })} className="h-7 w-20 text-xs" />
          <span className="w-14 text-muted-foreground">Seed</span>
          <Input type="number" value={spec.seed} onChange={(e) => setSpec({ ...spec, seed: Number(e.target.value) || 0 })} className="h-7 w-20 text-xs" />
        </label>
        <div>
          <div className="mb-1 text-muted-foreground">Right next to our store</div>
          <div className="flex flex-wrap gap-1">
            {neighborChoices.map((c) => {
              const on = spec.neighbor_categories.includes(c);
              return (
                <button key={c} type="button" onClick={() => setSpec({ ...spec, neighbor_categories: on ? spec.neighbor_categories.filter((x) => x !== c) : [...spec.neighbor_categories, c] })}
                  className={cn("rounded-full border px-2 py-0.5", on ? "border-primary bg-primary/10" : "hover:bg-muted")}>
                  {VENUE_LABELS[c]}
                </button>
              );
            })}
          </div>
        </div>
        <Button size="sm" className="w-full" onClick={() => gen.mutate()} disabled={gen.isPending}>
          {gen.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} {hasTown ? "Regenerate" : "Generate"}
        </Button>
      </div>
    </details>
  );
}

function ImportPanel({ projectId, onDone, onError }: { projectId: string; onDone: (t: Town) => void; onError: (e: unknown) => void }) {
  const [address, setAddress] = useState("");
  const [radius, setRadius] = useState(600);
  const imp = useMutation({ mutationFn: () => api.importTownFromMap(projectId, { address, radius_m: radius }), onSuccess: onDone, onError });
  return (
    <details className="rounded-lg border p-3">
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium"><Globe2 className="size-4" /> Real map (OpenStreetMap)</summary>
      <div className="mt-3 space-y-2 text-xs">
        <Input placeholder="Address, e.g. 84 Heukseok-ro, Seoul" value={address} onChange={(e) => setAddress(e.target.value)} className="h-8 text-xs" />
        <label className="flex items-center gap-2">
          <span className="w-16 text-muted-foreground">Radius</span>
          <input type="range" min={200} max={1500} step={50} value={radius} onChange={(e) => setRadius(Number(e.target.value))} className="flex-1 accent-primary" />
          <span className="w-14 text-right tabular-nums">{radius} m</span>
        </label>
        <Button size="sm" variant="outline" className="w-full" onClick={() => imp.mutate()} disabled={!address.trim() || imp.isPending}>
          {imp.isPending ? <Loader2 className="size-3 animate-spin" /> : <Globe2 className="size-3" />} Import buildings, shops and roads
        </Button>
        <p className="text-muted-foreground">Needs internet access. Residents are estimated from building footprint × floors.</p>
      </div>
    </details>
  );
}

function DemandView({ demand }: { demand: api.TownDemand }) {
  const hours = demand.hourly_totals;
  const peak = Math.max(1, ...hours);
  const segments = Object.entries(demand.segment_totals).filter(([, v]) => v > 0.5).sort((a, b) => b[1] - a[1]);
  const segTotal = segments.reduce((a, [, v]) => a + v, 0) || 1;
  const rivals = demand.store_shares.filter((s) => !s.is_focal).sort((a, b) => b.expected_visitors - a.expected_visitors).slice(0, 5);
  return (
    <div className="space-y-3 text-xs">
      <div className="grid grid-cols-2 gap-2">
        <Stat label="Visitors / day" value={Math.round(demand.total_daily_visitors).toLocaleString()} hint={`${Math.round(demand.linked_visitors)} via nearby venues`} />
        <Stat label="Market share" value={`${(demand.market_share * 100).toFixed(1)} %`} hint="of convenience trips in town" />
        <Stat label="Half of customers within" value={`${Math.round(demand.catchment_radius_50_m)} m`} hint={`80 % within ${Math.round(demand.catchment_radius_80_m)} m`} />
        <Stat label="Average walk" value={`${Math.round(demand.avg_walk_distance_m)} m`} hint={`≈ ${Math.max(1, Math.round(demand.avg_walk_distance_m / 80))} min`} icon={Footprints} />
      </div>
      <div>
        <div className="mb-1 text-muted-foreground">By hour</div>
        <div className="flex h-16 items-end gap-px">
          {hours.map((v, h) => (
            <div key={h} className="flex-1 rounded-t bg-primary/70" style={{ height: `${(v / peak) * 100}%` }} title={`${h}:00 · ${Math.round(v)} visitors`} />
          ))}
        </div>
        <div className="flex justify-between text-[0.72rem] text-muted-foreground"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div>
      </div>
      <div>
        <div className="mb-1 text-muted-foreground">Who comes</div>
        {segments.map(([seg, v]) => (
          <div key={seg} className="mb-1 grid grid-cols-[110px_1fr_44px] items-center gap-2">
            <span>{SEGMENT_LABELS[seg] ?? seg}</span>
            <span className="h-1.5 rounded-full bg-muted"><span className="block h-1.5 rounded-full bg-primary" style={{ width: `${(v / segTotal) * 100}%` }} /></span>
            <span className="text-right tabular-nums">{Math.round((v / segTotal) * 100)} %</span>
          </div>
        ))}
      </div>
      {rivals.length > 0 && (
        <div>
          <div className="mb-1 text-muted-foreground">Nearby stores competing for the same trips</div>
          {rivals.map((s) => (
            <div key={s.venue_id} className="flex justify-between gap-2">
              <span className="truncate">{s.name}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">{Math.round(s.distance_m)} m · {Math.round(s.expected_visitors)}/day</span>
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
      <div className="truncate text-xs text-muted-foreground">{hint}</div>
    </div>
  );
}

function SynergyTable({ rows, onAskShoppers }: { rows: SynergyRow[]; onAskShoppers: (row: SynergyRow) => void }) {
  const sorted = [...rows].sort((a, b) => Math.abs(b.effect_on_focal_visitors) - Math.abs(a.effect_on_focal_visitors));
  return (
    <div className="max-h-[22rem] overflow-y-auto pr-1">
    <table className="w-full text-xs">
      <thead className="text-muted-foreground">
        <tr><th className="text-left font-normal">Venue</th><th className="text-right font-normal">Dist.</th><th className="text-right font-normal">Effect on us</th><th /></tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.venue_id} className="border-t">
            <td className="max-w-[170px] truncate py-1" title={r.name}>
              <span className="mr-1 inline-block size-2 rounded-full" style={{ background: VENUE_COLORS[r.category] }} />{r.name}
            </td>
            <td className="text-right tabular-nums text-muted-foreground">{Math.round(r.distance_m)} m</td>
            <td className={cn("text-right tabular-nums", r.role === "complement" ? "text-positive" : r.role === "competitor" ? "text-negative" : "text-muted-foreground")}>
              {r.effect_on_focal_visitors > 0 ? "+" : ""}{Math.round(r.effect_on_focal_visitors)} ({r.effect_on_focal_pct > 0 ? "+" : ""}{r.effect_on_focal_pct.toFixed(1)} %)
            </td>
            <td className="pl-1 text-right">
              <button type="button" onClick={() => onAskShoppers(r)} title="Ask vision shoppers how their baskets change"
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" aria-label={`Vision shopper check for ${r.name}`}>
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
