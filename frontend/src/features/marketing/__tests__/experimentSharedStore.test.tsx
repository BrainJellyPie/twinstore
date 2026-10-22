// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ExperimentReport, VariantResult } from "@/shared/api/marketing";
import { ExperimentReportView } from "../ExperimentReport";

vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function show(operations: ExperimentReport["operations"]) {
  const control: VariantResult = { name: "Control", applied: [], warnings: [], revenue_per_visitor: 500,
    conversion: 0.5, units_per_visitor: 1, vs_control: [], focus: [], top_skus: [], lost_units: 3, left_line: 1, avg_wait_sec: 40 };
  const report: ExperimentReport = { experiment_id: "exp_test", name: "Cola promo", setup_id: "s", engine: "rule",
    model: "", panel_size: 100, currency: "USD", visitors_per_day: 100, focus_skus: [], control, winner: "", notes: [], seconds: 0,
    variants: [{ ...control, name: "Half price", lost_units: 41, left_line: 6 }], operations,
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ExperimentReportView projectId="p" report={report} /></QueryClientProvider>);
}

it("shows what each arm lost to empty shelves and the till line when the shoppers shared the store", () => {
  const { container } = show({ stock_per_facing: 6 });
  expect(container.textContent).toContain("Sold out: 3 · Left the line: 1");
  expect(container.textContent).toContain("Sold out: 41 · Left the line: 6");
  expect(container.textContent).toContain("shared the store (units per shelf level: 6)");
});

it("says nothing of it for shoppers who each had the store alone", () => {
  const { container } = show(null);
  expect(container.textContent).not.toContain("Sold out:");
  expect(container.textContent).not.toContain("shared the store");
});
