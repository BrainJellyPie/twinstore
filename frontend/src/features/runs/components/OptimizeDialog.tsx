// Layout optimization with synthetic shoppers: choose what to improve and what may change, watch
// the search, then judge the result by its validation on fresh customers — the search score is
// optimistic (it was tuned on the same shoppers), the validated number is the one to trust.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Eye, Loader2, Sparkles, Square, TriangleAlert, Wand2, Zap } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import * as api from "@/shared/api/client";
import type { JudgeSpec, OptimizeAlgorithm, OptimizeObjective, OptimizeScope, OptimizeSpec, OptimizationView, VLMJudgeReport } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { WholeNumberInput } from "@/shared/components/WholeNumberInput";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { currencyCode, formatMoney, formatPercent, formatDecimal } from "@/shared/utils/money";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import type { Locale, MessageKey } from "@/shared/i18n/messages";
import { translate } from "@/shared/i18n/translate";
import { NeedsModel } from "@/features/settings/NeedsModel";

import { ModelPicker, type ModelChoice } from "./ModelPicker";
import { useAvailableModels } from "../hooks";
import { focusOnMount } from "@/shared/utils/focusOnMount";

const OBJECTIVES: { value: OptimizeObjective; label: MessageKey }[] = [
  { value: "revenue_per_visitor", label: "optObjRevenuePerVisitor" },
  { value: "total_revenue", label: "optObjTotalRevenue" },
  { value: "impulse_revenue", label: "optObjImpulseRevenue" },
  { value: "units_per_visitor", label: "optObjUnitsPerVisitor" },
  { value: "conversion_rate", label: "optObjConversion" },
  { value: "walking_distance", label: "optObjWalking" },
];
const SCOPES: { value: OptimizeScope; label: MessageKey; hint: MessageKey }[] = [
  { value: "planogram", label: "optScopePlanogram", hint: "optScopePlanogramHint" },
  { value: "placement", label: "optScopePlacement", hint: "optScopePlacementHint" },
  { value: "both", label: "optScopeBoth", hint: "optScopeBothHint" },
];

const DEFAULT_SPEC: OptimizeSpec = {
  objective: "revenue_per_visitor", scope: "planogram", algorithm: "hill_climb", budget: 60, eval_customers: 300,
  validation_customers: null, seed: 0,
  constraints: { keep_fridges_on_walls: true, lock_rack_ids: [], max_moves: 10, min_improvement: 0 },
};

export function OptimizeDialog({
  open, onOpenChange, projectId, setupId, goalPrefill,
}: {
  open: boolean; onOpenChange: (o: boolean) => void; projectId: string; setupId: string;
  /** A goal routed from the command palette: filled in and read once. */
  goalPrefill?: { id: number; text: string };
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-[720px]">
        <OptimizeBody key={JSON.stringify([projectId, setupId])} active={open} projectId={projectId} setupId={setupId} goalPrefill={goalPrefill} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function OptimizeBody({ active, projectId, setupId, goalPrefill, onClose }: {
  active: boolean; projectId: string; setupId: string; goalPrefill?: { id: number; text: string }; onClose: () => void;
}) {
  const { t } = useI18n();
  const [spec, setSpec] = useState<OptimizeSpec>(DEFAULT_SPEC);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [judge, setJudge] = useState<JudgeSpec>({ judge: "rule", vlm_customers: 40, top_k: 3, calibrate: true });
  const [modelChoice, setModelChoice] = useState<ModelChoice>({ kind: "default" });
  const { data: scenarios = [] } = useQuery({
    queryKey: queryKeys.scenarios(projectId, setupId), queryFn: ({ signal }) => api.getScenarios({ projectId, setupId }, signal), staleTime: Infinity,
  });
  const models = useAvailableModels(judge.judge === "vlm");
  const available = models.data?.filter((model) => model.vision);
  let modelError: string | null = null;
  if (judge.judge === "vlm" && modelChoice.kind !== "default") {
    if (!available) modelError = models.isError ? t("optModelsFailed") : t("loadingModels");
    else if (modelChoice.kind === "single") {
      modelError = !modelChoice.model ? t("optSelectVision")
        : available.some((model) => model.ref === modelChoice.model) ? null : t("unavailableModel", { model: modelChoice.model });
    } else {
      const members = modelChoice.ensemble?.members ?? [];
      if (!members.length) modelError = t("optNeedEnsemble");
      else if (members.some((member) => !available.some((model) => model.ref === member.model))) modelError = t("optEnsembleUnavailable");
      else if (members.some((member) => !Number.isFinite(member.weight) || member.weight <= 0)) modelError = t("optInvalidWeights");
    }
  }

  // The goal in words sets the objective, what may change, the move limit and the locked shelves.
  const [goal, setGoal] = useState("");
  const [goalRead, setGoalRead] = useState<{ context: string; goal: api.OptimizeGoal } | null>(null);
  const goalContext = (value: OptimizeSpec) => JSON.stringify([projectId, setupId, goal, value, scenarioId, judge, modelChoice]);
  const context = goalContext(spec);
  const reader = useMutation({
    mutationFn: (text: string) => api.readOptimizeGoal(projectId, setupId, text.trim()),
  });
  const { reset: resetReader } = reader;
  useLayoutEffect(() => { resetReader(); }, [context, resetReader]);
  const readGoal = (text: string, replacePending = false) => {
    if (Array.from(text.trim()).length < 5 || (reader.isPending && !replacePending)) return;
    reader.mutate(text, { onSuccess: (g) => {
      const next: OptimizeSpec = {
        ...spec, objective: g.objective, scope: g.scope,
        constraints: {
          ...spec.constraints,
          ...(g.max_moves != null ? { max_moves: g.max_moves } : {}),
          ...(g.keep_fridges_on_walls != null ? { keep_fridges_on_walls: g.keep_fridges_on_walls } : {}),
          ...(g.min_improvement != null ? { min_improvement: g.min_improvement } : {}),
          lock_rack_ids: g.lock_rack_ids,
        },
      };
      setGoalRead({ context: goalContext(next), goal: g });
      setSpec(next);
    } });
  };
  const queueGoal = useQueuedStart((text: string) => readGoal(text, true));
  const [goalHandled, setGoalHandled] = useState<number | null>(null);
  const prefillId = goalPrefill?.id;
  const prefillText = goalPrefill?.text;
  useEffect(() => {
    if (prefillId === undefined || !prefillText || goalHandled === prefillId) return;
    setGoalHandled(prefillId);
    const text = Array.from(prefillText).slice(0, 600).join("");
    setGoal(text);
    queueGoal(text);
  }, [prefillId, prefillText, goalHandled, queueGoal]);
  const goalShown = goalRead?.context === context ? goalRead.goal : null;
  const goalLength = Array.from(goal.trim()).length;

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
        <DialogTitle className="flex items-center gap-2"><Wand2 className="size-5" /> {t("optTitle")}</DialogTitle>
        <DialogDescription>{t("optDescription")}</DialogDescription>
      </DialogHeader>

      {!jobId && (
        <div className="space-y-3 text-sm">
          <div className="space-y-1.5 rounded-lg bg-muted/60 p-2">
            <div className="flex items-center gap-1.5">
              <Sparkles className="ml-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <Input value={goal} onChange={(e) => setGoal(Array.from(e.target.value).slice(0, 600).join(""))}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229 && goalLength >= 5 && !reader.isPending) { e.preventDefault(); readGoal(goal); } }}
                placeholder={t("optGoalPlaceholder")}
                aria-label={t("optGoal")} className="h-8 min-w-0 flex-1 bg-background text-xs" />
              <Button type="button" size="sm" variant="outline" className="h-8 text-xs" disabled={goalLength < 5 || reader.isPending} onClick={() => readGoal(goal)}>
                {reader.isPending ? <Loader2 className="size-3.5 animate-spin" /> : t("optSetUp")}
              </Button>
            </div>
            {reader.error && <p role="alert" className="text-xs text-destructive">{reader.error.message}</p>}
            {reader.error && <div className="basis-full"><NeedsModel purpose="assist" /></div>}
            {goalShown && (
              <div className="space-y-0.5 text-xs text-muted-foreground">
                <p>{goalShown.rationale} {t("optCheckSettings")}</p>
                {goalShown.warnings.map((w) => <p key={w}>· {w}</p>)}
              </div>
            )}
          </div>
          {spec.constraints.lock_rack_ids.length > 0 && (
            <p className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">{t("optLockedShelves")}</span>
              <span>{goalRead?.goal.locked.join(", ") || t("optShelfCount", { count: spec.constraints.lock_rack_ids.length })}</span>
              <button type="button" className="text-primary hover:underline"
                onClick={() => setSpec({ ...spec, constraints: { ...spec.constraints, lock_rack_ids: [] } })}>{t("optUnlockAll")}</button>
            </p>
          )}
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">{t("optImprove")}</span>
            <select className="h-8 rounded-md border bg-background px-2" value={spec.objective} onChange={(e) => setSpec({ ...spec, objective: e.target.value as OptimizeObjective })}>
              {OBJECTIVES.map((o) => <option key={o.value} value={o.value}>{t(o.label)}</option>)}
            </select>
          </label>
          <div>
            <div className="mb-1 text-xs text-muted-foreground">{t("optWhatMayChange")}</div>
            <div className="grid grid-cols-3 gap-2">
              {SCOPES.map((s) => (
                <button key={s.value} type="button" onClick={() => setSpec({ ...spec, scope: s.value })}
                  className={cn("rounded-lg border p-2 text-left text-xs", spec.scope === s.value ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
                  <div className="font-medium">{t(s.label)}</div>
                  <div className="text-muted-foreground">{t(s.hint)}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("optSearchMethod")}</span>
              <select className="h-8 rounded-md border bg-background px-2" value={spec.algorithm} onChange={(e) => setSpec({ ...spec, algorithm: e.target.value as OptimizeAlgorithm })}>
                <option value="hill_climb">{t("optHillClimb")}</option>
                <option value="anneal">{t("optAnneal")}</option>
                <option value="genetic">{t("optGenetic")}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("optSituation")}</span>
              <select className="h-8 rounded-md border bg-background px-2" value={scenarioId ?? ""} onChange={(e) => setScenarioId(e.target.value || null)}>
                <option value="">{t("optOrdinaryDay")}</option>
                {scenarios.filter((s) => s.scenario.id !== "baseline").map((s) => <option key={s.scenario.id} value={s.scenario.id}>{s.scenario.name}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("optCandidatesToTry")}</span>
              <WholeNumberInput min={6} max={1000} value={spec.budget} onChange={(budget) => setSpec({ ...spec, budget })} className="h-8" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("optShoppersPerCandidate")}</span>
              <WholeNumberInput min={50} max={3000} step={50} value={spec.eval_customers} onChange={(eval_customers) => setSpec({ ...spec, eval_customers })} className="h-8" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("optMaxChanges")}</span>
              <WholeNumberInput min={1} max={50} value={spec.constraints.max_moves} onChange={(max_moves) => setSpec({ ...spec, constraints: { ...spec.constraints, max_moves } })} className="h-8" />
            </label>
            <label className="mt-5 flex items-center gap-2">
              <input type="checkbox" className="accent-primary" checked={spec.constraints.keep_fridges_on_walls} onChange={(e) => setSpec({ ...spec, constraints: { ...spec.constraints, keep_fridges_on_walls: e.target.checked } })} />
              {t("optFridgesOnWalls")}
            </label>
          </div>
          <div>
            <div className="mb-1 text-xs text-muted-foreground">{t("optWhoPicks")}</div>
            <div className="grid grid-cols-2 gap-2">
              {([
                { id: "rule", icon: Zap, title: t("optJudgeRule"), hint: t("optJudgeRuleHint") },
                { id: "vlm", icon: Eye, title: t("optJudgeVision"), hint: t("optJudgeVisionHint") },
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
                  <span className="text-muted-foreground">{t("optVisionPerLayout")}</span>
                  <WholeNumberInput min={4} max={400} value={judge.vlm_customers} onChange={(vlm_customers) => setJudge({ ...judge, vlm_customers })} className="h-8" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-muted-foreground">{t("optCandidatesJudged")}</span>
                  <WholeNumberInput min={1} max={8} value={judge.top_k} onChange={(top_k) => setJudge({ ...judge, top_k })} className="h-8" />
                </label>
                <label className="flex items-center gap-2 sm:mt-5">
                  <input type="checkbox" checked={judge.calibrate} onChange={(e) => setJudge({ ...judge, calibrate: e.target.checked })} />
                  {t("optCalibrateFirst")}
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                {judge.calibrate ? `${t("optCalibrateNote")} ` : ""}
                {t("optVlmVisits", { count: (judge.top_k + 1 + (judge.calibrate ? 1 : 0)) * judge.vlm_customers })}
              </p>
            </div>
          )}
          <p className="text-xs text-muted-foreground">{t(judge.judge === "vlm" ? "optSearchTimeVision" : "optSearchTime", { seconds: Math.max(20, seconds) })}</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>{t("cancel")}</Button>
            <Button onClick={() => { if (modelError === null && !reader.isPending) start.mutate(); }} disabled={start.isPending || reader.isPending || modelError !== null}>
              {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {t("optStart")}
            </Button>
          </div>
        </div>
      )}

      {jobId && job.isPending && <p role="status" className="text-sm text-muted-foreground">{t("optLoadingStatus")}</p>}
      {jobId && job.isError && <div className="space-y-2 text-sm">
        <p role="alert" className="text-destructive">{job.error instanceof Error ? job.error.message : t("optStatusFailed")}</p>
        <Button variant="outline" disabled={job.isFetching} onClick={() => void job.refetch()}>{t("optRetryStatus")}</Button>
      </div>}
      {jobId && job.data && <JobView active={active} projectId={projectId} view={job.data} onClose={onClose} onRestart={() => setJobId(null)} />}
    </div>
  );
}

function JobView({ active, projectId, view, onClose, onRestart }: { active: boolean; projectId: string; view: OptimizationView; onClose: () => void; onRestart: () => void }) {
  const { locale, t } = useI18n();
  const qc = useQueryClient();
  const setSelectedSetupId = useSimulationStore((s) => s.setSelectedSetupId);
  const viewedCurrency = useSimulationStore((s) => s.currency);
  const activeView = useRef(false);
  useLayoutEffect(() => {
    activeView.current = active;
    return () => { activeView.current = false; };
  }, [active]);
  const { status, result } = view;
  // Revenue scores are in the currency's minor unit; the optimized runs carry it, the viewed run is the fallback.
  const code = currencyCode(result?.baseline_summary?.currency ?? result?.best_summary?.currency ?? viewedCurrency);
  const objective = status.spec.objective;
  const score = (value: number) => scoreText(objective, value, code);
  const apply = useMutation({
    onMutate: () => ({ selectedId: useSimulationStore.getState().selectedSetupId }),
    mutationFn: () => api.applyOptimization(projectId, status.job_id),
    onSuccess: async (setup, _variables, context) => {
      await qc.invalidateQueries({ queryKey: queryKeys.setups(projectId) });
      // A completed save still refreshes its list, but must not navigate after the user leaves.
      if (!activeView.current || !context || useSimulationStore.getState().selectedSetupId !== context.selectedId) return;
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
        <p className="flex items-start gap-2 text-destructive"><TriangleAlert className="mt-0.5 size-4 shrink-0" /> {status.status === "canceled" ? t("optStopped") : status.error}</p>
        <Button variant="outline" onClick={onRestart}>{t("back")}</Button>
      </div>
    );
  }
  if (!result) {
    const ratio = status.budget ? status.evaluations / status.budget : 0;
    const elapsed = (now - Date.parse(status.created_at)) / 1000;
    const phase = status.phase ?? "";
    const label = phase.startsWith("judging") ? t("optJudging", { progress: phase.replace("judging", "").trim() })
      : phase === "calibrating" ? t("optCalibrating")
      : t("optTrying", { done: status.evaluations, total: status.budget });
    return (
      <div className="space-y-3 py-6 text-center text-sm">
        <div className="font-medium">{label}</div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted"><div className="heat-gradient h-full transition-[width]" style={{ width: `${(phase === "calibrating" ? 0.05 : ratio) * 100}%` }} /></div>
        <div className="text-xs text-muted-foreground">
          {elapsed >= 120 ? t("optElapsedMinutes", { minutes: Math.floor(elapsed / 60), seconds: Math.round(elapsed % 60) }) : t("optElapsedSeconds", { seconds: Math.round(elapsed) })}
          {status.best_score != null ? ` · ${t("optBestSoFar", { score: score(status.best_score) })}` : ""}{status.scenario ? ` · ${status.scenario}` : ""}
          {status.judge?.judge === "vlm" ? ` · ${t("optVisionJudge")}` : ""}
        </div>
        {status.operations && <div className="text-xs text-muted-foreground">{t("optSharedStoreNote")}</div>}
        <Button variant="outline" size="sm" className="gap-1.5" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
          <Square className="size-3.5" /> {t("optStop")}
        </Button>
        {cancel.error != null && <p role="alert" className="text-destructive">{cancel.error instanceof Error ? cancel.error.message : t("optStopFailed")}</p>}
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
    return <JudgeView projectId={projectId} report={result.judge} result={result} status={status} code={code} apply={apply} onRestart={onRestart} />;
  }
  return (
    <div className="space-y-4 text-sm">
      {/* Replaces the Start button and the progress, so focus moves to the verdict. */}
      <div ref={focusOnMount} tabIndex={-1} className={cn("rounded-lg border p-3 outline-offset-2", good ? "tone-good" : "bg-muted/30")}>
        <div className="flex items-center gap-2 font-medium">
          {good ? <CheckCircle2 className="size-4 text-positive" /> : <TriangleAlert className="size-4 text-warn" />}
          {t("optValidated", { improvement: improvementText(validated, validationGain ?? 0, metric?.mean_a ?? 1, objective, code, locale) })}
          {result.validation_prob_better != null && <span className="font-normal text-muted-foreground">{t("optProbBetter", { prob: formatPercent(result.validation_prob_better, 0) })}</span>}
        </div>
        {metric && (
          <div className="mt-1 text-xs text-muted-foreground">
            {t("optInterval", { low: signedScore(objective, metric.ci_low, code, locale), high: signedScore(objective, metric.ci_high, code, locale), paired: result.validation?.paired_customers ?? 0 })}
          </div>
        )}
        <div className="mt-1 text-xs text-muted-foreground">{t("optSearchScore", { improvement: improvementText(result.relative_improvement, searchGain, result.baseline_score, objective, code, locale) })}</div>
      </div>

      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chart} margin={{ top: 5, right: 10, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            {/* Candidates are numbered trials: a number axis ticked at 1, 10, 20 … instead of every other one. */}
            <XAxis dataKey="i" type="number" domain={["dataMin", "dataMax"]} allowDecimals={false}
              ticks={xTicks(chart.map((d) => d.i))} tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            <YAxis tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} domain={["auto", "auto"]} tickFormatter={score} width={64} />
            <Tooltip contentStyle={{ fontSize: 11 }} formatter={(value) => typeof value === "number" ? score(value) : value} />
            <Legend verticalAlign="top" align="right" height={20} iconType="plainline" wrapperStyle={{ fontSize: 11 }} />
            <Line type="linear" dataKey="score" stroke="var(--muted-foreground)" strokeOpacity={0.6} dot={false} strokeWidth={1} name={t("optChartCandidate")} isAnimationActive={false} />
            <Line type="stepAfter" dataKey="best" stroke="var(--primary)" dot={false} strokeWidth={2.5} name={t("optChartBest")} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {result.baseline_summary && result.best_summary && (
        <table className="w-full text-xs">
          <thead className="text-muted-foreground"><tr><th className="text-left font-normal">{t("optSearchShoppers")}</th><th className="text-right font-normal">{t("optNow")}</th><th className="text-right font-normal">{t("optOptimized")}</th></tr></thead>
          <tbody>
            {([
              ["kpiRevenuePerVisitor", (s: api.RunSummary) => formatMoney(s.revenue_per_visitor ?? 0, code)],
              ["kpiConversion", (s: api.RunSummary) => formatPercent(s.conversion_rate ?? 0, 1)],
              ["kpiUnitsPerBuyer", (s: api.RunSummary) => formatDecimal(s.avg_units_per_buyer ?? 0, 2)],
              ["dashImpulseShare", (s: api.RunSummary) => formatPercent(s.impulse_revenue_share ?? 0, 1)],
              ["optWalkTiles", (s: api.RunSummary) => formatDecimal(s.avg_path_tiles ?? 0, 1)],
            ] as const).map(([label, f]) => (
              <tr key={label} className="border-t"><td className="py-1">{t(label)}</td><td className="text-right tabular-nums">{f(result.baseline_summary!)}</td><td className="text-right tabular-nums">{f(result.best_summary!)}</td></tr>
            ))}
          </tbody>
        </table>
      )}

      <div>
        <div className="mb-1 text-xs text-muted-foreground">{t("optChanges", { count: result.applied_moves.length })}</div>
        <ol className="max-h-32 list-decimal space-y-0.5 overflow-y-auto pl-5 text-xs">
          {result.applied_moves.map((m, i) => <li key={i}>{m}</li>)}
        </ol>
      </div>
      {result.notes.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      {apply.error != null && <p role="alert" className="text-sm text-destructive">{apply.error instanceof Error ? apply.error.message : t("optSaveFailed")}</p>}

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onRestart}>{t("optTryOther")}</Button>
        <Button onClick={() => apply.mutate()} disabled={apply.isPending || result.applied_moves.length === 0 || !!status.applied_setup_id}>
          {apply.isPending ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
          {status.applied_setup_id ? t("optSaved") : t("optSaveNew")}
        </Button>
      </div>
    </div>
  );
}


function JudgeView({ report, result, status, code, apply, onRestart }: {
  projectId: string;
  report: VLMJudgeReport;
  result: api.OptimizeResult;
  status: api.OptimizationStatus;
  code: string;
  apply: { mutate: () => void; isPending: boolean; error: unknown };
  onRestart: () => void;
}) {
  const { locale, t } = useI18n();
  const winner = report.candidates.find((c) => c.winner);
  const objective = status.spec.objective;
  const minimize = objective === "walking_distance";
  const gain = minimize ? result.baseline_score - result.best_score : result.best_score - result.baseline_score;
  const improved = winner && winner.label !== "baseline" && gain > 0;
  const sure = minimize ? winner?.delta_ci_high != null && winner.delta_ci_high < 0
    : winner?.delta_ci_low != null && winner.delta_ci_low > 0;
  const cal = report.calibration;
  return (
    <div className="space-y-4 text-sm">
      <div ref={focusOnMount} tabIndex={-1} className={cn("rounded-xl border p-3 outline-offset-2", improved && sure ? "tone-good" : improved ? "tone-warn" : "bg-muted/30")}>
        <div className="flex items-center gap-2 font-medium">
          <Eye className="size-4" />
          {improved ? t("optPrefer", { candidate: winner!.label, improvement: improvementText(winner!.relative_improvement, gain, result.baseline_score, objective, code, locale) }) : t("optKept")}
          {winner?.prob_better != null && improved && <span className="font-normal text-muted-foreground">{t("optProbBetter", { prob: formatPercent(winner.prob_better, 0) })}</span>}
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          {t("optJudgeShoppers", { count: report.customers })} · {report.model}
          {report.spearman != null ? ` · ${t("optAgreement", { rho: formatDecimal(report.spearman, 2) })}` : ""}
          {` · ${t("optModelCalls", { calls: report.vlm_requests, minutes: Math.round(report.seconds / 60) })}`}
        </div>
        {improved && !sure && <div className="mt-1 text-xs">{t("optStillUnsure")}</div>}
      </div>

      <table className="w-full text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="text-left font-normal">{t("optLayout")}</th>
            <th className="text-right font-normal">{t("optRuleModel")}</th>
            <th className="text-right font-normal">{t("visionShoppers")}</th>
            <th className="text-right font-normal">{t("optVsNow")}</th>
            <th className="text-right font-normal">{t("optProbBetterHead")}</th>
          </tr>
        </thead>
        <tbody>
          {report.candidates.map((c) => (
            <tr key={c.label} className={cn("border-t", c.winner && "font-semibold")}>
              <td className="py-1.5">{c.label === "baseline" ? t("optCurrentLayout") : t("optCandidateLabel", { label: c.label })}{c.winner ? " ★" : ""}</td>
              <td className="text-right tabular-nums">{scoreText(objective, c.surrogate_score, code)} <span className="text-muted-foreground">#{c.surrogate_rank}</span></td>
              <td className="text-right tabular-nums">{c.vlm_score != null ? scoreText(objective, c.vlm_score, code) : "—"} <span className="text-muted-foreground">{c.vlm_rank != null ? `#${c.vlm_rank}` : ""}</span></td>
              <td className="text-right tabular-nums">
                {c.label === "baseline" || c.delta_mean == null ? "—" : `${signedScore(objective, c.delta_mean, code, locale)} (${c.delta_ci_low != null ? signedScore(objective, c.delta_ci_low, code, locale) : "—"} … ${c.delta_ci_high != null ? signedScore(objective, c.delta_ci_high, code, locale) : "—"})`}
              </td>
              <td className="text-right tabular-nums">{c.prob_better != null && c.label !== "baseline" ? formatPercent(c.prob_better, 0) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {cal && (
        <div className="rounded-xl border p-3 text-xs">
          <div className="mb-1 font-medium">{t("optCalibrated")}</div>
          <div className="grid grid-cols-3 gap-2 tabular-nums">
            <div className="text-muted-foreground">{t("optImpulseBuys")}</div>
            <div>{t("optVisionValue", { value: formatDecimal(cal.target.impulse_rate, 2) })}</div>
            <div>{t("optRuleValue", { before: formatDecimal(cal.before.impulse_rate, 2), after: formatDecimal(cal.after.impulse_rate, 2) })}</div>
            <div className="text-muted-foreground">{t("optImpulseRevenueShare")}</div>
            <div>{t("optVisionValue", { value: formatPercent(cal.target.impulse_revenue_share, 1) })}</div>
            <div>{t("optRuleValue", { before: formatPercent(cal.before.impulse_revenue_share, 1), after: formatPercent(cal.after.impulse_revenue_share, 1) })}</div>
          </div>
          <div className="mt-1 text-muted-foreground">{t("optMismatch", { before: formatDecimal(cal.gap_before, 2), after: formatDecimal(cal.gap_after, 2), settings: cal.grid_points })}</div>
        </div>
      )}

      {winner && winner.moves.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-muted-foreground">{t("optWinnerChanges", { count: winner.moves.length })}</div>
          <ol className="max-h-32 list-decimal space-y-0.5 overflow-y-auto pl-5 text-xs">{winner.moves.map((m, i) => <li key={i}>{m}</li>)}</ol>
        </div>
      )}
      {report.notes.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{report.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      {apply.error != null && <p role="alert" className="text-sm text-destructive">{apply.error instanceof Error ? apply.error.message : t("optSaveFailed")}</p>}

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onRestart}>{t("optTryOther")}</Button>
        <Button onClick={() => apply.mutate()} disabled={apply.isPending || !improved || result.applied_moves.length === 0 || !!status.applied_setup_id}>
          {apply.isPending ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
          {status.applied_setup_id ? t("optSaved") : t("optSaveWinner")}
        </Button>
      </div>
    </div>
  );
}

/** An objective's value in its own unit: money for revenue goals (minor units), a share for conversion, else a number. */
function scoreText(objective: OptimizeObjective, value: number, code: string): string {
  if (objective === "revenue_per_visitor" || objective === "total_revenue" || objective === "impulse_revenue") return formatMoney(value, code);
  if (objective === "conversion_rate") return formatPercent(value);
  return formatDecimal(value, objective === "units_per_visitor" ? 2 : 1);
}

/** Every candidate of a short search, else the first, each tenth and (when not crowding the tenth) the last. */
function xTicks(candidates: number[]): number[] {
  if (candidates.length <= 12) return candidates;
  const last = candidates[candidates.length - 1] ?? 1;
  return [...candidates.filter((i) => i === 1 || i % 10 === 0), ...(last % 10 > 3 ? [last] : [])];
}

/** A difference in the objective's unit, signed; a conversion difference reads in percentage points. */
function signedScore(objective: OptimizeObjective, value: number, code: string, locale: Locale): string {
  const text = objective === "conversion_rate" ? `${formatDecimal(value * 100, 1)}${translate(locale, "cmpPoints")}` : scoreText(objective, value, code);
  return value > 0 ? `+${text}` : text;
}

function improvementText(relative: number | null | undefined, gain: number, baseline: number, objective: OptimizeObjective, code: string, locale: Locale): string {
  if (baseline === 0) return translate(locale, "optAbsoluteChange", { gain: signedScore(objective, gain, code, locale) });
  return relative == null ? "—" : `${relative >= 0 ? "+" : ""}${formatPercent(relative)}`;
}
