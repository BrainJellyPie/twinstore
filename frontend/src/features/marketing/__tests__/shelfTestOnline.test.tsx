// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as marketing from "@/shared/api/marketing";
import type { ShelfTestReport, VariantChange } from "@/shared/api/marketing";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { ShelfTestReportView } from "../ShelfTest";

vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("@/shared/api/marketing", async (original) => ({ ...await original<typeof marketing>(), getStudyReading: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), listSites: vi.fn(), variantFromTest: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: ({ children }: { children: ReactNode }) => <a href="/online/p">{children}</a> }));
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const report: ShelfTestReport = {
  test_id: "st1", name: "Tea at eye level", setup_id: "s", rack_id: "r1", rack_name: "Drinks", face: "N", target_sku: "tea",
  target_name: "Green tea", model: "", currency: "USD", respondents: 40, errors: 0, applied: ["Green tea: moved to level 3"],
  warnings: [], comparisons: [], picks: [], choices: [], notes: [], seconds: 1,
};
const changes: VariantChange[] = [{ kind: "move", sku: "tea", rack_id: "r1", level: 3 } as VariantChange];

function show(withChanges: VariantChange[] | undefined) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ShelfTestReportView projectId="p" report={report} changes={withChanges} /></QueryClientProvider>);
}

it("tries a shelf test's changes in an online store", async () => {
  vi.mocked(marketing.getStudyReading).mockReturnValue(new Promise(() => {}));
  vi.mocked(online.listSites).mockResolvedValue([{ id: "s1", name: "Tea shop", currency: "USD" } as online.SiteSummary]);
  vi.mocked(online.variantFromTest).mockResolvedValue({
    site: { id: "v1", name: "Tea shop – Green tea" } as online.OnlineSite,
    applied: ["Green tea: first in its category, as on an eye-level shelf"], skipped: [],
  });
  show(changes);
  await screen.findByRole("option", { name: "Tea shop" });
  fireEvent.click(screen.getByRole("button", { name: "Make an online variant" }));
  expect(await screen.findByText("Green tea: first in its category, as on an eye-level shelf")).toBeTruthy();
  expect(online.variantFromTest).toHaveBeenCalledWith("p", "s1", {
    name: "Tea shop – Green tea", note: "Tea at eye level: Green tea", currency: "USD", changes,
  });
});

it("offers nothing when the test's changes are not known", () => {
  vi.mocked(marketing.getStudyReading).mockReturnValue(new Promise(() => {}));
  show(undefined);
  expect(screen.queryByRole("button", { name: "Make an online variant" })).toBeNull();
});
