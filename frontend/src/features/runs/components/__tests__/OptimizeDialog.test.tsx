// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { OptimizeDialog } from "../OptimizeDialog";
import { useSimulationStore } from "@/stores/simulationStore";

vi.mock("@/shared/api/client", () => ({
  getScenarios: vi.fn(), startOptimization: vi.fn(), getOptimization: vi.fn(),
  applyOptimization: vi.fn(), cancelOptimization: vi.fn(),
}));
const originalCurrency = useSimulationStore.getState().currency;
const originalSelectedSetupId = useSimulationStore.getState().selectedSetupId;
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); useSimulationStore.setState({ currency: originalCurrency, selectedSetupId: originalSelectedSetupId }); });

async function show(kind: "rule" | "vlm", baseline = 0, objective: api.OptimizeObjective = "revenue_per_visitor", options: { state?: "pending" | "running"; loadError?: Error; currency?: string; ci?: [number, number]; summaries?: [api.RunSummary, api.RunSummary]; closeable?: boolean } = {}) {
  useLocale.getState().setLocale("en");
  useSimulationStore.setState({ currency: options.currency ?? "USD" });
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
    ci_low: options.ci?.[0] ?? difference, ci_high: options.ci?.[1] ?? difference, prob_b_greater: minimize ? 0 : 1,
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
    baseline_summary: options.summaries?.[0] ?? null, best_summary: options.summaries?.[1] ?? null, validation_metric: metric.metric,
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
  // A host that really closes the dialog, with the tab a saved layout opens in.
  function Host() {
    const [open, setOpen] = useState(true);
    return <><button type="button" role="tab" data-layout-id="s2">Optimized layout</button><OptimizeDialog open={open} onOpenChange={setOpen} projectId="p" setupId="s1" /></>;
  }
  render(<QueryClientProvider client={client}>{options.closeable ? <Host /> : <OptimizeDialog open onOpenChange={() => {}} projectId="p" setupId="s1" />}</QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  if (options.loadError) await waitFor(() => expect(api.getOptimization).toHaveBeenCalled());
  else await screen.findByRole("button", { name: options.state ? "Stop" : "Try other settings" });
  return client;
}

it.each([
  ["rule", "USD", "+$0.10"], ["vlm", "USD", "+$0.10"],
  ["rule", "JPY", "+¥10"], ["vlm", "JPY", "+¥10"],
] as const)("keeps a gain from zero visible and saveable for %s in %s", async (kind, currency, gain) => {
  await show(kind, 0, "revenue_per_visitor", { currency });
  expect(screen.getByRole("dialog").textContent).toContain(`${gain} (absolute change from zero)`);
  expect(screen.getByRole("dialog").textContent).not.toContain("+0.0%");
  const save = screen.getByRole("button", { name: kind === "vlm" ? "Save the winner as a new layout" : "Save as new layout" });
  expect((save as HTMLButtonElement).disabled).toBe(false);
});

it("keeps percentage improvements for a positive baseline", async () => {
  await show("rule", 100);
  expect(screen.getByText(/Validated on fresh shoppers: \+10\.0%/)).toBeTruthy();
});

const summary = (revenue_per_visitor: number, currency: string) => ({
  total_customers: 900, total_revenue: revenue_per_visitor * 900, top_products: [], by_purpose: {}, by_identity: {}, by_age: {}, by_gender: {},
  currency, revenue_per_visitor, conversion_rate: 0.5, avg_units_per_buyer: 2, impulse_revenue_share: 0.2, avg_path_tiles: 20,
}) as api.RunSummary;

it("shows revenue scores, the comparison table and the interval as money in the run's currency", async () => {
  await show("rule", 695, "revenue_per_visitor", { ci: [-1326, 1140], summaries: [summary(695, "USD"), summary(714, "USD")] });
  const row = screen.getByText("Revenue / visitor").closest("tr")!;
  expect([...row.querySelectorAll("td")].slice(1).map((cell) => cell.textContent)).toEqual(["$6.95", "$7.14"]);
  expect(screen.getByText(/interval of the difference/).textContent).toContain("-$13.26 … +$11.40");
  expect(screen.getByText(/Validated on fresh shoppers/).textContent).toContain("+1.4%");
});

it("formats revenue in the currency's own unit and translates the interval in Korean", async () => {
  useLocale.getState().setLocale("ko");
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  const status = { job_id: "job1", setup_id: "s1", status: "completed", error: "", evaluations: 1, budget: 1, baseline_score: 6950, best_score: 7140,
    scenario: "", created_at: "2026-10-21T10:00:00Z", finished_at: "2026-10-21T10:01:00Z", applied_setup_id: null,
    spec: { objective: "revenue_per_visitor", scope: "planogram", algorithm: "hill_climb", budget: 1, eval_customers: 10, validation_customers: 10, seed: 0,
      constraints: { keep_fridges_on_walls: true, lock_rack_ids: [], max_moves: 10, min_improvement: 0 } } } as api.OptimizationStatus;
  vi.mocked(api.startOptimization).mockResolvedValue(status);
  vi.mocked(api.getOptimization).mockResolvedValue({ status, result: {
    baseline_score: 6950, best_score: 7140, relative_improvement: 190 / 6950, applied_moves: ["Move tea"], history: [], evaluations: 1, seconds: 1,
    baseline_summary: summary(6950, "KRW"), best_summary: summary(7140, "KRW"), validation_metric: "spend",
    validation_relative_improvement: -0.001, validation_prob_better: 0.4, notes: [],
    validation: { run_a: "a", run_b: "b", paired_customers: 900, unpaired_a: 0, unpaired_b: 0, n_bootstrap: 2000, confidence: 0.95, notes: [],
      metrics: [{ metric: "spend", mean_a: 6950, mean_b: 6943, diff: -7, rel_diff: -0.001, ci_low: -130, ci_high: 114, prob_b_greater: 0.4, sd_paired_diff: 1, n_for_5pct_effect: 10 }] },
  } });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><OptimizeDialog open onOpenChange={() => {}} projectId="p" setupId="s1" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "시작" }));
  await screen.findByRole("button", { name: "다른 설정으로 시도" });
  const row = screen.getByText("방문객당 매출").closest("tr")!;
  expect([...row.querySelectorAll("td")].slice(1).map((cell) => cell.textContent)).toEqual(["₩6,950", "₩7,140"]);
  expect(screen.getByText(/차이의 95% 구간/).textContent).toContain("-₩130 … +₩114");
  expect(screen.getByText(/새 고객으로 검증한 결과/).textContent).toContain("-0.1%");
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

it.each(["rule", "vlm"] as const)("moves focus to the %s verdict that replaces the controls", async (kind) => {
  await show(kind, 100);
  const focused = document.activeElement!;
  expect(focused.getAttribute("role")).not.toBe("dialog");
  expect(focused.textContent).toMatch(kind === "vlm" ? /Vision shoppers prefer/ : /Validated on fresh shoppers/);
});

it.each(["rule", "vlm"] as const)("continues from the saved layout's tab after saving the %s winner", async (kind) => {
  await show(kind, 100, "revenue_per_visitor", { closeable: true });
  vi.mocked(api.applyOptimization).mockResolvedValueOnce({ id: "s2" } as Awaited<ReturnType<typeof api.applyOptimization>>);
  fireEvent.click(screen.getByRole("button", { name: kind === "vlm" ? "Save the winner as a new layout" : "Save as new layout" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Optimized layout" })));
});

it.each(["closed", "unmounted", "selection changed"])("keeps the current layout when a delayed save finishes after the dialog is %s", async state => {
  useSimulationStore.setState({ selectedSetupId: "s1" });
  const client = await show("rule", 100, "revenue_per_visitor", { closeable: true });
  let finish!: (value: { id: string; name: string }) => void;
  const response = new Promise<{ id: string; name: string }>(resolve => { finish = resolve; });
  vi.mocked(api.applyOptimization).mockReturnValueOnce(response);
  const invalidated = vi.spyOn(client, "invalidateQueries");
  fireEvent.click(screen.getByRole("button", { name: "Save as new layout" }));
  await waitFor(() => expect(api.applyOptimization).toHaveBeenCalledOnce());
  if (state === "closed") {
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  } else if (state === "unmounted") {
    cleanup();
  } else {
    act(() => useSimulationStore.getState().setSelectedSetupId("other-layout"));
  }
  await act(async () => { finish({ id: "s2", name: "Optimized" }); await response; });
  await waitFor(() => expect(invalidated).toHaveBeenCalled());
  expect(useSimulationStore.getState().selectedSetupId).toBe(state === "selection changed" ? "other-layout" : "s1");
  client.clear();
});
