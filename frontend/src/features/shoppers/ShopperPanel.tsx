// Shoppers tab of a finished run: pick one shopper, follow their path and thoughts step by step, see them in
// 3D, and interview them about the trip afterwards.

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Crosshair, Loader2, MessagesSquare, Route, Search, UsersRound } from "lucide-react";

import { getJourney, interviewKeys } from "@/shared/api/interview";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import type { CustomerResult, Persona, Store } from "@/shared/types/domain";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";
import { parseTimeToSeconds } from "@/features/playback/utils/playback";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationStore } from "@/stores/simulationStore";

import { GroupInterviewPanel } from "./GroupInterview";
import { InterviewChat } from "./InterviewChat";
import { JourneyMap, JourneySteps } from "./JourneyView";
import { shopperRows, sortShoppers, type ShopperSort } from "./shopperStats";

const SORTS: { id: ShopperSort; label: string }[] = [
  { id: "spent", label: "Top spenders" },
  { id: "nothing", label: "Left empty-handed" },
  { id: "impulse", label: "Impulse buys" },
  { id: "longest", label: "Longest visits" },
];

export function ShopperPanel({ projectId, runId, customers, personas, store }: {
  projectId: string; runId: string; customers: CustomerResult[]; personas: Persona[]; store: Store;
}) {
  const currency = useSimulationStore((s) => s.currency);
  const [selected, setSelected] = useState<string | null>(null);
  const [sort, setSort] = useState<ShopperSort>("spent");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(40);
  const rows = useMemo(() => shopperRows(customers, personas), [customers, personas]);
  const list = useMemo(() => sortShoppers(rows, sort, query), [rows, sort, query]);
  const setHighlight = useSimulationStore((s) => s.setHighlightId);
  const [group, setGroup] = useState(false);

  if (selected) {
    return <ShopperDetail projectId={projectId} runId={runId} store={store} sid={selected} customers={customers}
      backLabel={group ? "Group interview" : "All shoppers"} onBack={() => { setSelected(null); setHighlight(null); }} />;
  }
  if (group) {
    return <GroupInterviewPanel projectId={projectId} runId={runId} currency={currency}
      onOpen={(sid) => { setSelected(sid); setHighlight(sid); }} onBack={() => setGroup(false)} />;
  }
  return (
    <div className="space-y-2.5 py-3">
      <button type="button" onClick={() => setGroup(true)}
        className="flex w-full items-center gap-2.5 rounded-2xl border border-dashed border-primary/40 bg-primary/[0.04] px-3 py-2.5 text-left transition-colors hover:border-primary">
        <UsersRound className="size-4 shrink-0 text-primary" />
        <span className="min-w-0">
          <span className="block text-[0.8rem] font-semibold">Group interview</span>
          <span className="block text-[0.7rem] text-muted-foreground">Ask many shoppers one question — e.g. everyone who left empty-handed — and see the themes</span>
        </span>
      </button>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`Search ${rows.length.toLocaleString()} shoppers`} className="h-9 pl-8 text-sm" />
      </div>
      <div className="flex flex-wrap gap-1">
        {SORTS.map((s) => (
          <button key={s.id} type="button" onClick={() => setSort(s.id)}
            className={cn("rounded-full border px-2.5 py-0.5 text-[0.72rem]", sort === s.id ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground hover:border-foreground/25")}>
            {s.label}
          </button>
        ))}
      </div>
      <ul className="space-y-1">
        {list.slice(0, limit).map((r) => (
          <li key={r.id}>
            <button type="button" onClick={() => { setSelected(r.id); setHighlight(r.id); }}
              onPointerEnter={() => setHighlight(r.id)} onPointerLeave={() => setHighlight(null)}
              className="flex w-full items-center gap-2.5 rounded-xl border bg-card/60 px-2.5 py-2 text-left transition-colors hover:border-primary/50">
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-foreground/[0.06] text-[0.68rem] font-semibold">{r.age || "–"}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[0.8rem] font-medium">{r.name}</span>
                <span className="num block text-[0.68rem] text-muted-foreground">Day {r.day} · {r.arrival} · {r.minutes.toFixed(1)} min · {r.stops} stop{r.stops === 1 ? "" : "s"}</span>
              </span>
              <span className="text-right">
                <span className="num block text-[0.8rem] font-semibold">{r.units ? formatMoney(r.spent, currency) : "–"}</span>
                <span className="num block text-[0.68rem] text-muted-foreground">{r.units} item{r.units === 1 ? "" : "s"}{r.impulse ? ` · ${r.impulse} impulse` : ""}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {list.length > limit && <Button variant="ghost" size="sm" className="w-full" onClick={() => setLimit((l) => l + 60)}>Show more ({list.length - limit})</Button>}
      {list.length === 0 && <p className="px-1 text-sm text-muted-foreground">No shopper matches.</p>}
    </div>
  );
}

function ShopperDetail({ projectId, runId, store, sid, customers, backLabel, onBack }: {
  projectId: string; runId: string; store: Store; sid: string; customers: CustomerResult[]; backLabel: string; onBack: () => void;
}) {
  const journey = useQuery({ queryKey: interviewKeys.journey(projectId, runId, sid), queryFn: ({ signal }) => getJourney(projectId, runId, sid, signal) });
  const [tab, setTab] = useState<"journey" | "interview">("journey");
  const [hover, setHover] = useState<number | null>(null);
  const [cited, setCited] = useState<number[] | null>(null);
  const active = useMemo(() => new Set([...(cited ?? []), ...(hover != null ? [hover] : [])]), [cited, hover]);

  const follow = () => {
    const c = customers.find((x) => x.persona_id === sid);
    if (!c) return;
    const sim = useSimulationStore.getState();
    sim.setHighlightId(sid);
    sim.setFollowPersonaId(sid);
    const play = usePlaybackControlStore.getState();
    play.setDay(c.day);
    play.seek(parseTimeToSeconds(c.arrival_time));
    play.play();
  };

  if (!journey.data) {
    return (
      <div className="py-3">
        <Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft className="size-4" /> {backLabel}</Button>
        <div className="grid h-40 place-items-center">{journey.error ? <p className="text-sm text-destructive">{journey.error.message}</p> : <Loader2 className="size-5 animate-spin" />}</div>
      </div>
    );
  }
  const j = journey.data;
  const p = j.persona;
  return (
    <div className="space-y-3 py-3">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" className="-ml-2" onClick={onBack}><ArrowLeft className="size-4" /> {backLabel}</Button>
        <Button variant="outline" size="sm" onClick={follow} title="Jump to this shopper's arrival and highlight them in the store"><Crosshair className="size-4" /> Follow in 3D</Button>
      </div>
      <div className="rounded-2xl border bg-card p-3">
        <div className="text-sm font-semibold">{p.identity}</div>
        <div className="text-[0.72rem] text-muted-foreground">{p.age_group} · {p.gender} · day {j.day} · {j.arrival_time.slice(0, 5)}–{j.leave_time.slice(0, 5)} · {j.engine_type.replace(/_/g, " ")}</div>
        <p className="mt-1.5 line-clamp-3 text-[0.76rem] text-muted-foreground">{p.description}</p>
        <div className="mt-2 grid grid-cols-3 gap-1.5 text-center">
          <Fact label="Came for" value={p.purpose || p.intent || "–"} />
          <Fact label="Budget" value={p.budget_max ? `${formatMoney(p.budget_min, j.currency)}–${formatMoney(p.budget_max, j.currency)}` : "–"} />
          <Fact label="Spent" value={`${formatMoney(j.total_spent, j.currency)} · ${j.units}`} />
        </div>
      </div>
      <JourneyMap journey={j} store={store} active={active} onHover={setHover} />
      <div className="flex rounded-xl bg-foreground/[0.055] p-1">
        {([["journey", "Journey", Route], ["interview", "Interview", MessagesSquare]] as const).map(([id, label, Icon]) => (
          <button key={id} type="button" onClick={() => setTab(id)}
            className={cn("flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 text-[0.8rem] font-medium", tab === id ? "bg-card shadow-sm" : "text-muted-foreground")}>
            <Icon className="size-3.5" /> {label}
          </button>
        ))}
      </div>
      {tab === "journey"
        ? <JourneySteps journey={j} active={active} onHover={setHover} />
        : <InterviewChat projectId={projectId} runId={runId} journey={j} onCite={setCited} />}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-foreground/[0.035] px-1.5 py-1">
      <div className="text-[0.62rem] text-muted-foreground">{label}</div>
      <div className="num truncate text-[0.72rem] font-medium" title={value}>{value}</div>
    </div>
  );
}
