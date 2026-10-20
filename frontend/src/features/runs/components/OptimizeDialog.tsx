// Layout optimization with synthetic shoppers: choose what to improve and what may change, watch
// the search, then judge the result by its validation on fresh customers — the search score is
// optimistic (it was tuned on the same shoppers), the validated number is the one to trust.

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Sparkles, TriangleAlert, Wand2 } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import * as api from "@/shared/api/client";
import type { OptimizeAlgorithm, OptimizeObjective, OptimizeScope, OptimizeSpec, OptimizationView } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { formatPercent } from "@/shared/utils/money";
import { cn } from "@/shared/utils/cn";

const OBJECTIVES: { value: OptimizeObjective; label: string }[] = [
  { value: "revenue_per_visitor", label: "Revenue per visitor" },
  { value: "total_revenue", label: "Total revenue" },
  { value: "impulse_revenue", label: "Impulse revenue" },
  { value: "units_per_visitor", label: "Units per visitor" },
  { value: "conversion_rate", label: "Conversion rate" },
  { value: "walking_distance", label: "Shorter walks (minimize)" },
];
const SCOPES: { value: OptimizeScope; label: string; hint: string }[] = [
  { value: "planogram", label: "Shelves only", hint: "Move products between shelves and levels; racks stay put" },
  { value: "placement", label: "Rack positions", hint: "Move and swap racks; contents travel with them" },
  { value: "both", label: "Both", hint: "Shelves and rack positions" },
];

const DEFAULT_SPEC: OptimizeSpec = {
  objective: "revenue_per_visitor", scope: "planogram", algorithm: "hill_climb", budget: 60, eval_customers: 300,
  validation_customers: null, seed: 0,
  constraints: { keep_fridges_on_walls: true, lock_rack_ids: [], max_moves: 10, min_improvement: 0 },
};

export function OptimizeDialog({
  open, onOpenChange, projectId, setupId,
}: { open: boolean; onOpenChange: (o: boolean) => void; projectId: string; setupId: string }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-[720px]">
        <OptimizeBody projectId={projectId} setupId={setupId} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function OptimizeBody({ projectId, setupId, onClose }: { projectId: string; setupId: string; onClose: () => void }) {
  const [spec, setSpec] = useState<OptimizeSpec>(DEFAULT_SPEC);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: scenarios = [] } = useQuery({ queryKey: queryKeys.scenarios(), queryFn: ({ signal }) => api.getScenarios(signal), staleTime: Infinity });

  const start = useMutation({
    mutationFn: () => api.startOptimization(projectId, setupId, spec, scenarioId),
    onSuccess: (s) => { setJobId(s.job_id); setError(null); },
    onError: (e) => setError(String(e)),
  });
  const job = useQuery({
    queryKey: ["projects", projectId, "optimizations", jobId],
    queryFn: ({ signal }) => api.getOptimization(projectId, jobId!, signal),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status.status) ? false : 1000),
  });

  const seconds = Math.round((spec.budget * spec.eval_customers) / 300 * 1.2);
  return (
    <div className="space-y-4">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2"><Wand2 className="size-5" /> Optimize this layout</DialogTitle>
        <DialogDescription>
          Thousands of synthetic shoppers try candidate layouts; the best one is then re-checked on fresh shoppers. The
          original layout is never changed — the result is saved as a new layout.
        </DialogDescription>
      </DialogHeader>

      {!jobId && (
        <div className="space-y-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Improve</span>
            <select className="h-8 rounded-md border bg-background px-2" value={spec.objective} onChange={(e) => setSpec({ ...spec, objective: e.target.value as OptimizeObjective })}>
              {OBJECTIVES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <div>
            <div className="mb-1 text-xs text-muted-foreground">What may change</div>
            <div className="grid grid-cols-3 gap-2">
              {SCOPES.map((s) => (
                <button key={s.value} type="button" onClick={() => setSpec({ ...spec, scope: s.value })}
                  className={cn("rounded-lg border p-2 text-left text-xs", spec.scope === s.value ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
                  <div className="font-medium">{s.label}</div>
                  <div className="text-muted-foreground">{s.hint}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">Search method</span>
              <select className="h-8 rounded-md border bg-background px-2" value={spec.algorithm} onChange={(e) => setSpec({ ...spec, algorithm: e.target.value as OptimizeAlgorithm })}>
                <option value="hill_climb">Hill climbing (robust)</option>
                <option value="anneal">Simulated annealing</option>
                <option value="genetic">Genetic algorithm</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">Situation</span>
              <select className="h-8 rounded-md border bg-background px-2" value={scenarioId ?? ""} onChange={(e) => setScenarioId(e.target.value || null)}>
                <option value="">Ordinary day</option>
                {scenarios.filter((s) => s.scenario.id !== "baseline").map((s) => <option key={s.scenario.id} value={s.scenario.id}>{s.scenario.name}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">Candidates to try</span>
              <Input type="number" min={6} max={1000} value={spec.budget} onChange={(e) => setSpec({ ...spec, budget: Math.max(1, Number(e.target.value) || 1) })} className="h-8" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">Shoppers per candidate</span>
              <Input type="number" min={50} max={3000} step={50} value={spec.eval_customers} onChange={(e) => setSpec({ ...spec, eval_customers: Math.max(10, Number(e.target.value) || 10) })} className="h-8" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">Max. changes</span>
              <Input type="number" min={1} max={50} value={spec.constraints.max_moves} onChange={(e) => setSpec({ ...spec, constraints: { ...spec.constraints, max_moves: Math.max(1, Number(e.target.value) || 1) } })} className="h-8" />
            </label>
            <label className="mt-5 flex items-center gap-2">
              <input type="checkbox" className="accent-primary" checked={spec.constraints.keep_fridges_on_walls} onChange={(e) => setSpec({ ...spec, constraints: { ...spec.constraints, keep_fridges_on_walls: e.target.checked } })} />
              Fridges stay on walls
            </label>
          </div>
          <p className="text-xs text-muted-foreground">Uses the fast rule-based shoppers · about {Math.max(20, seconds)} s on this machine.</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Start
            </Button>
          </div>
        </div>
      )}

      {jobId && job.data && <JobView projectId={projectId} view={job.data} onClose={onClose} onRestart={() => setJobId(null)} />}
    </div>
  );
}

function JobView({ projectId, view, onClose, onRestart }: { projectId: string; view: OptimizationView; onClose: () => void; onRestart: () => void }) {
  const qc = useQueryClient();
  const setSelectedSetupId = useSimulationStore((s) => s.setSelectedSetupId);
  const { status, result } = view;
  const apply = useMutation({
    mutationFn: () => api.applyOptimization(projectId, status.job_id),
    onSuccess: async (setup) => {
      await qc.invalidateQueries({ queryKey: queryKeys.setups(projectId) });
      setSelectedSetupId(setup.id);
      onClose();
    },
  });
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (status.status !== "running" && status.status !== "pending") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [status.status]);

  if (status.status === "failed") {
    return (
      <div className="space-y-3 text-sm">
        <p className="flex items-start gap-2 text-destructive"><TriangleAlert className="mt-0.5 size-4 shrink-0" /> {status.error}</p>
        <Button variant="outline" onClick={onRestart}>Back</Button>
      </div>
    );
  }
  if (!result) {
    const ratio = status.budget ? status.evaluations / status.budget : 0;
    const elapsed = (now - Date.parse(status.created_at)) / 1000;
    return (
      <div className="space-y-3 py-6 text-center text-sm">
        <div className="font-medium">Trying layouts… {status.evaluations} / {status.budget}</div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-[width]" style={{ width: `${ratio * 100}%` }} /></div>
        <div className="text-xs text-muted-foreground">
          {Math.round(elapsed)} s{status.best_score != null ? ` · best so far ${status.best_score.toFixed(1)}` : ""}{status.scenario ? ` · ${status.scenario}` : ""}
        </div>
      </div>
    );
  }

  const validated = result.validation_relative_improvement;
  const metric = result.validation?.metrics.find((m) => m.metric === result.validation_metric);
  const minimize = status.spec.objective === "walking_distance";
  const significant = metric ? (minimize ? metric.ci_high < 0 : metric.ci_low > 0) : false;
  const good = validated != null && validated > 0 && significant;
  const chart = result.history.map((h) => ({ i: h.iteration, score: h.score, best: h.best_score }));
  const pct = (x: number) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)} %`;
  return (
    <div className="space-y-4 text-sm">
      <div className={cn("rounded-lg border p-3", good ? "border-emerald-300 bg-emerald-50" : "bg-muted/30")}>
        <div className="flex items-center gap-2 font-medium">
          {good ? <CheckCircle2 className="size-4 text-emerald-700" /> : <TriangleAlert className="size-4 text-amber-600" />}
          Validated on fresh shoppers: {validated != null ? pct(validated) : "—"}
          {result.validation_prob_better != null && <span className="font-normal text-muted-foreground">· P(better) {formatPercent(result.validation_prob_better, 0)}</span>}
        </div>
        {metric && (
          <div className="mt-1 text-xs text-muted-foreground">
            95 % interval of the difference: {metric.ci_low.toFixed(2)} … {metric.ci_high.toFixed(2)} ({result.validation?.paired_customers.toLocaleString()} paired shoppers)
          </div>
        )}
        <div className="mt-1 text-xs text-muted-foreground">Search score: {pct(result.relative_improvement)} (optimistic — tuned on the search shoppers)</div>
      </div>

      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chart} margin={{ top: 5, right: 10, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="i" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} />
            <Tooltip contentStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="score" stroke="#94a3b8" dot={false} strokeWidth={1} name="candidate" isAnimationActive={false} />
            <Line type="stepAfter" dataKey="best" stroke="#0e7490" dot={false} strokeWidth={2} name="best" isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {result.baseline_summary && result.best_summary && (
        <table className="w-full text-xs">
          <thead className="text-muted-foreground"><tr><th className="text-left font-normal">Search shoppers</th><th className="text-right font-normal">Now</th><th className="text-right font-normal">Optimized</th></tr></thead>
          <tbody>
            {([
              ["Revenue / visitor", (s: api.RunSummary) => (s.revenue_per_visitor ?? 0).toFixed(0)],
              ["Conversion", (s: api.RunSummary) => formatPercent(s.conversion_rate ?? 0, 1)],
              ["Units / buyer", (s: api.RunSummary) => (s.avg_units_per_buyer ?? 0).toFixed(2)],
              ["Impulse share", (s: api.RunSummary) => formatPercent(s.impulse_revenue_share ?? 0, 1)],
              ["Walk (tiles)", (s: api.RunSummary) => (s.avg_path_tiles ?? 0).toFixed(1)],
            ] as const).map(([label, f]) => (
              <tr key={label} className="border-t"><td className="py-1">{label}</td><td className="text-right tabular-nums">{f(result.baseline_summary!)}</td><td className="text-right tabular-nums">{f(result.best_summary!)}</td></tr>
            ))}
          </tbody>
        </table>
      )}

      <div>
        <div className="mb-1 text-xs text-muted-foreground">Changes ({result.applied_moves.length})</div>
        <ol className="max-h-32 list-decimal space-y-0.5 overflow-y-auto pl-5 text-xs">
          {result.applied_moves.map((m, i) => <li key={i}>{m}</li>)}
        </ol>
      </div>
      {result.notes.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onRestart}>Try other settings</Button>
        <Button onClick={() => apply.mutate()} disabled={apply.isPending || result.applied_moves.length === 0 || !!status.applied_setup_id}>
          {apply.isPending ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
          {status.applied_setup_id ? "Saved as a layout" : "Save as new layout"}
        </Button>
      </div>
    </div>
  );
}
