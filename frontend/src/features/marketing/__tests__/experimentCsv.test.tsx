// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as XLSX from "xlsx";
import type { ExperimentReport, VariantResult } from "@/shared/api/marketing";
import { ExperimentReportView } from "../ExperimentReport";

vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("../charts", () => ({ DemandChart: () => null, LiftChart: () => null }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

async function exportedRows(name: string, change = "Price reduced") {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:experiment-csv");
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const control: VariantResult = { name: "Control", applied: [], warnings: [], revenue_per_visitor: 100,
    conversion: 1, units_per_visitor: 1, vs_control: [], focus: [], top_skus: [] };
  const report: ExperimentReport = { experiment_id: "exp_test", name: "Tea experiment", setup_id: "s", engine: "rule",
    model: "", panel_size: 40, currency: "USD", visitors_per_day: 40, focus_skus: [], control, winner: "", notes: [], seconds: 0,
    variants: [{ ...control, name, applied: [change], revenue_per_visitor: 90, vs_control: [{ metric: "spend",
      mean_a: 100, mean_b: 90, diff: -10, rel_diff: -0.1, ci_low: -10, ci_high: -10,
      prob_b_greater: 0, sd_paired_diff: 0, n_for_5pct_effect: 0 }] }],
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ExperimentReportView projectId="p" report={report} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "CSV" }));
  const blob = createObjectURL.mock.calls[0]?.[0];
  if (!blob) throw new Error("No CSV was downloaded");
  const csv = await new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob);
  });
  const workbook = XLSX.read(csv, { type: "string", raw: true });
  return XLSX.utils.sheet_to_json<string[]>(workbook.Sheets[workbook.SheetNames[0]!]!, { header: 1, raw: true });
}

it.each(["Tea\rOffer", "Tea\nOffer", 'Tea, "Offer"'])("round-trips CSV row boundaries and quotes in %j", async (name) => {
  const rows = await exportedRows(name);
  expect(rows[2]?.[0]).toBe(name);
  expect(rows[2]?.[1]).toBe("90");
  expect(rows[2]?.[5]).toBe("-10");
});

it.each(["=1+1", "+SUM(1,2)", "-2+3", "@SUM(1,2)", "\t=1+1"])("exports formula-like text %j without changing numeric losses", async (name) => {
  const rows = await exportedRows(name, name);
  expect(rows[2]?.[0]).toBe(`'${name}`);
  expect(rows[2]?.[8]).toBe(`'${name}`);
  expect(rows[2]?.[4]).toBe("-10");
});
