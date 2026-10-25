// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ExperimentReport, VariantResult } from "@/shared/api/marketing";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { ExperimentReportView } from "../ExperimentReport";

vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), listSites: vi.fn(), variantFromTest: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, search }: { children: ReactNode; search?: { site?: string; compare?: string } }) =>
    <a href={search ? `/online/p?site=${search.site}&compare=${search.compare}` : "/online/p"}>{children}</a>,
}));
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const control: VariantResult = { name: "Control", applied: [], warnings: [], revenue_per_visitor: 100, conversion: 0.1,
  units_per_visitor: 1, vs_control: [], focus: [], top_skus: [] };
const report: ExperimentReport = { experiment_id: "exp", name: "Tea test", setup_id: "s", engine: "rule", model: "", panel_size: 100,
  currency: "USD", visitors_per_day: 100, focus_skus: [], control, winner: "", notes: [], seconds: 0,
  variants: [{ ...control, name: "Cheaper tea", applied: ["Green tea: price 299 → 249"] }] };
const variants = [{ name: "Cheaper tea", changes: [{ kind: "price" as const, sku: "tea", price: 249 }] }];
const site = (id: string, name: string, currency = "USD") => ({ id, name, currency }) as online.SiteSummary;

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ExperimentReportView projectId="p" report={report} variants={variants} /></QueryClientProvider>);
}

it("carries a tested variant to an online store in the test's currency and links to the comparison", async () => {
  vi.mocked(online.listSites).mockResolvedValue([site("s1", "Tea shop"), site("s2", "Seoul tea", "KRW"), site("s3", "Tea outlet")]);
  vi.mocked(online.variantFromTest).mockResolvedValue({
    site: { id: "v1", name: "Tea outlet – Cheaper tea" } as online.OnlineSite, applied: ["Green tea: price $2.99 → $2.49"],
    skipped: ["a move to another shelf has no web counterpart"],
  });
  show();
  await screen.findByRole("option", { name: "Tea shop" });
  const picker = screen.getByRole("combobox", { name: "Online store" }) as HTMLSelectElement;
  expect([...picker.options].map((o) => o.text)).toEqual(["Tea shop", "Tea outlet"]);
  fireEvent.change(picker, { target: { value: "s3" } });
  fireEvent.click(screen.getByRole("button", { name: "Make an online variant" }));
  expect(await screen.findByText("Online variant ready: Tea outlet – Cheaper tea")).toBeTruthy();
  expect(online.variantFromTest).toHaveBeenCalledWith("p", "s3", {
    name: "Tea outlet – Cheaper tea", note: "Tea test: Cheaper tea", currency: "USD", changes: variants[0]!.changes,
  });
  expect(screen.getByText("Green tea: price $2.99 → $2.49")).toBeTruthy();
  const notCarried = screen.getByText("Not carried over").parentElement!;
  expect(within(notCarried).getByText("a move to another shelf has no web counterpart")).toBeTruthy();
  expect(screen.getByRole("link", { name: /Compare online/ }).getAttribute("href")).toBe("/online/p?site=s3&compare=v1");
});

it("points to putting a store online when none has the test's currency", async () => {
  vi.mocked(online.listSites).mockResolvedValue([site("s2", "Seoul tea", "KRW")]);
  show();
  expect(await screen.findByText(/No online store has prices in USD yet/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "Put a store online" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Make an online variant" })).toBeNull();
});
