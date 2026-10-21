// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));

function Picker() {
  const [value, onChange] = useState(DEFAULT_TEMPLATE_CHOICE);
  return <TemplatePicker value={value} onChange={onChange} budgetCurrency="USD" />;
}

beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "urban_cvs", name: "City store", description: "Daily groceries", store_type: "convenience", grid: [12, 10], racks: 10, skus: 40, open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0 },
    { id: "community_pharmacy", name: "Community pharmacy", description: "First aid and wellness", store_type: "pharmacy", grid: [14, 12], racks: 12, skus: 50, open_hours: [9, 21], default_style: "spine", default_design: "minimal", default_dining_tables: 0 },
    { id: "family_restaurant", name: "Family restaurant", description: "Central dining", store_type: "restaurant", grid: [24, 20], racks: 20, skus: 40, open_hours: [11, 22], default_style: "perimeter", default_design: "warm", default_dining_tables: 8, default_seating_zone: "center", default_checkout_placement: "near_entrance" },
    { id: "warehouse_club", name: "Warehouse club", description: "Bulk groceries", store_type: "supermarket", grid: [36, 28], racks: 60, skus: 80, open_hours: [9, 21], default_style: "spine", default_design: "classic", default_dining_tables: 0, default_checkouts: 8 },
    { id: "campus_dining_hall", name: "Campus dining hall", description: "Weekday dining", store_type: "restaurant", grid: [32, 24], racks: 40, skus: 80, open_hours: [7, 21], default_style: "perimeter", default_design: "minimal", default_dining_tables: 24, default_checkouts: 4 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Preview", type: "convenience", grid_size: [12, 10], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Picker /></QueryClientProvider>);
}

it("filters formats and sends selected requirements to the preview", async () => {
  mount();
  await screen.findByRole("button", { name: /Community pharmacy/ });
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "pharmacy" } });
  expect(screen.queryByRole("button", { name: /City store/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Community pharmacy/ }));
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "showroom" } });
  fireEvent.change(screen.getByLabelText("Interior shelf direction"), { target: { value: "vertical" } });
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Exit position"), { target: { value: "right" } });
  fireEvent.change(screen.getByLabelText("Checkout counters"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("Checkout placement"), { target: { value: "away_from_entrance" } });
  fireEvent.change(screen.getByLabelText("Dining tables (4 seats each)"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Space around dining tables"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Seating starts near"), { target: { value: "right" } });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "28" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ template_id: "community_pharmacy", style: "showroom", checkouts: 3, width: 28, aisle_width: 4,
      checkout_placement: "away_from_entrance", dining_tables: 4, table_clearance: 2, seating_zone: "right", shelf_direction: "vertical", exit_position: "right" }), expect.any(AbortSignal),
  ));
});

it("does not request an invalid size and resets options without losing the brief", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "99" } });
  expect(screen.getByRole("status").textContent).toContain("valid grid size");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "Quiet corner" } });
  fireEvent.change(screen.getByLabelText("Checkout placement"), { target: { value: "near_entrance" } });
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Quiet corner");
  expect((screen.getByLabelText("Checkout placement") as HTMLSelectElement).value).toBe("auto");
  expect((screen.getByLabelText("Seating starts near") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).value).toBe("1");
  expect((screen.getByLabelText("Interior shelf direction") as HTMLSelectElement).value).toBe("horizontal");
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).value).toBe("");
  expect((screen.getByLabelText("Exit position") as HTMLSelectElement).value).toBe("shared");
  await screen.findByRole("img", { name: "Floor plan preview" });
});

it("shows preview errors instead of a stale successful plan", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  vi.mocked(api.previewStoreTemplate).mockRejectedValue(new Error("Preview failed"));
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "spine" } });
  await screen.findByRole("alert");
  expect(screen.queryByRole("img", { name: "Floor plan preview" })).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("Preview failed");
});

it("makes a different budget currency explicit while still allowing a price preview", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Price currency"), { target: { value: "JPY" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ currency: "JPY" }), expect.any(AbortSignal),
  ));
  expect(screen.getByText(/This project uses USD shopper budgets/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Price currency"), { target: { value: "USD" } });
  expect(screen.queryByText(/Existing budgets are not converted/)).toBeNull();
});

it("shows each format's seating and checkout defaults without replacing explicit user choices", async () => {
  mount();
  await screen.findByRole("button", { name: /Family restaurant/ });
  fireEvent.click(screen.getByRole("button", { name: /Family restaurant/ }));
  expect((screen.getByLabelText("Interior shelf direction") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).disabled).toBe(true);
  expect(screen.getByRole("option", { name: "Format default (center)" })).toBeTruthy();
  expect(screen.getByRole("option", { name: "Format default (near entrance)" })).toBeTruthy();
  expect((screen.getByLabelText("Seating starts near") as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Seating starts near"), { target: { value: "front" } });
  fireEvent.change(screen.getByLabelText("Checkout placement"), { target: { value: "away_from_entrance" } });
  fireEvent.click(screen.getByRole("button", { name: /Community pharmacy/ }));
  expect((screen.getByLabelText("Interior shelf direction") as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).disabled).toBe(false);
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    template_id: "community_pharmacy", seating_zone: "front", checkout_placement: "away_from_entrance",
  }), expect.any(AbortSignal)));
});

it("previews named clear areas, converts display coordinates and removes them on reset", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  fireEvent.change(screen.getByLabelText("Area 1 name"), { target: { value: "Consultation" } });
  fireEvent.change(screen.getByLabelText("Area 1 start column"), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText("Area 1 depth"), { target: { value: "4" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    reserved_areas: [{ label: "Consultation", x: 4, y: 2, width: 3, height: 4 }],
  }), expect.any(AbortSignal)));
  const marker = await screen.findByTestId("reserved-area-preview-0");
  expect(marker.getAttribute("x")).toBe("4");
  expect(marker.textContent).toBe("Consultation: kept clear");
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ reserved_areas: [] }), expect.any(AbortSignal)));
  expect(screen.queryByTestId("reserved-area-preview-0")).toBeNull();
});

it("holds preview for incomplete area values and supports removing a reservation", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  await screen.findByTestId("reserved-area-preview-0");
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Area 1 width"), { target: { value: "" } });
  expect(screen.getByRole("status").textContent).toContain("reserved-area values");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.click(screen.getByRole("button", { name: "Remove area 1" }));
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect(screen.queryByLabelText("Area 1 name")).toBeNull();
});

it("offers large checkout counts and resets to the selected format's default", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /Warehouse club/ }));
  expect((screen.getByLabelText("Checkout counters") as HTMLSelectElement).value).toBe("");
  expect(screen.getByRole("option", { name: "Format default (8, sized to fit)" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Checkout counters"), { target: { value: "12" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ checkouts: 12 }), expect.any(AbortSignal)));
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ checkouts: null }), expect.any(AbortSignal)));
});

it("keeps an explicit aisle gap when density changes and supports returning to density defaults", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Display density"), { target: { value: "dense" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ density: "dense", aisle_width: 4 }), expect.any(AbortSignal),
  ));
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).value).toBe("4");
  expect(screen.getByRole("option", { name: "Density default (1 cell)" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ density: "dense", aisle_width: null }), expect.any(AbortSignal),
  ));
});

it("accepts any whole dining count through 48, rejects invalid counts, and restores automatic seating when cleared", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /Campus dining hall/ }));
  const input = screen.getByLabelText("Dining tables (4 seats each)") as HTMLInputElement;
  expect(input.placeholder).toBe("Format default (24)");
  for (const count of [13, 48]) {
    fireEvent.change(input, { target: { value: String(count) } });
    await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ dining_tables: count }), expect.any(AbortSignal)));
  }
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  for (const value of ["49", "-1", "1.5"]) {
    fireEvent.change(input, { target: { value } });
    expect(screen.getByRole("status").textContent).toContain("table count");
    expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  }
  fireEvent.change(input, { target: { value: "" } });
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect(input.value).toBe("");
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).disabled).toBe(false);
});
