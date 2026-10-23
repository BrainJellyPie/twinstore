// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { starterCategoryLabel } from "@/shared/i18n/catalogCategories";
import type { Store } from "@/shared/types/domain";
import { BuildingPicker } from "../components/BuildingPicker";
import { buildingPreset } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn(), validateLayoutPreset: vi.fn(), validateBuildingPreset: vi.fn() }));

// Custom server descriptions stay as sent; known category labels are translated. Currency codes, color codes, key
// names in the keyboard hint and the plan's IN/OUT marks.
const SERVER_TEXT = ["Gifts and beauty"];
const ALLOWED = /#[0-9a-f]{6}\b|\b(USD|KRW|JPY|IN|OUT|INOUT|SVG|Home|End|Enter|Space|Tab)\b/gi;

function englishLeft(root: HTMLElement): string[] {
  const parts = [root.textContent ?? ""];
  for (const element of root.querySelectorAll("*")) {
    for (const name of ["aria-label", "placeholder", "title"]) {
      const value = element.getAttribute(name);
      if (value) parts.push(value);
    }
  }
  let text = parts.join(" ");
  for (const server of SERVER_TEXT) text = text.split(server).join(" ");
  return text.replace(ALLOWED, " ").match(/[A-Za-z]{3,}/g) ?? [];
}

function Building() {
  const locale = useLocale((state) => state.locale);
  const [floors, setFloors] = useState(() => buildingPreset("department", "USD", locale));
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <BuildingPicker floors={floors} onChange={setFloors} defaultCurrency="USD" />
  </QueryClientProvider>;
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "beauty_flagship", name: "Beauty flagship", description: "Gifts and beauty", store_type: "cosmetics", grid: [12, 10], racks: 10, skus: 40,
      open_hours: [10, 22], default_style: "showroom", default_design: "luxury", default_dining_tables: 2, default_seating_zone: "back",
      default_checkout_placement: "near_entrance", categories: [{ id: "soft_drinks", label: "Drinks" }, { id: "beer_alcohol", label: "Beer & Alcohol" }, { id: "household", label: "Household & Daily" }] },
  ]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Beauty flagship", type: "cosmetics", grid_size: [12, 10], design_theme: "luxury",
    weekly_schedule: [{ day: 1, is_open: true, open_hour: 10, close_hour: 22 }],
    racks: [
      { id: "s1", type: "shelf", rack_name: "", shape: [[1]], position: [2, 2], rotation: 0, levels: 4, slots: [] },
      { id: "in", type: "entrance", rack_name: "", shape: [[1]], position: [0, 9], rotation: 0, levels: 0, slots: [] },
      { id: "out", type: "exit", rack_name: "", shape: [[1]], position: [0, 9], rotation: 0, levels: 0, slots: [] },
    ] } as unknown as Store);
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

it("shows the new-store layout customization panel, its building floors and floor-plan dialogs in Korean", async () => {
  useLocale.getState().setLocale("ko");
  const ko = (key: Parameters<typeof translate>[1], params?: Parameters<typeof translate>[2]) => translate("ko", key, params);
  const { container } = render(<Building />);
  expect(screen.getByRole("button", { name: "1층 · 뷰티 플래그십 스토어" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "백화점" })).toBeTruthy();
  await screen.findByRole("button", { name: ko("planExpand") });
  fireEvent.click(screen.getByRole("button", { name: "비워 둘 구역 추가" }));
  fireEvent.click(screen.getByLabelText(ko("templateHoursIndividual")));
  fireEvent.click(screen.getByLabelText("테이블 크기 섞어 쓰기"));
  fireEvent.click(screen.getByRole("button", { name: "층 복제" }));

  for (const text of ["배치 우선순위 적용", "배치 패턴", "진열 밀도", "최대 연속 진열 길이", "입구 벽", "계산대 위치", ko("layInteriorDesignRealistic"),
    "식사 테이블 (크기 혼합)", ko("templateSeed"), "배치 설정 초기화", "비워 둘 구역 만들기", "구역 1", "월요일", ko("templateOpens"), ko("templateCloses"), ko("layCustomColors"),
    "모든 층에 크기 적용", ko("templateHoursApply"), "설정 내보내기", ko("optionsImportBuilding")]) {
    expect(container.textContent, text).toContain(text);
  }
  expect(screen.getByRole("option", { name: "템플릿 기본값 (뒤쪽 벽)" })).toBeTruthy();
  expect(screen.getByRole("option", { name: "템플릿 기본값 (입구 가까이)" })).toBeTruthy();
  expect(screen.getByText("기본 패턴: 쇼룸형 그룹 진열")).toBeTruthy();
  expect(screen.getByText(translate("ko", "layDefaultDesign", { design: ko("planDesignLuxury") }))).toBeTruthy();
  expect(screen.getByRole("spinbutton", { name: translate("ko", "templateProductsFor", { category: starterCategoryLabel("soft_drinks", "Drinks", "ko") }) })).toBeTruthy();
  expect(screen.getByRole("button", { name: "2층 · 뷰티 플래그십 스토어 사본 1" })).toBeTruthy();
  expect(englishLeft(container)).toEqual([]);

  fireEvent.click(await screen.findByRole("button", { name: ko("planExpand") }));
  const details = await screen.findByRole("dialog", { name: ko("planDetails") });
  expect(details.textContent).toContain("뷰티 플래그십 스토어 · 12×10칸");
  expect(details.textContent).toContain(ko("planCounts", { displays: 0, tables: 0, seats: 0, counters: 0 }));
  expect(details.textContent).toContain("영업시간: 월: 10:00–22:00; 화–일: 휴무");
  expect(within(details).getByRole("button", { name: ko("planFit") })).toBeTruthy();
  expect(within(details).getByRole("button", { name: ko("planDownload") })).toBeTruthy();
  expect(englishLeft(details)).toEqual([]);
  act(() => fireEvent.keyDown(details, { key: "Escape" }));

  fireEvent.click(await screen.findByRole("button", { name: ko("compareWithDefault") }));
  const compare = await screen.findByRole("dialog", { name: ko("planCompareTitle") });
  const table = await within(compare).findByRole("table", { name: ko("planCompareTable") });
  for (const row of ["planCompareSize", "planCompareDisplays", "planCompareProducts", "planCompareSeating", "planCompareCounters",
    "planCompareAreas", "planCompareDesign", "planCompareHours"] as const) {
    expect(within(table).getByRole("rowheader", { name: ko(row) })).toBeTruthy();
  }
  expect(within(table).getAllByText("차콜·브라스").length).toBeGreaterThan(0);
  expect(englishLeft(compare)).toEqual([]);
}, 20_000);

it("keeps English option text unchanged", async () => {
  render(<Building />);
  expect(screen.getByRole("button", { name: "1F · Ground · Beauty" })).toBeTruthy();
  await screen.findByRole("button", { name: "Expand floor plan" });
  expect(screen.getByRole("option", { name: "Format default (back wall)" })).toBeTruthy();
  expect(screen.getByText("Default pattern: Showroom groups")).toBeTruthy();
  expect(screen.getByLabelText("Products for Drinks")).toBeTruthy();
});
