// @vitest-environment jsdom
// Marketing studio, shelf capture and neighborhood pages in Korean: labels come from messages/studio.ts while the
// values sent to the API stay unchanged.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { CapturePage } from "@/features/capture/CapturePage";
import { MarketingPage } from "@/features/marketing/MarketingPage";
import { PriceChecks } from "@/features/marketing/PriceChecks";
import { TownPage } from "@/features/town/TownPage";
import * as api from "@/shared/api/client";
import { useLocale } from "../i18n";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  getProject: vi.fn(), getSetup: vi.fn(), getSetups: vi.fn(), getModels: vi.fn(),
  listCaptures: vi.fn(), getCapture: vi.fn(),
  getTown: vi.fn(), getTownDemand: vi.fn(), getScenarios: vi.fn(),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(),
  getMarketingInfo: vi.fn().mockResolvedValue({ currency: "USD" }),
  listExperiments: vi.fn().mockResolvedValue([]), listSurveys: vi.fn().mockResolvedValue([]),
  listPitches: vi.fn().mockResolvedValue([]), listShelfTests: vi.fn().mockResolvedValue([]),
  listConjoints: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/features/marketing/hooks", () => ({ usePackages: () => ({ data: [] }) }));
vi.mock("@/features/capture/ShelfLab", () => ({ BeforeAfter: () => null, ShelfLabPanel: () => null }));
vi.mock("@/features/capture/RivalCard", () => ({ RivalCard: () => null }));
vi.mock("@/features/town/TownMap", () => ({ TownMap: () => null }));
vi.mock("@/features/town/StorefrontCard", () => ({ StorefrontCard: () => null }));
vi.mock("@/features/town/VlmSynergyDialog", () => ({ VlmSynergyDialog: () => null }));

const clients: QueryClient[] = [];
const capture: api.CaptureStatus = {
  capture_id: "cap_test", status: "completed", stage: "done", progress: 1, error: "",
  options: { detector: "classic", model: "none", currency: "USD", rack_type: "shelf", label: "Tea" },
  image_name: "shelf.png", image_size: [100, 100], created_at: "", finished_at: "",
  items: 3, facings: 3, gaps: 0, levels: 1, applied_setup_ids: [],
};

beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getProject).mockResolvedValue({
    metadata: { currency: "USD" }, state: { activeSetupId: "s1" }, setups: [{ id: "s1", name: "Layout one", status: "draft" }], personas: [],
  } as never);
  vi.mocked(api.getSetup).mockResolvedValue({ id: "s1", name: "Layout one", status: "draft", store: { currency: "USD", racks: [] } } as never);
  vi.mocked(api.getSetups).mockResolvedValue([]);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.listCaptures).mockResolvedValue([]);
  vi.mocked(api.getCapture).mockResolvedValue({ status: capture, result: null });
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getTownDemand).mockImplementation(() => new Promise(() => {}));
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  useLocale.getState().setLocale("ko");
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.clearAllMocks();
  vi.restoreAllMocks();
  useLocale.getState().setLocale("en");
});

async function mount(page: () => ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  clients.push(client);
  const root = createRootRoute({ component: page });
  const router = createRouter({ routeTree: root, history: createMemoryHistory({ initialEntries: ["/"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

it("shows the marketing studio in Korean", async () => {
  await mount(() => <MarketingPage projectId="p" />);
  expect((await screen.findByRole("heading", { level: 1 })).textContent).toBe("마케팅 스튜디오");
  expect(screen.getByRole("tab", { name: "A/B 테스트" })).toBeTruthy();
  expect(screen.getByRole("tab", { name: "컨조인트 분석" })).toBeTruthy();
  expect(screen.getByRole("tab", { name: "연구 계획서" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "새 A/B 테스트" })).toBeTruthy();
  expect(screen.queryByRole("tab", { name: "A/B tests" })).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "가격 점검" }));
  expect(await screen.findByRole("region", { name: "선반·계산대 가격 점검" })).toBeTruthy();
});

it("shows a price-check review form in Korean", async () => {
  await mount(() => <PriceChecks projectId="p" />);
  const review = await screen.findByRole("button", { name: "가격 점검 검토" });
  expect((review as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByLabelText("매장 참조값")).toBeTruthy();
  expect(screen.getByLabelText("점검일")).toBeTruthy();
  expect(screen.getByLabelText("가격표 관찰 CSV")).toBeTruthy();
  expect(screen.getByRole("button", { name: "가격 점검 템플릿 받기" })).toBeTruthy();
});

it("shows the shelf capture upload queue in Korean", async () => {
  await mount(() => <CapturePage projectId="p" />);
  expect(await screen.findByRole("heading", { name: "선반 사진 한꺼번에 추가" })).toBeTruthy();
  expect(screen.getByRole("region", { name: "사진 업로드 대기열" })).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "상품 찾기 방식" })).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "진열대 종류" })).toBeTruthy();
  expect((screen.getByRole("option", { name: "선반 / 곤돌라" }) as HTMLOptionElement).value).toBe("shelf");
  expect(screen.getByRole("button", { name: "사진을 선택하거나 여기로 끌어다 놓으세요" })).toBeTruthy();
});

it("shows a saved capture with Korean tabs and labels", async () => {
  vi.mocked(api.listCaptures).mockResolvedValue([capture]);
  await mount(() => <CapturePage projectId="p" />);
  expect(await screen.findByRole("img", { name: "선반 사진" })).toBeTruthy();
  expect(screen.getByText("사진 추가")).toBeTruthy();
  expect(screen.getByText("플래노그램")).toBeTruthy();
  expect(screen.getByText("선반 실험실")).toBeTruthy();
  expect(screen.getByText("선반을 읽는 중…")).toBeTruthy();
});

it("shows the neighborhood page in Korean", async () => {
  await mount(() => <TownPage projectId="p" />);
  expect(await screen.findByRole("link", { name: "매장으로 돌아가기" })).toBeTruthy();
  expect(await screen.findByText("매장을 주변 지역에 배치해 보세요")).toBeTruthy();
  expect(screen.getByText("가상 동네 만들기")).toBeTruthy();
  expect(screen.getByText("실제 지도 (OpenStreetMap)")).toBeTruthy();
  expect(screen.getByRole("button", { name: "생성" })).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/Back to store|Generate a neighborhood|Place the store/);
});
