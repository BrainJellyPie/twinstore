// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import type { Rack, Store } from "@/shared/types/domain";
import { ReviewBuildingFloors } from "../components/ReviewBuildingFloors";
import { DEFAULT_TEMPLATE_CHOICE, type BuildingFloorChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ previewStoreTemplate: vi.fn() }));
const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
const rack: Rack = { id: "counter", type: "counter", position: [1, 9], shape: [[1]], rotation: 0,
  levels: 1, dwell_min: 0, dwell_max: 0, rack_name: "Checkout", rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [],
};
const small: Store = { id: "small", name: "Juice bar", type: "cafe", currency: "USD", design_theme: "botanical", grid_size: [12, 10], weekly_schedule: [], racks: [rack] };
const large: Store = { ...small, id: "large", name: "Pizza restaurant", grid_size: [24, 18], design_theme: "terracotta", racks: [rack, { ...rack, id: "table", type: "table", position: [3, 3], shape: [[1, 1], [1, 1]] }] };
const floors: BuildingFloorChoice[] = [
  { label: "Juice", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "juice_bar" } },
  { label: "Pizza", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "pizzeria", width: 24, height: 18,
    requirements: "Keep my lighting brief", reserved_areas: [{ label: "Pickup", x: 2, y: 14, width: 3, height: 2 }] } },
];
beforeEach(() => { vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => request.template_id === "juice_bar" ? small : large); });

it("reviews resolved per-floor hours even when the choices use format defaults", async () => {
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => ({
    ...(request.template_id === "juice_bar" ? small : large),
    weekly_schedule: Array.from({ length: 7 }, (_, index) => ({ day: index + 1,
      is_open: request.template_id !== "juice_bar" || index !== 0,
      open_hour: request.template_id === "juice_bar" ? 10 : 0, close_hour: request.template_id === "juice_bar" ? 18 : 24 })),
  }));
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  await screen.findByText("2 of 2 floor previews ready");
  expect(within(screen.getByRole("region", { name: "1F · Juice" })).getByText("Operating hours: Mon: Closed; Tue–Sun: 10:00–18:00")).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "2F · Pizza" })).getByText("Operating hours: Every day: 00:00–24:00")).toBeTruthy();
});

function mount(value = floors) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const edit = vi.fn(), submit = vi.fn();
  render(<QueryClientProvider client={client}><form onSubmit={(event) => { event.preventDefault(); submit(); }}>
    <label>Building name<input defaultValue="My dining house" /></label>
    <ReviewBuildingFloors floors={value} onEdit={edit} />
  </form></QueryClientProvider>);
  return { edit, submit };
}

it("totals the actual two- and six-seat furniture on independent floors", async () => {
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => ({
    ...small, racks: [{ ...rack, type: "table", position: [3, 3],
      shape: request.template_id === "juice_bar" ? [[1], [1]] : [[1, 1, 1], [1, 1, 1]] }],
  }));
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  await screen.findByText("2 of 2 floor previews ready");
  expect(screen.getByText("240 total floor cells · 2 dining tables · 8 seats · 0 checkout counters")).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "1F · Juice" })).getByText(/1 dining tables · 2 seats/)).toBeTruthy();
  expect(within(screen.getByRole("region", { name: "2F · Pizza" })).getByText(/1 dining tables · 6 seats/)).toBeTruthy();
});

it("loads all floors on demand at the same scale, totals actual capacity and keeps settings", async () => {
  const { edit, submit } = mount();
  expect(api.previewStoreTemplate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  await screen.findByText("2 of 2 floor previews ready");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(2);
  expect(api.previewStoreTemplate).toHaveBeenCalledWith(expect.objectContaining({ template_id: "pizzeria", width: 24, height: 18 }), expect.any(AbortSignal));
  expect(vi.mocked(api.previewStoreTemplate).mock.calls.every(([request]) => !("requirements" in request))).toBe(true);
  expect(screen.getByText("552 total floor cells · 1 dining tables · 4 seats · 2 checkout counters")).toBeTruthy();
  expect(screen.getAllByRole("img", { name: "Floor plan preview" }).map((plan) => plan.getAttribute("viewBox"))).toEqual(["-0.2 -0.2 24.4 18.4", "-0.2 -0.2 24.4 18.4"]);
  expect(within(screen.getByRole("region", { name: "2F · Pizza" })).getByTestId("reserved-area-preview-0")).toBeTruthy();
  fireEvent.click(within(screen.getByRole("region", { name: "1F · Juice" })).getByRole("button", { name: "Expand floor plan" }));
  expect(screen.getByRole("img", { name: "Detailed floor plan" }).getAttribute("viewBox")).toBe("-1.2 -1.2 13.4 11.4");
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Floor plan details" })).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: "Edit floor 2" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull());
  expect(edit).toHaveBeenCalledWith(1);
  expect(submit).not.toHaveBeenCalled();
  expect((screen.getByLabelText("Building name") as HTMLInputElement).value).toBe("My dining house");
  expect(floors[1]!.choice.requirements).toBe("Keep my lighting brief");
});

it("shows a failed floor beside working floors and retries before showing totals", async () => {
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => {
    if (request.template_id === "pizzeria") throw new Error("Not enough room for 48 dining tables.");
    return small;
  });
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Not enough room");
  expect(screen.getByText("1 of 2 floor previews ready")).toBeTruthy();
  expect(screen.queryByText(/total floor cells/)).toBeNull();
  expect(screen.getAllByRole("img", { name: "Floor plan preview" })).toHaveLength(1);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue(large);
  fireEvent.click(screen.getByRole("button", { name: "Retry floor 2" }));
  await screen.findByText("2 of 2 floor previews ready");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("keeps invalid floor values local and offers a direct edit action", async () => {
  const { edit } = mount([floors[0]!, { label: "Invalid", choice: { ...floors[1]!.choice, width: 7 } }]);
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  await screen.findByText("1 of 2 floor previews ready");
  expect(vi.mocked(api.previewStoreTemplate).mock.calls.map(([request]) => request.template_id)).toEqual(["juice_bar"]);
  expect(within(screen.getByRole("region", { name: "2F · Invalid" })).getByRole("alert").textContent).toContain("Enter valid grid dimensions");
  fireEvent.click(screen.getByRole("button", { name: "Edit floor 2" }));
  expect(edit).toHaveBeenCalledWith(1);
});

it("reuses identical requests for duplicated floors but counts each floor separately", async () => {
  mount([floors[0]!, { ...floors[0]!, label: "Juice upstairs" }]);
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  await screen.findByText("2 of 2 floor previews ready");
  expect(vi.mocked(api.previewStoreTemplate).mock.calls.map(([request]) => request.template_id)).toEqual(["juice_bar"]);
  expect(screen.getByText("240 total floor cells · 0 dining tables · 0 seats · 2 checkout counters")).toBeTruthy();
  expect(screen.getAllByRole("img", { name: "Floor plan preview" })).toHaveLength(2);
});
