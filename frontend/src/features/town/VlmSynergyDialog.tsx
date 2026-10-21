// Ask the vision shoppers what a neighboring venue does to our store: the demand model says how
// many visitors it brings or takes; paired VLM simulations (with the venue in the shoppers' trip
// context and without it) say how their baskets change.

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Eye, Loader2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import type { SynergyRow, TownDayType, VLMSynergyResult } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { ModelPicker, type ModelChoice } from "@/features/runs/components/ModelPicker";
import { useSimulationStore } from "@/stores/simulationStore";
import { formatMoney, formatPercent } from "@/shared/utils/money";
import { cn } from "@/shared/utils/cn";

export function VlmSynergyDialog({
  projectId, venue, dayType, scenarioId, onOpenChange,
}: {
  projectId: string;
  venue: SynergyRow | null;
  dayType: TownDayType;
  scenarioId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={!!venue} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-[680px]">
        {venue && <Body projectId={projectId} venue={venue} dayType={dayType} scenarioId={scenarioId} />}
      </DialogContent>
    </Dialog>
  );
}

function Body({ projectId, venue, dayType, scenarioId }: { projectId: string; venue: SynergyRow; dayType: TownDayType; scenarioId: string | null }) {
  const [customers, setCustomers] = useState(24);
  const [model, setModel] = useState<ModelChoice>({ kind: "default" });
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = useMutation({
    mutationFn: () => api.startVlmSynergy(projectId, venue.venue_id, {
      customers, day_type: dayType, scenario_id: scenarioId,
      model: model.kind === "single" ? model.model : null,
      ensemble: model.kind === "ensemble" && model.ensemble?.members.length ? model.ensemble : null,
    }),
    onSuccess: (s) => { setJobId(s.job_id); setError(null); },
    onError: (e) => setError(e instanceof Error ? e.message : String(e)),
  });
  const job = useQuery({
    queryKey: ["projects", projectId, "synergy-jobs", jobId],
    queryFn: ({ signal }) => api.getVlmSynergyJob(projectId, jobId!, signal),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed", "canceled"].includes(q.state.data.status.status) ? false : 1500),
  });

  return (
    <div className="space-y-4 text-sm">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2"><Eye className="size-5" /> {venue.name}: what it does to our baskets</DialogTitle>
        <DialogDescription>
          The neighborhood model already estimates how many visitors {venue.name} brings or takes. Here vision shoppers walk our
          store twice — once knowing they came from {venue.name}, once in a neighborhood without it — so you also see how
          their baskets change.
        </DialogDescription>
      </DialogHeader>

      {!jobId && (
        <div className="space-y-3">
          <ModelPicker engine="vlm_glance" value={model} onChange={setModel} />
          <label className="flex items-center gap-3 text-xs">
            <span className="text-muted-foreground">Visitors to simulate</span>
            <Input type="number" min={4} max={400} value={customers} className="h-8 w-24"
              onChange={(e) => setCustomers(Math.min(400, Math.max(4, Number(e.target.value) || 4)))} />
            <span className="text-muted-foreground">Each affected visitor is simulated twice, paired.</span>
          </label>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex justify-end">
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Run vision shoppers
            </Button>
          </div>
        </div>
      )}

      {jobId && job.isPending && <p role="status" className="text-xs text-muted-foreground">Loading shopper status…</p>}
      {jobId && job.isError && <div className="space-y-2">
        <p role="alert" className="text-xs text-destructive">{job.error instanceof Error ? job.error.message : "Could not load the shopper status. Please try again."}</p>
        <Button variant="outline" disabled={job.isFetching} onClick={() => void job.refetch()}>Retry status</Button>
      </div>}
      {jobId && job.data && !job.data.result && (
        <div className="space-y-3 py-6 text-center">
          {job.data.status.status === "failed" ? (
            <p className="text-destructive">{job.data.status.error}</p>
          ) : (
            <>
              <div className="font-medium">
                {job.data.status.phase === "with venue" ? `Shoppers who came from ${venue.name}…`
                  : job.data.status.phase === "without venue" ? `The same shoppers without ${venue.name}…` : "Choosing visitors…"}
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="heat-gradient h-full transition-[width]" style={{ width: `${(job.data.status.total ? job.data.status.done / job.data.status.total : 0.03) * 100}%` }} />
              </div>
              <div className="text-xs text-muted-foreground">{job.data.status.done} / {job.data.status.total} shopper visits</div>
            </>
          )}
        </div>
      )}

      {job.data?.result && <ResultView r={job.data.result} />}
    </div>
  );
}

function ResultView({ r }: { r: VLMSynergyResult }) {
  const currency = useSimulationStore((s) => s.currency);
  const money = (x: number) => formatMoney(x, currency);
  const signed = (x: number, f: (v: number) => string) => `${x >= 0 ? "+" : "−"}${f(Math.abs(x))}`;
  const ci = r.delta_spend_ci_low != null && r.delta_spend_ci_high != null
    ? `95 % CI ${signed(r.delta_spend_ci_low, money)} … ${signed(r.delta_spend_ci_high, money)}` : "";
  const shifts = [...r.category_shifts].sort((a, b) => Math.abs(b.spend_diff) - Math.abs(a.spend_diff)).slice(0, 6);
  const maxShift = Math.max(1, ...shifts.map((s) => Math.abs(s.spend_diff)));
  return (
    <div className="space-y-4">
      <div className={cn("rounded-xl border p-3", r.delta_revenue_per_day >= 0 ? "tone-good" : "tone-bad")}>
        <div className="font-display text-2xl font-bold tabular-nums">{signed(r.delta_revenue_per_day, money)} / day</div>
        <div className="text-xs">
          {signed(r.delta_revenue_from_visitors, money)} from visitors it sends us · {signed(r.delta_revenue_from_baskets, money)} from what they put in their baskets
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Tile label="Visitors / day" value={`${r.delta_visitors >= 0 ? "+" : ""}${r.delta_visitors.toFixed(1)}`} hint={`${r.linked_visitors_from_venue.toFixed(1)} come straight from it`} />
        <Tile label="Spend / visitor" value={signed(r.delta_spend_per_visitor, money)} hint={ci || "—"} />
        <Tile label="Conversion" value={`${r.delta_conversion >= 0 ? "+" : ""}${(r.delta_conversion * 100).toFixed(1)} pp`} hint={`${formatPercent(r.affected_share, 1)} of visitors affected`} />
      </div>
      {shifts.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-muted-foreground">What the affected shoppers buy differently</div>
          <ul className="space-y-1 text-xs">
            {shifts.map((s) => (
              <li key={s.category} className="grid grid-cols-[110px_1fr_70px] items-center gap-2">
                <span className="truncate">{s.category}</span>
                <span className="relative h-2 rounded-full bg-muted">
                  <span className={cn("absolute top-0 h-2 rounded-full", s.spend_diff >= 0 ? "left-1/2 bg-positive" : "right-1/2 bg-negative")}
                    style={{ width: `${(Math.abs(s.spend_diff) / maxShift) * 50}%` }} />
                </span>
                <span className="text-right tabular-nums">{signed(s.spend_diff, money)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {r.examples.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-muted-foreground">Same shopper, two neighborhoods</div>
          <ul className="space-y-2 text-xs">
            {r.examples.slice(0, 3).map((e) => (
              <li key={e.persona_id} className="grid grid-cols-2 gap-2 rounded-lg border p-2">
                <div><div className="text-muted-foreground">With {r.venue_name}</div>“{e.mission_with || "—"}” · {money(e.spend_with)}</div>
                <div><div className="text-muted-foreground">Without</div>“{e.mission_without || "—"}” · {money(e.spend_without)}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        {r.panel_customers} visitors simulated ({r.affected_customers} with a changed trip) · {r.vlm_requests} model calls in {Math.round(r.seconds / 60)} min
        {r.model ? ` · ${r.model}` : ""}
      </p>
      {r.notes.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{r.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border px-2 py-1.5">
      <div className="text-muted-foreground">{label}</div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
      <div className="truncate text-muted-foreground" title={hint}>{hint}</div>
    </div>
  );
}
