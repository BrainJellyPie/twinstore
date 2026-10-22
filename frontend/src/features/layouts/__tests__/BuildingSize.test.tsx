// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { BuildingPicker } from "../components/BuildingPicker";
import { DEFAULT_TEMPLATE_CHOICE, type BuildingFloorChoice, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "airport_shopping_gallery", name: "Airport shopping", description: "Travel gifts", store_type: "travel", grid: [30, 24], racks: 50, skus: 80,
      open_hours: [0, 24], default_style: "loop", default_design: "luxury", default_dining_tables: 0 },
    { id: "evening_food_court", name: "Evening dining", description: "Dining", store_type: "restaurant", grid: [32, 26], racks: 30, skus: 80,
      open_hours: [16, 24], default_style: "perimeter", default_design: "terracotta", default_dining_tables: 12 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => {
    if (request.template_id === "evening_food_court" && request.width != null && request.width < 20) throw new Error("Twelve tables cannot fit this floor.");
    return { id: request.template_id, name: request.template_id, type: "store", grid_size: [request.width ?? 30, request.height ?? 24], weekly_schedule: [], racks: [] };
  });
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
const initial: BuildingFloorChoice[] = [
  { label: "Shopping", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "airport_shopping_gallery", currency: "JPY", seed: 3, design_theme: "nordic", requirements: "Leave a quiet corner", open_hour: 6, close_hour: 20, closed_days: [7] } },
  { label: "Dining", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "evening_food_court", seed: 9, dining_tables: 12, checkout_clearance: 2,
    reserved_areas: [{ label: "Kitchen", x: 24, y: 20, width: 3, height: 2 }] } },
];
function Building({ patch = {} }: { patch?: Partial<TemplateChoice> }) {
  const [floors, setFloors] = useState(() => initial.map((f, i) => ({ ...f, choice: { ...f.choice, ...(i === 0 ? patch : {}) } })));
  return <><BuildingPicker floors={floors} onChange={setFloors} /><output data-testid="floors">{JSON.stringify(floors)}</output></>;
}
async function mount(patch: Partial<TemplateChoice> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><Building patch={patch} /></QueryClientProvider>);
  await waitFor(() => expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).placeholder).toBe("30"));
}
const floors = (): BuildingFloorChoice[] => JSON.parse(screen.getByTestId("floors").textContent!);
const apply = () => screen.getByRole("button", { name: "Apply size to all floors" }) as HTMLButtonElement;
async function closeReview() {
  fireEvent.click(within(screen.getByRole("dialog", { name: "Review building floors" })).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull());
}

it("copies effective source dimensions, preserves other choices and opens review immediately", async () => {
  await mount();
  fireEvent.click(screen.getByRole("button", { name: "Hide layout settings" }));
  fireEvent.click(apply());
  expect(floors()).toEqual(initial.map((f) => ({ ...f, choice: { ...f.choice, width: 30, height: 24 } })));
  expect(await screen.findByText("Floor previews ready: 2/2")).toBeTruthy();
  await closeReview();
  expect((screen.getByRole("button", { name: "Size used on all floors" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "2F · Dining" }));
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "32" } });
  expect(floors().map((f) => f.choice.width)).toEqual([30, 32]);
  fireEvent.click(apply());
  await screen.findByText("Floor previews ready: 2/2");
  expect(floors().map((f) => f.choice.width)).toEqual([32, 32]);
});

it("shows a later floor's capacity error and lets the user edit that floor without changing the others", async () => {
  await mount({ width: 8, height: 6 });
  fireEvent.click(apply());
  const dialog = screen.getByRole("dialog", { name: "Review building floors" });
  expect(await within(dialog).findByText(/Twelve tables cannot fit/)).toBeTruthy();
  expect(floors()[1]!.choice.dining_tables).toBe(12);
  fireEvent.click(within(dialog).getByRole("button", { name: "Edit floor 2" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull());
  expect(screen.getByRole("button", { name: "2F · Dining" }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "32" } });
  fireEvent.change(screen.getByLabelText("Depth (6–40 cells)"), { target: { value: "26" } });
  expect(floors()[0]!.choice.width).toBe(8);
  fireEvent.click(apply());
  expect(await screen.findByText("Floor previews ready: 2/2")).toBeTruthy();
  expect(floors().every((f) => f.choice.width === 32 && f.choice.height === 26)).toBe(true);
});

it.each([{ width: 7 }, { width: 41 }, { height: 5 }, { height: 41 }, { width: 12.5 }])("does not propagate invalid source dimensions %j", async (patch) => {
  await mount(patch);
  expect(apply().disabled).toBe(true); fireEvent.click(apply());
  expect(floors()[1]).toEqual(initial[1]);
  expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull();
});

it("shares partial dimensions with all six floors and keeps added floors independent until applied", async () => {
  await mount({ width: 40 });
  for (let count = 2; count < 6; count++) fireEvent.click(screen.getByRole("button", { name: "Add floor" }));
  fireEvent.click(screen.getByRole("button", { name: "1F · Shopping" }));
  fireEvent.click(apply());
  expect(await screen.findByText("Floor previews ready: 6/6")).toBeTruthy();
  expect(floors().every((f) => f.choice.width === 40 && f.choice.height === 24)).toBe(true);
});
