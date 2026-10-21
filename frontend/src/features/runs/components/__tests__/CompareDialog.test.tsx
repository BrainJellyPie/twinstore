// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { explainComparison, type ComparisonReport, type MetricComparison } from "@/shared/api/client";
import { CompareDialog } from "../CompareDialog";

const state = vi.hoisted(() => ({ report: null as ComparisonReport | null }));
vi.mock("../../hooks", () => ({
  useProjectRuns: () => ({ data: ["run_a", "run_b"].map((run_id) => ({
    run_id, status: "completed", setup_id: "s1", created_at: "2026-10-21T10:00:00Z",
  })) }),
  useCompare: () => ({ data: state.report, isLoading: false, isError: false }),
}));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), explainComparison: vi.fn(),
}));
afterEach(cleanup);

function show(overrides: Partial<MetricComparison> = {}) {
  state.report = {
    run_a: "run_a", run_b: "run_b", paired_customers: 100,
    unpaired_a: 0, unpaired_b: 0, n_bootstrap: 2000, confidence: 0.95, notes: [],
    metrics: [{
      metric: "spend", mean_a: 0, mean_b: 500, diff: 500, rel_diff: 0,
      ci_low: 200, ci_high: 800, prob_b_greater: 1, sd_paired_diff: 50,
      n_for_5pct_effect: 0, ...overrides,
    }],
  };
  render(<QueryClientProvider client={new QueryClient()}>
    <CompareDialog open onOpenChange={() => {}} projectId="p" layouts={[]} defaultRunId="run_b" />
  </QueryClientProvider>);
}

it("shows absolute spend gains and their interval when baseline spend is zero", () => {
  show();
  expect(screen.getByText("Spend per visitor: +500 minor units")).toBeTruthy();
  expect(screen.getByText("+200 … +800")).toBeTruthy();
  const row = screen.getByText("Spend / visitor").closest("tr")!;
  const marker = row.querySelector("circle")!;
  const zero = row.querySelector("line")!;
  expect(Number(marker.getAttribute("cx"))).toBeGreaterThan(Number(zero.getAttribute("x1")));
});

it("keeps relative changes for a nonzero baseline", () => {
  show({ mean_a: 1000, mean_b: 1500, rel_diff: 0.5 });
  expect(screen.getByText("Spend per visitor: +50.0%")).toBeTruthy();
  expect(screen.getByText("+20.0% … +80.0%")).toBeTruthy();
});

it("shows a zero absolute difference when neither run has purchases", () => {
  show({ mean_b: 0, diff: 0, ci_low: 0, ci_high: 0, prob_b_greater: 0 });
  expect(screen.getByText("Spend per visitor: 0 minor units")).toBeTruthy();
  expect(screen.getByText("0 … 0")).toBeTruthy();
  expect(screen.getByRole("dialog").textContent).not.toMatch(/NaN|Infinity/);
});

it("labels absolute conversion gains in percentage points", () => {
  show({ metric: "bought", mean_b: 0.5, diff: 0.5, ci_low: 0.2, ci_high: 0.8 });
  expect(screen.getByText("+20.0 pp … +80.0 pp")).toBeTruthy();
});

it.each(["spend", "units", "bought", "impulse_spend", "visit_sec", "path_tiles"].flatMap(metric =>
  [0, 10].map(mean_b => ({ metric, mean_b })),
))("withholds undefined relative sample sizes for $metric with B=$mean_b", ({ metric, mean_b }) => {
  show({ metric, mean_a: 0, mean_b, diff: mean_b, n_for_5pct_effect: 0 });
  const cell = screen.getByRole("table").querySelector("tbody tr")!.lastElementChild!;
  expect(cell.textContent).toBe("—");
  expect(cell.getAttribute("title")).toMatch(/zero baseline/i);
});

it.each([1, 100, 12345])("preserves an available relative sample size of %s", count => {
  show({ mean_a: 100, mean_b: 110, diff: 10, rel_diff: 0.1, n_for_5pct_effect: count });
  const cell = screen.getByRole("table").querySelector("tbody tr")!.lastElementChild!;
  expect(cell.textContent).toBe(count.toLocaleString());
});


it("explains the difference on request, with the figures it used", async () => {
  vi.mocked(explainComparison).mockResolvedValue({ summary: "B sells more drinks.", where: "Drink 3 gains 40 buyers.",
    caveats: "Snacks are within noise.", figures: ["Drink 3 1027 / 917"] });
  show({ mean_a: 1000, mean_b: 1500, rel_diff: 0.5 });
  fireEvent.click(screen.getByRole("button", { name: "Explain the difference" }));
  expect(await screen.findByText("B sells more drinks.")).toBeTruthy();
  expect(explainComparison).toHaveBeenCalledWith("p", "run_a", "run_b");
  expect(screen.getByRole("list", { name: "Figures used" }).textContent).toContain("Drink 3 1027 / 917");
});
