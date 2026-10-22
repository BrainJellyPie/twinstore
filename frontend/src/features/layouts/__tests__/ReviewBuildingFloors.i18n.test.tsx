// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";
import type { Store } from "@/shared/types/domain";
import { ReviewBuildingFloors } from "../components/ReviewBuildingFloors";
import { DEFAULT_TEMPLATE_CHOICE, type BuildingFloorChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ previewStoreTemplate: vi.fn() }));
let client: QueryClient;
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
const store: Store = { id: "raw-preview", name: "Original store", type: "store", grid_size: [12, 10], racks: [], weekly_schedule: [] };
const floors: BuildingFloorChoice[] = [
  { label: "茶 & <Books> 🛒", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "urban_cvs", reserved_areas: [{ label: "受け取り", x: 1, y: 7, width: 3, height: 2 }] } },
  { label: "Café — 원문", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "book_cafe" } },
];
beforeEach(() => {
  useLocale.getState().setLocale("en");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.previewStoreTemplate).mockResolvedValue(store);
});
afterEach(() => { cleanup(); client.clear(); vi.resetAllMocks(); useLocale.getState().setLocale("en"); });
function mount() {
  const edit = vi.fn();
  render(<QueryClientProvider client={client}><ReviewBuildingFloors floors={floors} onEdit={edit} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: t("layReviewAllFloors") }));
  return edit;
}
it.each(LOCALES)("reviews floor labels and zero/one counts in $code without changing user names or requests", async ({ code }) => {
  useLocale.getState().setLocale(code);
  const original = JSON.stringify(floors), edit = mount();
  await screen.findByText(t("layFloorPreviewsReady", { ready: 2, total: 2 }));
  expect(screen.getByText(t("layBuildingTotals", { cells: 240, tables: 0, seats: 0, checkouts: 0 }))).toBeTruthy();
  for (const [index, floor] of floors.entries()) {
    const section = within(screen.getByRole("region", { name: t("layNamedFloor", { number: index + 1, name: floor.label }) }));
    expect(section.getByText(content => content.endsWith(t("layReservedAreaCount", { count: index === 0 ? 1 : 0 })))).toBeTruthy();
  }
  expect(vi.mocked(api.previewStoreTemplate).mock.calls[0]![0].reserved_areas).toEqual(floors[0]!.choice.reserved_areas);
  act(() => useLocale.getState().setLocale(code === "fr" ? "ko" : "fr"));
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("region", { name: t("layNamedFloor", { number: 1, name: floors[0]!.label }) })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("layEditFloorNumber", { number: 2 }) }));
  expect(edit).toHaveBeenCalledWith(1);
  expect(JSON.stringify(floors)).toBe(original);
});
it("translates a pending floor failure and retries its exact settings beside the successful floor", async () => {
  let reject!: (error: Error) => void;
  vi.mocked(api.previewStoreTemplate).mockImplementation(request => request.template_id === "urban_cvs"
    ? Promise.resolve(store) : new Promise((_resolve, fail) => { reject = fail; }));
  mount();
  await screen.findByText(t("layFloorPreviewsReady", { ready: 1, total: 2 }));
  act(() => useLocale.getState().setLocale("ja"));
  await act(async () => reject(new ApiError("Original diagnostic <floor> 原文", 422)));
  await screen.findByText(t("requestInvalid"));
  expect(screen.getAllByRole("img", { name: t("planPreviewImage") })).toHaveLength(1);
  expect(screen.queryByText(t("layBuildingTotals", { cells: 240, tables: 0, seats: 0, checkouts: 0 }))).toBeNull();
  fireEvent.click(screen.getByText(t("requestDetails")));
  expect(screen.getByText("Original diagnostic <floor> 原文")).toBeTruthy();
  const originalRequest = vi.mocked(api.previewStoreTemplate).mock.calls[1]![0];
  act(() => useLocale.getState().setLocale("es"));
  expect(screen.getByText(t("requestInvalid"))).toBeTruthy();
  vi.mocked(api.previewStoreTemplate).mockResolvedValue(store);
  fireEvent.click(screen.getByRole("button", { name: t("layRetryFloor", { number: 2 }) }));
  await screen.findByText(t("layFloorPreviewsReady", { ready: 2, total: 2 }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenCalledTimes(3));
  expect(vi.mocked(api.previewStoreTemplate).mock.calls[2]![0]).toEqual(originalRequest);
  expect(screen.queryByRole("alert")).toBeNull();
});
