// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { MetricComparison } from "@/shared/api/client";
import type { ExperimentReport, VariantResult } from "@/shared/api/marketing";
import { ExperimentReportView } from "../ExperimentReport";

vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function show(baseline: number) {
  const comparison = (metric: string, base: number, gain: number): MetricComparison => ({
    metric, mean_a: base, mean_b: base + gain, diff: gain, rel_diff: base ? gain / base : 0,
    ci_low: gain, ci_high: gain, prob_b_greater: 1, sd_paired_diff: 0, n_for_5pct_effect: 0,
  });
  const units = baseline ? 1 : 0;
  const control: VariantResult = { name: "Control", applied: [], warnings: [], revenue_per_visitor: baseline,
    conversion: 0, units_per_visitor: units, vs_control: [], focus: [], top_skus: [] };
  const report: ExperimentReport = { experiment_id: "exp_test", name: "Tea experiment", setup_id: "s", engine: "rule",
    model: "", panel_size: 100, currency: "USD", visitors_per_day: 100, focus_skus: [], control, winner: "Offer", notes: [], seconds: 0,
    variants: [{ ...control, name: "Offer", revenue_per_visitor: baseline + 100, units_per_visitor: units + 1,
      vs_control: [comparison("spend", baseline, 100), comparison("units", units, 1)] }],
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ExperimentReportView projectId="p" report={report} /></QueryClientProvider>);
}

it("shows absolute revenue and unit gains when the control sold nothing", () => {
  const { container } = show(0);
  expect(container.textContent).toContain("+$1.00 from zero");
  expect(container.textContent).toContain("+1.00 from zero");
  expect(container.textContent).not.toContain("+0.0%");
});

it("keeps relative gains for a nonzero control", () => {
  const { container } = show(100);
  expect(container.textContent).toContain("+100.0%");
  expect(container.textContent).not.toContain("from zero");
});
