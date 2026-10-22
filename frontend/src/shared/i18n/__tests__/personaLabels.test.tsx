// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { getJourney, type Journey } from "@/shared/api/interview";
import type { RunSummary } from "@/shared/api/client";
import type { CustomerResult, Persona, Store } from "@/shared/types/domain";
import { ShopperPanel } from "@/features/shoppers/ShopperPanel";
import { RunKpis } from "@/features/runs/components/RunKpis";
import { SettingsPanel } from "@/features/dashboard/components/SettingsPanel";
import { useLocale, translate } from "../i18n";
import { LOCALES } from "../messages";
import { AGE_GROUPS, GENDERS, ageBadge, personaLabel } from "../personaLabels";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(), getJourney: vi.fn(), listGroups: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]) }));
beforeEach(() => { vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} })); });
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); });

const persona = { id: "p1", identity: "Office worker", age_group: "40s", gender: "Female", purpose: "Lunch", day: 1 } as unknown as Persona;
const customer = {
  persona_id: "p1", day: 1, arrival_time: "12:00:00", leave_time: "12:10:00", total_spent: 3573,
  timeline: [{ elapsed_sec: 0, x: 0, y: 0, action: "buy", quantity: 7, target_rack: "r1" }],
} as unknown as CustomerResult;
const store = { id: "s", name: "Corner", type: "convenience", grid_size: [8, 8], racks: [], weekly_schedule: [] } as unknown as Store;

it.each(LOCALES)("labels every age group and gender in $code, with a short badge form", ({ code }) => {
  const t = (key: Parameters<typeof translate>[1], values?: Record<string, string | number>) => translate(code, key, values);
  for (const value of [...AGE_GROUPS, ...GENDERS]) expect(personaLabel(value, t).trim()).not.toBe("");
  for (const value of AGE_GROUPS) expect(ageBadge(value, t).length).toBeLessThanOrEqual(6);
  expect(personaLabel("Nonbinary", t)).toBe("Nonbinary");
  expect(ageBadge("70s", t)).toBe("70s");
  if (code === "en") expect([personaLabel("40s", t), personaLabel("Female", t), ageBadge("60s+", t)]).toEqual(["40s", "Female", "60s+"]);
});

it("shows the shopper list badge and the detail line in Korean, with the item unit", async () => {
  useLocale.getState().setLocale("ko");
  vi.mocked(getJourney).mockResolvedValue({
    run_id: "r", persona, day: 1, arrival_time: "12:00:00", leave_time: "12:10:00", engine_type: "rule_based", currency: "USD",
    total_spent: 3573, units: 7, steps: [], path: [], shelves: {},
  } as Journey);
  render(<QueryClientProvider client={new QueryClient()}>
    <ShopperPanel projectId="p" runId="r" customers={[customer]} personas={[persona]} store={store} />
  </QueryClientProvider>);
  const item = screen.getByRole("listitem");
  expect(within(item).getByText("40대")).toBeTruthy();
  expect(item.textContent).not.toContain("40s");
  fireEvent.click(within(item).getByRole("button"));
  const detail = await screen.findByText(/40대 · 여성 · 1일차/);
  expect(detail.textContent).not.toMatch(/40s|Female/);
  expect(screen.getByText("US$35.73 · 7개")).toBeTruthy();
});

const summary: RunSummary = {
  total_customers: 10, total_revenue: 1000, top_products: [], by_purpose: { Lunch: 10 }, by_identity: {}, by_age: { "40s": 6, "20s": 4 },
  by_gender: { Female: 7, Male: 3 }, currency: "USD", buyers: 5, conversion_rate: 0.5, impulse_revenue_share: 0.1, units_sold: 12,
  segments: {
    age_group: { "40s": { visitors: 6, conversion_rate: 0.5, revenue_per_visitor: 100 }, "60s+": { visitors: 4, conversion_rate: 0.5, revenue_per_visitor: 100 } },
    gender: { Female: { visitors: 7, conversion_rate: 0.5, revenue_per_visitor: 100 }, Male: { visitors: 3, conversion_rate: 0.5, revenue_per_visitor: 100 } },
  },
} as unknown as RunSummary;

it("translates age groups and genders in the Results segments", () => {
  useLocale.getState().setLocale("ko");
  render(<RunKpis summary={summary} days={1} />);
  expect(screen.getByText("40대")).toBeTruthy();
  expect(screen.getByText("60대 이상")).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: "성별" }));
  expect(screen.getByText("여성")).toBeTruthy();
  expect(screen.getByText("남성")).toBeTruthy();
  expect(screen.queryByText(/^(40s|Female|Male)$/)).toBeNull();
});

it("translates the Store tab's age and gender breakdown and keeps purposes as written", () => {
  useLocale.getState().setLocale("ko");
  render(<SettingsPanel store={store} summary={summary} personas={[persona]} location="Seoul" />);
  fireEvent.click(screen.getByRole("radio", { name: "연령대" }));
  expect(screen.getByText("40대")).toBeTruthy();
  expect(screen.getByText("20대")).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: "성별" }));
  expect(screen.getByText("여성")).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: "방문 목적" }));
  expect(screen.getByText("Lunch")).toBeTruthy();
});
