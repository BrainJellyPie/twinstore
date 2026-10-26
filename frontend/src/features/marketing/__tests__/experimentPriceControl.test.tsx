// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ExperimentReport, VariantResult } from "@/shared/api/marketing";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { ExperimentReportView } from "../ExperimentReport";

vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), listSites: vi.fn().mockResolvedValue([]) }));
vi.mock("@tanstack/react-router", () => ({ Link: () => null }));
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

const control: VariantResult = { name: "Control", applied: [], warnings: [], revenue_per_visitor: 100, conversion: 0.1,
  units_per_visitor: 1, vs_control: [], focus: [], top_skus: [] };
const report: ExperimentReport = { experiment_id: "exp", name: "Ladder", setup_id: "s", engine: "rule", model: "", panel_size: 100,
  currency: "USD", visitors_per_day: 100, focus_skus: [], control, winner: "", notes: [], seconds: 0,
  variants: [{ ...control, name: "-10 %" }],
  price_response: { sku: "cola", name: "Cola", elasticity: null, best_price: 224, points: [
    { arm: "-10 %", price: 224, units: 0.02, units_low: 0.017, units_high: 0.027, revenue: 4.48 },
    { arm: "Control", price: 249, units: 0.017, units_low: 0.017, units_high: 0.017, revenue: 4.15 },
  ] } };

it("names the control in the reader's language and gives it no interval of its own", () => {
  useLocale.getState().setLocale("ko");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ExperimentReportView projectId="p" report={report} /></QueryClientProvider>);
  const rows = within(screen.getByRole("table")).getAllByRole("row");
  expect(rows[1]!.textContent).toContain("[1.7, 2.7]");
  expect(rows[2]!.textContent).toBe("대조군US$2.491.7US$4.15");
});
