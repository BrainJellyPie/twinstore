// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ExperimentReport, Variant, VariantResult } from "@/shared/api/marketing";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { ExperimentReportView } from "../ExperimentReport";

vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), listSites: vi.fn().mockResolvedValue([]) }));
vi.mock("@tanstack/react-router", () => ({ Link: () => null }));
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(cleanup);

const control: VariantResult = { name: "Control", applied: [], warnings: [], revenue_per_visitor: 100, conversion: 0.1,
  units_per_visitor: 1, vs_control: [], focus: [], top_skus: [] };
const report: ExperimentReport = { experiment_id: "exp", name: "Cola test", setup_id: "s", engine: "rule", model: "", panel_size: 100,
  currency: "USD", visitors_per_day: 100, focus_skus: [], control, winner: "", notes: [], seconds: 0,
  variants: [{ ...control, name: "-10 %" }, { ...control, name: "-20 %" }] };
const discount = (percent: number) => ({ kind: "discount" as const, sku: "cola", percent });
const sign = { kind: "promo" as const, sku: "cola", promo: "SALE" };

function show(variants?: Variant[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ExperimentReportView projectId="p" report={report} variants={variants} /></QueryClientProvider>);
}

it("does not offer the price × sign analysis for a test without a sign arm", () => {
  show([{ name: "-10 %", changes: [discount(10)] }, { name: "-20 %", changes: [discount(20)] }]);
  expect(screen.queryByRole("button", { name: "Open price × sign analysis" })).toBeNull();
});

it("offers it when the test has a price arm, a sign arm and both together", () => {
  show([{ name: "-20 %", changes: [discount(20)] }, { name: "Sign", changes: [sign] }, { name: "Both", changes: [discount(20), sign] }]);
  expect(screen.getByRole("button", { name: "Open price × sign analysis" })).toBeTruthy();
});

it("still offers it for an older test whose variants were not kept", () => {
  show();
  expect(screen.getByRole("button", { name: "Open price × sign analysis" })).toBeTruthy();
});
