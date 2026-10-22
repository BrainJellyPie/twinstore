// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { BuildingPicker } from "../components/BuildingPicker";
import { applyLayoutPriority, DEFAULT_TEMPLATE_CHOICE, LAYOUT_PRIORITIES, type BuildingFloorChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "urban_cvs", name: "City store", description: "Groceries", store_type: "convenience", grid: [12, 10], racks: 10, skus: 40,
      open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => {
    if (request.dining_tables === 6 && (request.width ?? 12) < 20) throw new Error("Six dining tables do not fit this floor.");
    return { id: request.template_id, name: "Floor", type: "store", grid_size: [request.width ?? 12, request.height ?? 10], weekly_schedule: [], racks: [] };
  });
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
const walls = ["front", "back", "left", "right"] as const;
const initial: BuildingFloorChoice[] = walls.map((wall, i) => ({ label: `Floor ${i + 1}`, choice: {
  ...DEFAULT_TEMPLATE_CHOICE, width: 32 + i, height: 28, gate_wall: wall, checkout_wall: "right", seed: i,
  currency: i % 2 ? "JPY" : "USD", design_theme: i % 2 ? "nordic" : "coastal", table_rotation: i % 2 ? 90 : 0,
  open_hour: i, close_hour: 20 + i, closed_days: [i + 1], products_per_category: i + 1,
  requirements: `Keep corner ${i + 1}`, reserved_areas: [{ label: "Pickup", x: 24, y: 20, width: 2, height: 2 }],
  dining_tables: 3, table_mix: { two_seat: 1, four_seat: 1, six_seat: 1 },
} }));
function Building({ starting }: { starting: BuildingFloorChoice[] }) {
  const [floors, setFloors] = useState(starting);
  return <><BuildingPicker floors={floors} onChange={setFloors} /><output data-testid="floors">{JSON.stringify(floors)}</output></>;
}
async function mount(starting = initial) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><Building starting={starting} /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Apply a layout priority"));
}
const floors = (): BuildingFloorChoice[] => JSON.parse(screen.getByTestId("floors").textContent!);
const select = (id: string) => fireEvent.change(screen.getByLabelText("Layout priority"), { target: { value: id } });
const apply = () => fireEvent.click(screen.getByRole("button", { name: "Apply priority to all floors" }));
async function closeReview() {
  fireEvent.click(within(screen.getByRole("dialog", { name: "Review building floors" })).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull());
}

it("applies the selected priority only on request, follows every entrance wall and opens review", async () => {
  await mount(); select("mixed_parties");
  expect(floors()).toEqual(initial);
  expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull();
  apply(); await screen.findByText("Floor previews ready: 4/4");
  floors().forEach((floor, i) => {
    const before = initial[i]!;
    expect(floor.label).toBe(before.label);
    expect(floor.choice).toMatchObject({ ...before.choice, style: "perimeter", density: "balanced", dining_tables: 6, dining_seats: 4,
      table_mix: { two_seat: 2, four_seat: 2, six_seat: 2 }, table_clearance: 1, seating_zone: "center", checkouts: 2,
      checkout_clearance: 1, checkout_placement: "near_entrance", checkout_wall: walls[i], aisle_width: null, max_shelf_run: null });
  });
  await closeReview();
  fireEvent.click(screen.getByRole("button", { name: "2F · Floor 2" }));
  fireEvent.click(screen.getByText("Mixed table sizes · 6 tables"));
  fireEvent.change(screen.getByLabelText("2-seat tables"), { target: { value: "3" } });
  expect(floors().map((floor) => floor.choice.table_mix?.two_seat)).toEqual([2, 3, 2, 2]);
  expect(floors().map((floor) => floor.choice.dining_tables)).toEqual([6, 7, 6, 6]);
});

it("switches all mixed floors to no seating and then uniform family tables", async () => {
  await mount(); select("service_points"); apply(); await screen.findByText("Floor previews ready: 4/4");
  expect(floors().every((floor) => floor.choice.dining_tables === 0 && floor.choice.table_mix?.two_seat === 0 && floor.choice.table_mix?.four_seat === 0 && floor.choice.table_mix?.six_seat === 0)).toBe(true);
  await closeReview(); select("family_dining"); apply(); await screen.findByText("Floor previews ready: 4/4");
  expect(floors().every((floor) => floor.choice.dining_tables === 6 && floor.choice.dining_seats === 6 && floor.choice.table_mix === null)).toBe(true);
  expect(floors().map((floor) => floor.choice.table_rotation)).toEqual([0, 90, 0, 90]);
});

it("shows a small upper floor's capacity error and supports independent recovery", async () => {
  await mount([initial[0]!, { ...initial[1]!, choice: { ...initial[1]!.choice, width: 8, height: 6, dining_tables: 0, table_mix: null, reserved_areas: [] } }]);
  select("family_dining"); apply();
  const review = screen.getByRole("dialog", { name: "Review building floors" });
  expect(await within(review).findByText(/Six dining tables do not fit/)).toBeTruthy();
  expect(floors()[1]!.choice.width).toBe(8);
  fireEvent.click(within(review).getByRole("button", { name: "Edit floor 2" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull());
  expect(screen.getByRole("button", { name: "2F · Floor 2" }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "30" } });
  fireEvent.change(screen.getByLabelText("Depth (6–40 cells)"), { target: { value: "28" } });
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  await screen.findByText("Floor previews ready: 2/2");
  expect(floors().map((floor) => floor.choice.width)).toEqual([32, 30]);
});

it("applies to six floors while keeping the single-floor action independent", async () => {
  const six = Array.from({ length: 6 }, (_, i) => ({ ...initial[i % 4]!, label: `Floor ${i + 1}` }));
  await mount(six); select("wide");
  fireEvent.click(screen.getByRole("button", { name: "Apply priority" }));
  expect(floors()[0]!.choice.style).toBe("cross"); expect(floors().slice(1)).toEqual(six.slice(1));
  expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull();
  apply(); await screen.findByText("Floor previews ready: 6/6");
  expect(floors().every((floor) => floor.choice.style === "cross" && floor.choice.aisle_width === 3)).toBe(true);
  expect(floors().every((floor) => floor.choice.dining_tables === 3 && floor.choice.checkout_wall === "right")).toBe(true);
});

it("does not hide invalid dimensions on another floor when applying a priority", async () => {
  await mount([initial[0]!, { ...initial[1]!, choice: { ...initial[1]!.choice, width: 7 } }]);
  select("open"); apply(); await screen.findByText("Floor previews ready: 1/2");
  expect(within(screen.getByRole("dialog", { name: "Review building floors" })).getByText(/Enter valid grid dimensions/)).toBeTruthy();
  expect(floors()[1]!.choice.width).toBe(7);
});

it("keeps mixed counts independent from the preset and from another floor", () => {
  const priority = LAYOUT_PRIORITIES.find((p) => p.id === "mixed_parties")!;
  const first = applyLayoutPriority(initial[0]!.choice, priority);
  const second = applyLayoutPriority(initial[1]!.choice, priority);
  expect(first.table_mix).not.toBe(second.table_mix);
  expect(first.table_mix).not.toBe(priority.options.table_mix);
  first.table_mix!.two_seat = 4;
  expect(second.table_mix!.two_seat).toBe(2);
  expect(priority.options.table_mix!.two_seat).toBe(2);
  expect(initial[0]!.choice.table_mix!.two_seat).toBe(1);
});
