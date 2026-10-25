// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import type { SurveyReport } from "@/shared/api/marketing";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { SurveyReportView } from "../SurveyReport";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), listPackages: vi.fn(), getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), listSites: vi.fn(), variantFromTest: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: ({ children }: { children: ReactNode }) => <a href="/online/p">{children}</a> }));
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const report = {
  survey_id: "sv", name: "Tea packs", model: "m", stimuli: ["pkg_new", "pkg_old"], stimulus_names: ["Green box", "Old box"],
  questions: ["appeal"], currency: "USD", respondents: 10, errors: 0, scales: [], segments: [], price: null, preference: [],
  verbatims: [], answers: [], notes: [], seconds: 1,
} as unknown as SurveyReport;

it("puts a tested package that shows a store product onto that product in an online store", async () => {
  vi.mocked(api.listPackages).mockResolvedValue([
    { asset_id: "pkg_new", name: "Green box", width: 1, height: 1, sku: "tea" }, { asset_id: "pkg_old", name: "Old box", width: 1, height: 1 },
  ]);
  vi.mocked(online.listSites).mockResolvedValue([{ id: "s1", name: "Tea shop", currency: "USD" } as online.SiteSummary]);
  vi.mocked(online.variantFromTest).mockResolvedValue({ site: { id: "v1", name: "Tea shop – Green box package" } as online.OnlineSite,
    applied: ["Green tea: new package picture"], skipped: [] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SurveyReportView projectId="p" report={report} />
  </QueryClientProvider>);
  await screen.findByRole("option", { name: "Tea shop" });
  expect(screen.queryByRole("combobox", { name: "Package to put online" })).toBeNull();  // only one package is linked
  fireEvent.click(screen.getByRole("button", { name: "Make an online variant" }));
  expect(await screen.findByText("Green tea: new package picture")).toBeTruthy();
  expect(online.variantFromTest).toHaveBeenCalledWith("p", "s1", {
    name: "Tea shop – Green box package", note: "Tea packs: Green box package", currency: "USD",
    changes: [{ kind: "package", sku: "tea", asset_id: "pkg_new" }],
  });
});

it("offers nothing when no tested package shows a store product", async () => {
  vi.mocked(api.listPackages).mockResolvedValue([{ asset_id: "pkg_new", name: "Green box", width: 1, height: 1 }]);
  vi.mocked(online.listSites).mockResolvedValue([]);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SurveyReportView projectId="p" report={report} />
  </QueryClientProvider>);
  await new Promise((r) => setTimeout(r, 20));
  expect(screen.queryByText("Test it online")).toBeNull();
});
