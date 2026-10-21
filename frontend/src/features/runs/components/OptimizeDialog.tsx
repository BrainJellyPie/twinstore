// Layout optimization with synthetic shoppers: choose what to improve and what may change, watch
// the search, then judge the result by its validation on fresh customers — the search score is
// optimistic (it was tuned on the same shoppers), the validated number is the one to trust.

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Eye, Loader2, Sparkles, Square, TriangleAlert, Wand2, Zap } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import * as api from "@/shared/api/client";
import type { JudgeSpec, OptimizeAlgorithm, OptimizeObjective, OptimizeScope, OptimizeSpec, OptimizationView, VLMJudgeReport } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { formatPercent } from "@/shared/utils/money";
import { cn } from "@/shared/utils/cn";

import { ModelPicker, type ModelChoice } from "./ModelPicker";
import { useAvailableModels } from "../hooks";

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
  const [judge, setJudge] = useState<JudgeSpec>({ judge: "rule", vlm_customers: 40, top_k: 3, calibrate: true });
  const [modelChoice, setModelChoice] = useState<ModelChoice>({ kind: "default" });
  const { data: scenarios = [] } = useQuery({ queryKey: queryKeys.scenarios(), queryFn: ({ signal }) => api.getScenarios(signal), staleTime: Infinity });
  const models = useAvailableModels(judge.judge === "vlm");
  const available = models.data?.filter((model) => model.vision);
  let modelError: string | null = null;
  if (judge.judge === "vlm" && modelChoice.kind !== "default") {
    if (!available) modelError = models.isError ? "Could not load models. Retry the model list." : "Loading models…";
    else if (modelChoice.kind === "single") {
      modelError = !modelChoice.model ? "Select a vision model."
        : available.some((model) => model.ref === modelChoice.model) ? null : `Unavailable model: ${modelChoice.model}`;
    } else {
      const members = modelChoice.ensemble?.members ?? [];
      if (!members.length) modelError = "Select at least one ensemble model.";
      else if (members.some((member) => !available.some((model) => model.ref === member.model))) modelError = "An ensemble model is unavailable. Remove it or choose another model.";
      else if (members.some((member) => !Number.isFinite(member.weight) || member.weight <= 0)) modelError = "Every ensemble weight must be a positive finite number.";
    }
  }

  const start = useMutation({
    mutationFn: () => api.startOptimization(projectId, setupId, spec, scenarioId, judge.judge === "vlm" ? {
      ...judge,
      model: modelChoice.kind === "single" ? modelChoice.model : null,
      ensemble: modelChoice.kind === "ensemble" && modelChoice.ensemble?.members.length ? modelChoice.ensemble : null,
    } : undefined),
    onSuccess: (s) => { setJobId(s.job_id); setError(null); },
    onError: (e) => setError(String(e)),
  });
  const job = useQuery({
    queryKey: ["projects", projectId, "optimizations", jobId],
    queryFn: ({ signal }) => api.getOptimization(projectId, jobId!, signal),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed", "canceled"].includes(q.state.data.status.status) ? false : 1000),
  });

  const seconds = Math.round((spec.budget * spec.eval_customers) / 300 * 1.2);
  return (
    <div className="min-w-0 space-y-4">
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
          <div>
            <div className="mb-1 text-xs text-muted-foreground">Who picks the winner</div>
            <div className="grid grid-cols-2 gap-2">
              {([
                { id: "rule", icon: Zap, title: "Rule-based shoppers", hint: "Fast. Search and validation by the rule model." },
                { id: "vlm", icon: Eye, title: "Vision shoppers decide", hint: "The rule model only proposes; VLM shoppers walk the best candidates and pick the winner." },
              ] as const).map(({ id, icon: Icon, title, hint }) => (
                <button key={id} type="button" onClick={() => setJudge({ ...judge, judge: id })}
                  className={cn("rounded-lg border p-2.5 text-left text-xs", judge.judge === id ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
                  <div className="flex items-center gap-1.5 font-medium"><Icon className="size-3.5" />{title}</div>
                  <div className="text-muted-foreground">{hint}</div>
                </button>
              ))}
            </div>
          </div>
          {judge.judge === "vlm" && (
            <div className="space-y-3 rounded-xl border bg-muted/30 p-3">
              <ModelPicker engine="vlm_glance" value={modelChoice} onChange={setModelChoice} />
              {modelError && <p id="run-model-error" role="alert" className="text-xs text-destructive">{modelError}</p>}
              <div className="grid grid-cols-1 gap-3 text-xs min-[400px]:grid-cols-2 sm:grid-cols-3">
                <label className="flex flex-col gap-1">
                  <span className="text-muted-foreground">Vision shoppers per layout</span>
                  <Input type="number" min={4} max={400} value={judge.vlm_customers} onChange={(e) => setJudge({ ...judge, vlm_customers: Math.min(400, Math.max(4, Number(e.target.value) || 4)) })} className="h-8" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-muted-foreground">Candidates judged</span>
                  <Input type="number" min={1} max={8} value={judge.top_k} onChange={(e) => setJudge({ ...judge, top_k: Math.min(8, Math.max(1, Number(e.target.value) || 1)) })} className="h-8" />
                </label>
                <label className="flex items-center gap-2 sm:mt-5">
                  <input type="checkbox" checked={judge.calibrate} onChange={(e) => setJudge({ ...judge, calibrate: e.target.checked })} />
                  Calibrate first
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                {judge.calibrate ? "A VLM pilot on the current layout first tunes the rule model to behave like the vision shoppers. " : ""}
                About {(judge.top_k + 1 + (judge.calibrate ? 1 : 0)) * judge.vlm_customers} shopper visits by the VLM — minutes on a cloud model, an hour or more on a small CPU model.
              </p>
            </div>
          )}
          <p className="text-xs text-muted-foreground">Search with the fast rule-based shoppers · about {Math.max(20, seconds)} s{judge.judge === "vlm" ? ", then the vision judging" : ""}.</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={() => { if (modelError === null) start.mutate(); }} disabled={start.isPending || modelError !== null}>
              {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Start
            </Button>
          </div>
        </div>
      )}

      {jobId && job.isPending && <p role="status" className="text-sm text-muted-foreground">Loading optimization status…</p>}
      {jobId && job.isError && <div className="space-y-2 text-sm">
        <p role="alert" className="text-destructive">{job.error instanceof Error ? job.error.message : "Could not load the optimization status. Please try again."}</p>
        <Button variant="outline" disabled={job.isFetching} onClick={() => void job.refetch()}>Retry status</Button>
      </div>}
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
  const cancel = useMutation({ mutationFn: () => api.cancelOptimization(projectId, status.job_id) });
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (status.status !== "running" && status.status !== "pending") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [status.status]);

  if (status.status === "failed" || status.status === "canceled") {
    return (
      <div className="space-y-3 text-sm">
        <p className="flex items-start gap-2 text-destructive"><TriangleAlert className="mt-0.5 size-4 shrink-0" /> {status.status === "canceled" ? "Stopped." : status.error}</p>
        <Button variant="outline" onClick={onRestart}>Back</Button>
      </div>
    );
  }
  if (!result) {
    const ratio = status.budget ? status.evaluations / status.budget : 0;
    const elapsed = (now - Date.parse(status.created_at)) / 1000;
    const phase = status.phase ?? "";
    const label = phase.startsWith("judging") ? `Vision shoppers are walking the candidates… ${phase.replace("judging", "").trim()}`
      : phase === "calibrating" ? "Vision shoppers walk the current layout to calibrate the rule model…"
      : `Trying layouts… ${status.evaluations} / ${status.budget}`;
    return (
      <div className="space-y-3 py-6 text-center text-sm">
        <div className="font-medium">{label}</div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted"><div className="heat-gradient h-full transition-[width]" style={{ width: `${(phase === "calibrating" ? 0.05 : ratio) * 100}%` }} /></div>
        <div className="text-xs text-muted-foreground">
          {elapsed >= 120 ? `${Math.floor(elapsed / 60)} min ${Math.round(elapsed % 60)} s` : `${Math.round(elapsed)} s`}
          {status.best_score != null ? ` · best so far ${status.best_score.toFixed(1)}` : ""}{status.scenario ? ` · ${status.scenario}` : ""}
          {status.judge?.judge === "vlm" ? " · vision judge" : ""}
        </div>
        <Button variant="outline" size="sm" className="gap-1.5" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
          <Square className="size-3.5" /> Stop
        </Button>
        {cancel.error != null && <p role="alert" className="text-destructive">{cancel.error instanceof Error ? cancel.error.message : "Could not stop the optimization. Please try again."}</p>}
      </div>
    );
  }

  const validated = result.validation_relative_improvement;
  const metric = result.validation?.metrics.find((m) => m.metric === result.validation_metric);
  const minimize = status.spec.objective === "walking_distance";
  const significant = metric ? (minimize ? metric.ci_high < 0 : metric.ci_low > 0) : false;
  const validationGain = metric ? (minimize ? -metric.diff : metric.diff) : validated;
  const good = validationGain != null && validationGain > 0 && significant;
  const chart = result.history.map((h) => ({ i: h.iteration, score: h.score, best: h.best_score }));
  const searchGain = minimize ? result.baseline_score - result.best_score : result.best_score - result.baseline_score;
  if (result.judge) {
    return <JudgeView projectId={projectId} report={result.judge} result={result} status={status} apply={apply} onRestart={onRestart} />;
  }
  return (
    <div className="space-y-4 text-sm">
      <div className={cn("rounded-lg border p-3", good ? "tone-good" : "bg-muted/30")}>
        <div className="flex items-center gap-2 font-medium">
          {good ? <CheckCircle2 className="size-4 text-positive" /> : <TriangleAlert className="size-4 text-warn" />}
          Validated on fresh shoppers: {improvementText(validated, validationGain ?? 0, metric?.mean_a ?? 1)}
          {result.validation_prob_better != null && <span className="font-normal text-muted-foreground">· P(better) {formatPercent(result.validation_prob_better, 0)}</span>}
        </div>
        {metric && (
          <div className="mt-1 text-xs text-muted-foreground">
            95 % interval of the difference: {metric.ci_low.toFixed(2)} … {metric.ci_high.toFixed(2)} ({result.validation?.paired_customers.toLocaleString()} paired shoppers)
          </div>
        )}
        <div className="mt-1 text-xs text-muted-foreground">Search score: {improvementText(result.relative_improvement, searchGain, result.baseline_score)} (optimistic — tuned on the search shoppers)</div>
      </div>

      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chart} margin={{ top: 5, right: 10, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="i" tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            <YAxis tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} domain={["auto", "auto"]} />
            <Tooltip contentStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="score" stroke="var(--muted-foreground)" strokeOpacity={0.6} dot={false} strokeWidth={1} name="candidate" isAnimationActive={false} />
            <Line type="stepAfter" dataKey="best" stroke="var(--primary)" dot={false} strokeWidth={2.5} name="best" isAnimationActive={false} />
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
      {apply.error != null && <p role="alert" className="text-sm text-destructive">{apply.error instanceof Error ? apply.error.message : "Could not save the layout. Please try again."}</p>}

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


function JudgeView({ report, result, status, apply, onRestart }: {
  projectId: string;
  report: VLMJudgeReport;
  result: api.OptimizeResult;
  status: api.OptimizationStatus;
  apply: { mutate: () => void; isPending: boolean; error: unknown };
  onRestart: () => void;
}) {
  const winner = report.candidates.find((c) => c.winner);
  const minimize = status.spec.objective === "walking_distance";
  const gain = minimize ? result.baseline_score - result.best_score : result.best_score - result.baseline_score;
  const improved = winner && winner.label !== "baseline" && gain > 0;
  const sure = minimize ? winner?.delta_ci_high != null && winner.delta_ci_high < 0
    : winner?.delta_ci_low != null && winner.delta_ci_low > 0;
  const cal = report.calibration;
  return (
    <div className="space-y-4 text-sm">
      <div className={cn("rounded-xl border p-3", improved && sure ? "tone-good" : improved ? "tone-warn" : "bg-muted/30")}>
        <div className="flex items-center gap-2 font-medium">
          <Eye className="size-4" />
          {improved ? `Vision shoppers prefer ${winner!.label}: ${improvementText(winner!.relative_improvement, gain, result.baseline_score)}` : "Vision shoppers kept the current layout"}
          {winner?.prob_better != null && improved && <span className="font-normal text-muted-foreground">· P(better) {formatPercent(winner.prob_better, 0)}</span>}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          {report.customers} paired vision shoppers per layout · {report.model}
          {report.spearman != null ? ` · rule vs vision ranking agreement ρ = ${report.spearman.toFixed(2)}` : ""}
          {` · ${report.vlm_requests} model calls in ${Math.round(report.seconds / 60)} min`}
        </div>
        {improved && !sure && <div className="mt-1 text-xs">The interval still includes no change — judge with more vision shoppers before relying on it.</div>}
      </div>

      <table className="w-full text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="text-left font-normal">Layout</th>
            <th className="text-right font-normal">Rule model</th>
            <th className="text-right font-normal">Vision shoppers</th>
            <th className="text-right font-normal">vs. now (95 % CI)</th>
            <th className="text-right font-normal">P(better)</th>
          </tr>
        </thead>
        <tbody>
          {report.candidates.map((c) => (
            <tr key={c.label} className={cn("border-t", c.winner && "font-semibold")}>
              <td className="py-1.5">{c.label === "baseline" ? "Current layout" : `Candidate ${c.label}`}{c.winner ? " ★" : ""}</td>
              <td className="text-right tabular-nums">{c.surrogate_score.toFixed(1)} <span className="text-muted-foreground">#{c.surrogate_rank}</span></td>
              <td className="text-right tabular-nums">{c.vlm_score != null ? c.vlm_score.toFixed(1) : "—"} <span className="text-muted-foreground">{c.vlm_rank != null ? `#${c.vlm_rank}` : ""}</span></td>
              <td className="text-right tabular-nums">
                {c.label === "baseline" || c.delta_mean == null ? "—" : `${c.delta_mean >= 0 ? "+" : ""}${c.delta_mean.toFixed(1)} (${c.delta_ci_low?.toFixed(1)} … ${c.delta_ci_high?.toFixed(1)})`}
              </td>
              <td className="text-right tabular-nums">{c.prob_better != null && c.label !== "baseline" ? formatPercent(c.prob_better, 0) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {cal && (
        <div className="rounded-xl border p-3 text-xs">
          <div className="mb-1 font-medium">Rule model calibrated to the vision shoppers</div>
          <div className="grid grid-cols-3 gap-2 tabular-nums">
            <div className="text-muted-foreground">Impulse buys / visitor</div>
            <div>vision {cal.target.impulse_rate.toFixed(2)}</div>
            <div>rule {cal.before.impulse_rate.toFixed(2)} → {cal.after.impulse_rate.toFixed(2)}</div>
            <div className="text-muted-foreground">Impulse revenue share</div>
            <div>vision {formatPercent(cal.target.impulse_revenue_share, 1)}</div>
            <div>rule {formatPercent(cal.before.impulse_revenue_share, 1)} → {formatPercent(cal.after.impulse_revenue_share, 1)}</div>
          </div>
          <div className="mt-1 text-muted-foreground">Mismatch {cal.gap_before.toFixed(2)} → {cal.gap_after.toFixed(2)} over {cal.grid_points} settings.</div>
        </div>
      )}

      {winner && winner.moves.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-muted-foreground">Changes in the winner ({winner.moves.length})</div>
          <ol className="max-h-32 list-decimal space-y-0.5 overflow-y-auto pl-5 text-xs">{winner.moves.map((m, i) => <li key={i}>{m}</li>)}</ol>
        </div>
      )}
      {report.notes.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{report.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      {apply.error != null && <p role="alert" className="text-sm text-destructive">{apply.error instanceof Error ? apply.error.message : "Could not save the layout. Please try again."}</p>}

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onRestart}>Try other settings</Button>
        <Button onClick={() => apply.mutate()} disabled={apply.isPending || !improved || result.applied_moves.length === 0 || !!status.applied_setup_id}>
          {apply.isPending ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
          {status.applied_setup_id ? "Saved as a layout" : "Save the winner as a new layout"}
        </Button>
      </div>
    </div>
  );
}

function improvementText(relative: number | null | undefined, gain: number, baseline: number): string {
  if (baseline === 0) return `${gain >= 0 ? "+" : ""}${gain.toFixed(2)} (absolute change from zero)`;
  return relative == null ? "—" : `${relative >= 0 ? "+" : ""}${(relative * 100).toFixed(1)} %`;
}
