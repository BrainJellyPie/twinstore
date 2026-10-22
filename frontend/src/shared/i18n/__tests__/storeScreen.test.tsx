// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { DashboardPanel } from "@/features/dashboard/components/DashboardPanel";
import { SettingsPanel } from "@/features/dashboard/components/SettingsPanel";
import { TimeBar } from "@/features/playback/components/TimeBar";
import { formatWeeklyHours } from "@/features/layouts/weeklyHours";
import type { RunSummary } from "@/shared/api/client";
import type { CustomerResult, Store } from "@/shared/types/domain";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { useLocale } from "../i18n";
import { LOCALES } from "../messages";
import { storeTypeLabel, templateName } from "../storeLabels";
import { clockTime, weekdayShort } from "../timeFormat";

const store: Store = { id: "store", name: "Corner", type: "Convenience store", grid_size: [8, 8], racks: [], weekly_schedule: [
  ...[1, 2, 3, 4, 5].map((day) => ({ day, is_open: true, open_hour: 7, close_hour: 24 })),
  { day: 6, is_open: true, open_hour: 10, close_hour: 20 },
  { day: 7, is_open: false, open_hour: 0, close_hour: 0 },
] };
const summary: RunSummary = { total_customers: 3000, total_revenue: 500000, top_products: [], by_purpose: {}, by_identity: {}, by_age: {}, by_gender: {},
  currency: "KRW", buyers: 1500, conversion_rate: 0.5, impulse_revenue_share: 0.2, units_sold: 4200 };
const customers = [1, 2, 3].map((day) => ({ persona_id: `p${day}`, day, arrival_time: "09:00:00", leave_time: "09:05:00", total_spent: 0, timeline: [] })) as CustomerResult[];

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }));
  usePlaybackControlStore.getState().reset();
  useSimulationMetricsStore.getState().reset();
  useSimulationStore.getState().reset();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); });

it("shows the playback panel in Korean", () => {
  useLocale.getState().setLocale("ko");
  render(<TimeBar minTime={28800} maxTime={72000} hasDwell hasRackStats />);
  const panel = screen.getByRole("region", { name: "재생 컨트롤" });
  expect(within(panel).getByText("1일차 · 월")).toBeTruthy();
  expect(within(panel).getByText("속도")).toBeTruthy();
  expect(within(panel).getByText("레이어")).toBeTruthy();
  expect(within(panel).getByRole("radio", { name: "보통" })).toBeTruthy();
  expect(within(panel).getByRole("radio", { name: "체류" })).toBeTruthy();
  expect(within(panel).getByRole("radio", { name: "실사" })).toBeTruthy();
  expect(within(panel).getByRole("button", { name: "고객 시점" })).toBeTruthy();
  expect(within(panel).getByRole("slider", { name: "하루 중 시각 이동" })).toBeTruthy();
  expect(panel.textContent).toContain(clockTime(28800, "ko"));
  expect(panel.textContent).not.toMatch(/Speed|Layer|Footfall| am\b/);
  fireEvent.click(within(panel).getByRole("button", { name: "재생" }));
  expect(within(panel).getByRole("button", { name: "일시정지" })).toBeTruthy();
});

it("shows the run dashboard and its KPI notes in Korean", () => {
  useLocale.getState().setLocale("ko");
  useSimulationMetricsStore.getState().setMetrics({ entered: 10, paidCount: 5, revenue: 5000, impulseRevenue: 1000 });
  render(<DashboardPanel mode="playback" customers={customers} minTime={28800} maxTime={72000} store={store} summary={summary} />);
  for (const text of ["시간대별 방문", "현재까지 매출", "객단가", "방문객", "구매 전환", "실행 결과", "진열대", "인기 상품"]) {
    expect(screen.getAllByText(text).length, text).toBeGreaterThan(0);
  }
  expect(screen.getByText("3일간 합계:", { exact: false }).textContent).toBe("3일간 합계: 고객 3,000명 (하루 약 1,000명) · 매출 ₩500,000 · 판매 수량 4,200개");
  expect(screen.getByText("구매 전환율")).toBeTruthy();
  expect(screen.getByText("고객이 결제할 때마다 진열대 순위가 채워집니다.")).toBeTruthy();
  expect(screen.queryByText(/Totals over|Run results|Revenue so far/)).toBeNull();
});

it("shows the Store tab with localized store type and opening hours", () => {
  useLocale.getState().setLocale("ko");
  render(<SettingsPanel store={store} summary={null} personas={[]} location="Seoul" />);
  expect(screen.getByText("매장 정보")).toBeTruthy();
  expect(screen.getByText("매장 유형").nextElementSibling!.textContent).toBe("편의점");
  expect(screen.getByText("영업시간").nextElementSibling!.textContent).toBe("월–금: 07:00–24:00; 토: 10:00–20:00; 일: 휴무");
});

it.each(LOCALES)("labels the sample store's type and store formats in $code", ({ code }) => {
  expect(storeTypeLabel("Convenience store", code)).toBe(storeTypeLabel("convenience", code));
  expect(storeTypeLabel("café", code)).toBe(storeTypeLabel("cafe", code));
  expect(templateName("unknown_format", "Server name", code)).toBe("Server name");
  expect(templateName("urban_cvs", "Urban convenience store", code)).toBe(code === "en" ? "Urban convenience store" : templateName("urban_cvs", "", code));
  expect(formatWeeklyHours([], code).trim()).not.toBe("");
  expect(weekdayShort(8, code)).toBe(weekdayShort(1, code));
});

it("keeps English store clocks and weekday names unchanged", () => {
  expect(clockTime(0, "en")).toBe("12:00 am");
  expect(clockTime(13 * 3600 + 5 * 60, "en")).toBe("1:05 pm");
  expect(weekdayShort(1, "en")).toBe("Mon");
  expect(weekdayShort(7, "en")).toBe("Sun");
  expect(templateName("urban_cvs", "Urban convenience store", "ko")).toBe("도심형 편의점");
});
