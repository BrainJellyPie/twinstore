// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { OptimizeDialog } from "../OptimizeDialog";

vi.mock("@/shared/api/client", () => ({
  getScenarios: vi.fn(), startOptimization: vi.fn(), getOptimization: vi.fn(),
  applyOptimization: vi.fn(), cancelOptimization: vi.fn(),
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

async function show(kind: "rule" | "vlm", baseline = 0, objective: api.OptimizeObjective = "revenue_per_visitor", options: { state?: "pending" | "running"; loadError?: Error } = {}) {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  const minimize = objective === "walking_distance";
  const difference = minimize ? -10 : 10;
  const best = baseline + difference;
  const relative = baseline ? Math.abs(difference) / baseline : 0;
  const spec: api.OptimizeSpec = {
    objective, scope: "planogram", algorithm: "hill_climb", budget: 1,
    eval_customers: 10, validation_customers: 10, seed: 0,
    constraints: { keep_fridges_on_walls: true, lock_rack_ids: [], max_moves: 10, min_improvement: 0 },
  };
  const status: api.OptimizationStatus = {
    job_id: "job1", setup_id: "s1", status: options.state ?? "completed", error: "", evaluations: 1, budget: 1,
    baseline_score: baseline, best_score: best, scenario: "", spec,
    created_at: "2026-10-21T10:00:00Z", finished_at: "2026-10-21T10:01:00Z", applied_setup_id: null,
  };
  const metric: api.MetricComparison = {
    metric: minimize ? "path_tiles" : "spend", mean_a: baseline, mean_b: best,
    diff: difference, rel_diff: baseline ? difference / baseline : 0,
    ci_low: difference, ci_high: difference, prob_b_greater: minimize ? 0 : 1,
    sd_paired_diff: 0, n_for_5pct_effect: 0,
  };
  const candidate: api.JudgedCandidate = {
    label: "#1", iteration: 1, moves: ["Move tea to eye level"], surrogate_score: best,
    surrogate_rank: 1, vlm_score: best, vlm_rank: 1, delta_mean: difference,
    delta_ci_low: difference, delta_ci_high: difference, prob_better: 1,
    relative_improvement: relative, failed_customers: 0, plan_errors: 0, winner: true,
  };
  const result: api.OptimizeResult = {
    baseline_score: baseline, best_score: best, relative_improvement: relative,
    applied_moves: candidate.moves, history: [], evaluations: 1, seconds: 1,
    baseline_summary: null, best_summary: null, validation_metric: metric.metric,
    validation_relative_improvement: baseline ? relative : null, validation_prob_better: 1,
    validation: { run_a: "baseline", run_b: "optimized", paired_customers: 10, unpaired_a: 0,
      unpaired_b: 0, n_bootstrap: 2000, confidence: 0.95, metrics: [metric], notes: [] },
    notes: [],
    judge: kind === "vlm" ? { model: "scripted", customers: 10, metric: metric.metric,
      candidates: [{ ...candidate, label: "baseline", iteration: 0, moves: [], vlm_score: baseline,
        surrogate_score: baseline, vlm_rank: 2, surrogate_rank: 2, winner: false }, candidate],
      winner: "#1", surrogate_winner: "#1", spearman: 1, calibration: null, vlm_requests: 0, seconds: 1, notes: [] } : null,
  };
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  vi.mocked(api.startOptimization).mockResolvedValue(status);
  vi.mocked(api.getOptimization).mockResolvedValue({ status, result: options.state ? null : result });
  if (options.loadError) vi.mocked(api.getOptimization).mockRejectedValueOnce(options.loadError);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OptimizeDialog open onOpenChange={() => {}} projectId="p" setupId="s1" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  if (options.loadError) await waitFor(() => expect(api.getOptimization).toHaveBeenCalled());
  else await screen.findByRole("button", { name: options.state ? "Stop" : "Try other settings" });
  return client;
}

it.each(["rule", "vlm"] as const)("keeps a gain from zero visible and saveable for %s", async (kind) => {
  await show(kind);
  expect(screen.getByRole("dialog").textContent).toContain("+10.00 (absolute change from zero)");
  expect(screen.getByRole("dialog").textContent).not.toContain("+0.0 %");
  const save = screen.getByRole("button", { name: kind === "vlm" ? "Save the winner as a new layout" : "Save as new layout" });
  expect((save as HTMLButtonElement).disabled).toBe(false);
});

it("keeps percentage improvements for a positive baseline", async () => {
  await show("rule", 100);
  expect(screen.getByText(/Validated on fresh shoppers: \+10.0 %/)).toBeTruthy();
});

it("recognizes a decisive reduction in walking distance for the vision winner", async () => {
  await show("vlm", 100, "walking_distance");
  expect(screen.getByText(/Vision shoppers prefer #1/)).toBeTruthy();
  expect(screen.queryByText(/The interval still includes no change/)).toBeNull();
});

it.each(["rule", "vlm"] as const)("explains a failed save and permits retry for %s", async (kind) => {
  await show(kind, 100);
  vi.mocked(api.applyOptimization).mockRejectedValueOnce(new Error("The source layout no longer exists."));
  const save = screen.getByRole("button", { name: kind === "vlm" ? "Save the winner as a new layout" : "Save as new layout" });
  fireEvent.click(save);
  expect((await screen.findByRole("alert")).textContent).toContain("The source layout no longer exists.");
  expect((save as HTMLButtonElement).disabled).toBe(false);
});


it.each(["pending", "running"] as const)("explains a failed stop request while the job is %s", async (state) => {
  await show("rule", 100, "revenue_per_visitor", { state });
  vi.mocked(api.cancelOptimization).mockRejectedValueOnce(new Error("The server could not stop this optimization."));
  const stop = screen.getByRole("button", { name: "Stop" });
  fireEvent.click(stop);
  expect((await screen.findByRole("alert")).textContent).toContain("The server could not stop this optimization.");
  expect((stop as HTMLButtonElement).disabled).toBe(false);
});

it("explains an initial status failure and retries the same job", async () => {
  await show("rule", 100, "revenue_per_visitor", { loadError: new Error("Could not load optimization.") });
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load optimization.");
  fireEvent.click(screen.getByRole("button", { name: "Retry status" }));
  await screen.findByRole("button", { name: "Try other settings" });
  expect(api.startOptimization).toHaveBeenCalledOnce();
  expect(api.getOptimization).toHaveBeenLastCalledWith("p", "job1", expect.any(AbortSignal));
});

it("keeps the job controls visible after a polling failure and clears the error on retry", async () => {
  const client = await show("rule", 100, "revenue_per_visitor", { state: "running" });
  vi.mocked(api.getOptimization).mockRejectedValueOnce(new Error("Status connection lost."));
  await client.invalidateQueries({ queryKey: ["projects", "p", "optimizations", "job1"] });
  expect((await screen.findByRole("alert")).textContent).toContain("Status connection lost.");
  expect(screen.getByRole("button", { name: "Stop" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Retry status" }));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(api.startOptimization).toHaveBeenCalledOnce();
});
