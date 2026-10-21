// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn(), validateLayoutPreset: vi.fn() }));

function Picker() {
  const [value, onChange] = useState(DEFAULT_TEMPLATE_CHOICE);
  return <TemplatePicker value={value} onChange={onChange} budgetCurrency="USD" />;
}

beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "urban_cvs", name: "City store", description: "Daily groceries", store_type: "convenience", grid: [12, 10], racks: 10, skus: 40, open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0,
      categories: [{ id: "soft_drinks", label: "Drinks" }, { id: "beer_alcohol", label: "Beer & Alcohol" }, { id: "household", label: "Household & Daily" }] },
    { id: "community_pharmacy", name: "Community pharmacy", description: "First aid and wellness", store_type: "pharmacy", grid: [14, 12], racks: 12, skus: 50, open_hours: [9, 21], default_style: "spine", default_design: "minimal", default_dining_tables: 0 },
    { id: "family_restaurant", name: "Family restaurant", description: "Central dining", store_type: "restaurant", grid: [24, 20], racks: 20, skus: 40, open_hours: [11, 22], default_style: "perimeter", default_design: "warm", default_dining_tables: 8, default_seating_zone: "center", default_checkout_placement: "near_entrance" },
    { id: "warehouse_club", name: "Warehouse club", description: "Bulk groceries", store_type: "supermarket", grid: [36, 28], racks: 60, skus: 80, open_hours: [9, 21], default_style: "spine", default_design: "classic", default_dining_tables: 0, default_checkouts: 8 },
    { id: "campus_dining_hall", name: "Campus dining hall", description: "Weekday dining", store_type: "restaurant", grid: [32, 24], racks: 40, skus: 80, open_hours: [7, 21], default_style: "perimeter", default_design: "minimal", default_dining_tables: 24, default_checkouts: 4 },
    { id: "garden_center", name: "Garden & outdoor center", description: "Plants and garden supplies", store_type: "garden", grid: [32, 26], racks: 60, skus: 40, open_hours: [8, 20], default_style: "cross", default_design: "botanical", default_dining_tables: 0, default_checkouts: 4 },
    { id: "specialty_cafe", name: "Specialty café", description: "Coffee and pastries", store_type: "cafe", grid: [18, 14], racks: 20, skus: 40, open_hours: [7, 22], default_style: "perimeter", default_design: "warm", default_dining_tables: 6 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Preview", type: "convenience", grid_size: [12, 10], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("sets operating hours, protects the last open day and restores only the schedule", async () => {
  mount();
  fireEvent.click(await screen.findByText("Operating hours · 7 open days"));
  fireEvent.change(screen.getByLabelText("Opening hour (0–23)"), { target: { value: "6" } });
  fireEvent.change(screen.getByLabelText("Closing hour (1–24)"), { target: { value: "15" } });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  for (const day of ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]) {
    fireEvent.click(screen.getByRole("checkbox", { name: day }));
  }
  expect((screen.getByRole("checkbox", { name: "Monday" }) as HTMLInputElement).disabled).toBe(true);
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ open_hour: 6, close_hour: 15, closed_days: [2, 3, 4, 5, 6, 7] }), expect.any(AbortSignal)));
  fireEvent.click(screen.getByRole("checkbox", { name: "Sunday" }));
  expect((screen.getByRole("checkbox", { name: "Monday" }) as HTMLInputElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Use format operating hours" }));
  expect((screen.getByLabelText("Opening hour (0–23)") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("24");
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ open_hour: null, close_hour: null, closed_days: null }), expect.any(AbortSignal)));
});

it("does not request a preview or export when explicit hours are reversed", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Operating hours · 7 open days"));
  fireEvent.change(screen.getByLabelText("Opening hour (0–23)"), { target: { value: "20" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ open_hour: 20 }), expect.any(AbortSignal)));
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Closing hour (1–24)"), { target: { value: "6" } });
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  expect((screen.getByRole("button", { name: "Export options" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Opening hour (0–23)") as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("Closing hour (1–24)") as HTMLInputElement).value).toBe("");
});

it("can use a wizard's hours without offering a conflicting second schedule editor", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><TemplatePicker value={{ ...DEFAULT_TEMPLATE_CHOICE, open_hour: 6, close_hour: 15, closed_days: [6, 7] }}
    onChange={vi.fn()} showOperatingHours={false} /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect(screen.queryByLabelText("Opening hour (0–23)")).toBeNull();
  expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ open_hour: 6, close_hour: 15, closed_days: [6, 7] }), expect.any(AbortSignal));
});

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Picker /></QueryClientProvider>);
}

it.each(["front", "back", "left", "right"] as const)("applies priorities on the %s entrance wall without losing unrelated requirements", async (gateWall) => {
  const starting = { ...DEFAULT_TEMPLATE_CHOICE, width: 24, height: 18, seed: 7, currency: "JPY", gate_wall: gateWall,
    design_theme: "coastal" as const, dining_tables: 3, checkouts: 4, checkout_wall: "back" as const,
    open_hour: 6, close_hour: 15, closed_days: [6, 7], products_per_category: 1, excluded_categories: ["beer_alcohol"],
    requirements: "Keep the consultation corner", reserved_areas: [{ label: "Consultation", x: 2, y: 2, width: 2, height: 3 }] };
  function PrioritizedPicker() {
    const [choice, setChoice] = useState<typeof DEFAULT_TEMPLATE_CHOICE>(starting);
    return <TemplatePicker value={choice} onChange={setChoice} />;
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PrioritizedPicker /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Apply a layout priority"));
  const unchanged = { width: 24, height: 18, seed: 7, currency: "JPY", gate_wall: gateWall, design_theme: "coastal",
    open_hour: 6, close_hour: 15, closed_days: [6, 7], products_per_category: 1, excluded_categories: ["beer_alcohol"], reserved_areas: starting.reserved_areas };
  for (const [id, expected] of [
    ["wide", { style: "cross", density: "spacious", aisle_width: 3, max_shelf_run: 3, table_clearance: 2, dining_tables: 3, checkouts: 4, checkout_wall: "back" }],
    ["capacity", { style: "aisles", density: "dense", aisle_width: 1, max_shelf_run: 8, table_clearance: 1, dining_tables: 3, checkouts: 4 }],
    ["open", { style: "perimeter", density: "balanced", dining_tables: 0, aisle_width: null, max_shelf_run: null, checkouts: 4 }],
    ["takeaway", { style: "perimeter", density: "balanced", dining_tables: 0, checkouts: 2, checkout_placement: "near_entrance", checkout_wall: gateWall }],
  ] as const) {
    const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
    fireEvent.change(screen.getByLabelText("Layout priority"), { target: { value: id } });
    expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
    fireEvent.click(screen.getByRole("button", { name: "Apply priority" }));
    await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ ...unchanged, ...expected }), expect.any(AbortSignal)));
    expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe(starting.requirements);
  }
});

it("lets users edit applied priority settings and reset the floor normally", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Apply a layout priority"));
  fireEvent.click(screen.getByRole("button", { name: "Apply priority" }));
  expect((screen.getByLabelText("Layout pattern") as HTMLSelectElement).value).toBe("cross");
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ style: "cross", aisle_width: 4 }), expect.any(AbortSignal)));
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Layout pattern") as HTMLSelectElement).value).toBe("");
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).value).toBe("");
});

it("applies the actual default palette or explicit design and currency without submitting the form", async () => {
  const design = vi.fn(), currency = vi.fn(), submit = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { rerender } = render(<QueryClientProvider client={client}><form onSubmit={submit}>
    <TemplatePicker value={DEFAULT_TEMPLATE_CHOICE} onChange={vi.fn()} onApplyDesignToAll={design} onApplyCurrencyToAll={currency} />
  </form></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByRole("button", { name: "Apply design to all floors" }));
  expect(design).toHaveBeenLastCalledWith("classic");
  const value = { ...DEFAULT_TEMPLATE_CHOICE, design_theme: "terracotta" as const, currency: "JPY" };
  rerender(<QueryClientProvider client={client}><form onSubmit={submit}>
    <TemplatePicker value={value} onChange={vi.fn()} onApplyDesignToAll={design} onApplyCurrencyToAll={currency} />
  </form></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Apply design to all floors" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply currency to all floors" }));
  expect(design).toHaveBeenLastCalledWith("terracotta");
  expect(currency).toHaveBeenLastCalledWith("JPY");
  expect(submit).not.toHaveBeenCalled();
  rerender(<QueryClientProvider client={client}><TemplatePicker value={value} onChange={vi.fn()}
    onApplyDesignToAll={design} onApplyCurrencyToAll={currency} sharedDesign="terracotta" sharedCurrency="JPY" /></QueryClientProvider>);
  expect((screen.getByRole("button", { name: "Design used on all floors" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Currency used on all floors" }) as HTMLButtonElement).disabled).toBe(true);
});

it("excludes chosen categories, keeps a stocked category and restores the assortment independently", async () => {
  mount();
  fireEvent.click(await screen.findByText("Product categories · 3 of 3 included"));
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "Keep local signs" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Beer & Alcohol" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Household & Daily" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ width: 24, excluded_categories: ["beer_alcohol", "household"] }), expect.any(AbortSignal),
  ));
  expect(screen.getByText("Product categories · 1 of 3 included")).toBeTruthy();
  expect((screen.getByRole("checkbox", { name: "Drinks" }) as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Restore all product categories" }));
  expect((screen.getByRole("checkbox", { name: "Drinks" }) as HTMLInputElement).disabled).toBe(false);
  expect((screen.getByRole("checkbox", { name: "Beer & Alcohol" }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("24");
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Keep local signs");
  fireEvent.click(screen.getByRole("checkbox", { name: "Beer & Alcohol" }));
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByRole("checkbox", { name: "Beer & Alcohol" }) as HTMLInputElement).checked).toBe(true);
});

it("places gates on other walls and keeps existing pickup areas when the wall changes", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  fireEvent.change(screen.getByLabelText("Depth (6–40 cells)"), { target: { value: "18" } });
  fireEvent.change(screen.getByLabelText("Entrance wall"), { target: { value: "left" } });
  expect(within(screen.getByLabelText("Entrance position")).getByRole("option", { name: "Near back" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Entrance position"), { target: { value: "center" } });
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "pickup" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  fireEvent.change(screen.getByLabelText("Entrance wall"), { target: { value: "back" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    gate_wall: "back", entrance: "center", reserved_areas: [
      { label: "Pickup", x: 2, y: 7, width: 2, height: 3 },
      { label: "Pickup 2", x: 10, y: 2, width: 3, height: 2 },
    ],
  }), expect.any(AbortSignal)));
  expect(within(screen.getByLabelText("Entrance position")).getByRole("option", { name: "Left" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Entrance wall") as HTMLSelectElement).value).toBe("front");
});

it("places the exit independently, labels its wall positions and restores shared-gate defaults", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect((screen.getByLabelText("Exit wall") as HTMLSelectElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Exit position"), { target: { value: "right" } });
  fireEvent.change(screen.getByLabelText("Exit wall"), { target: { value: "left" } });
  expect(within(screen.getByLabelText("Exit position")).getByRole("option", { name: "Near front" })).toBeTruthy();
  expect(within(screen.getByLabelText("Entrance position")).getByRole("option", { name: "Right" })).toBeTruthy();
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    gate_wall: "front", exit_position: "right", exit_wall: "left",
  }), expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText("Entrance wall"), { target: { value: "back" } });
  expect((screen.getByLabelText("Exit wall") as HTMLSelectElement).value).toBe("left");
  fireEvent.change(screen.getByLabelText("Exit position"), { target: { value: "shared" } });
  expect((screen.getByLabelText("Exit wall") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Exit wall") as HTMLSelectElement).value).toBe("");
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    gate_wall: "back", exit_position: "shared", exit_wall: null,
  }), expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText("Exit position"), { target: { value: "center" } });
  fireEvent.change(screen.getByLabelText("Exit wall"), { target: { value: "right" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Exit wall") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Exit wall") as HTMLSelectElement).value).toBe("");
});

it("limits products per category, validates whole counts and restores the full assortment", async () => {
  mount();
  fireEvent.click(await screen.findByText("Product categories · 3 of 3 included"));
  fireEvent.change(screen.getByLabelText("Products per category"), { target: { value: "4" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ products_per_category: 4 }), expect.any(AbortSignal),
  ));
  for (const invalid of ["0", "17", "1.5"]) {
    const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
    fireEvent.change(screen.getByLabelText("Products per category"), { target: { value: invalid } });
    expect(screen.queryByRole("button", { name: "Expand floor plan" })).toBeNull();
    expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  }
  fireEvent.change(screen.getByLabelText("Products per category"), { target: { value: "" } });
  await screen.findByRole("button", { name: "Expand floor plan" });
  expect((screen.getByLabelText("Products per category") as HTMLInputElement).value).toBe("");
  fireEvent.change(screen.getByLabelText("Products per category"), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Products per category") as HTMLInputElement).value).toBe("");
});

it("reveals the imported format even when previous catalog filters would hide it", async () => {
  mount();
  await screen.findByRole("button", { name: /Community pharmacy/ });
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "pharmacy" } });
  fireEvent.change(screen.getByLabelText("Store category"), { target: { value: "pharmacy" } });
  fireEvent.change(screen.getByLabelText("Default seating"), { target: { value: "without" } });
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "specialty_cafe", seed: 2, currency: "JPY", requirements: "Quiet seating" } });
  const file = Object.assign(new File(["{}"], "options.json"), { text: async () => "{}" });
  fireEvent.change(screen.getByLabelText("Import layout options file"), { target: { files: [file] } });
  const imported = await screen.findByRole("button", { name: /Specialty café/ });
  expect(imported.getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText("7 of 7 formats")).toBeTruthy();
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Quiet seating");
});

it("filters formats and sends selected requirements to the preview", async () => {
  mount();
  await screen.findByRole("button", { name: /Community pharmacy/ });
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "pharmacy" } });
  expect(screen.queryByRole("button", { name: /City store/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Community pharmacy/ }));
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "showroom" } });
  fireEvent.change(screen.getByLabelText("Interior shelf direction"), { target: { value: "vertical" } });
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Maximum shelf run"), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("Exit position"), { target: { value: "right" } });
  fireEvent.change(screen.getByLabelText("Checkout counters"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("Checkout placement"), { target: { value: "away_from_entrance" } });
  fireEvent.change(screen.getByLabelText("Checkout wall"), { target: { value: "back" } });
  fireEvent.change(screen.getByLabelText("Dining tables (4 seats each)"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Space around dining tables"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Seating starts near"), { target: { value: "right" } });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "28" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ template_id: "community_pharmacy", style: "showroom", checkouts: 3, width: 28, aisle_width: 4, max_shelf_run: 8,
      checkout_placement: "away_from_entrance", checkout_wall: "back", dining_tables: 4, table_clearance: 2, seating_zone: "right", shelf_direction: "vertical", exit_position: "right" }), expect.any(AbortSignal),
  ));
});

it("matches accents and unordered words without changing the selected layout", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "CAFE specialty" } });
  expect(screen.getByRole("button", { name: /Specialty café/ })).toBeTruthy();
  expect(screen.queryByRole("button", { name: /City store/ })).toBeNull();
  expect(screen.getByText("1 of 7 formats")).toBeTruthy();
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "café" } });
  expect(screen.getByRole("button", { name: /Specialty café/ })).toBeTruthy();
});

it("combines default floor size and seating filters and sorts the matching formats", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("More format filters"));
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "large" } });
  fireEvent.change(screen.getByLabelText("Default seating"), { target: { value: "with" } });
  const results = within(screen.getByLabelText("Store formats"));
  expect(results.getAllByRole("button")).toHaveLength(1);
  expect(results.getByRole("button", { name: /Campus dining hall/ })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "medium" } });
  fireEvent.change(screen.getByLabelText("Sort formats"), { target: { value: "seats" } });
  expect(results.getAllByRole("button").map((button) => button.textContent)).toEqual([
    expect.stringContaining("Family restaurant"), expect.stringContaining("Specialty café"),
  ]);
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "large" } });
  fireEvent.change(screen.getByLabelText("Default seating"), { target: { value: "without" } });
  fireEvent.change(screen.getByLabelText("Sort formats"), { target: { value: "largest" } });
  expect(results.getAllByRole("button").map((button) => button.textContent)).toEqual([
    expect.stringContaining("Warehouse club"), expect.stringContaining("Garden & outdoor center"),
  ]);
  fireEvent.change(screen.getByLabelText("Sort formats"), { target: { value: "smallest" } });
  expect(results.getAllByRole("button")[0]?.textContent).toContain("Garden & outdoor center");
});

it("clears an empty search without discarding the selected format, custom dimensions or brief", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /Community pharmacy/ }));
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "28" } });
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "Keep consultation space" } });
  fireEvent.change(screen.getByLabelText("Store category"), { target: { value: "pharmacy" } });
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "large" } });
  expect(screen.getByText(/No matching formats/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear format filters" }));
  expect(screen.getByRole("button", { name: /Community pharmacy/ }).getAttribute("aria-pressed")).toBe("true");
  expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("28");
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Keep consultation space");
  expect((screen.getByLabelText("Default floor size") as HTMLSelectElement).value).toBe("all");
  expect(screen.getByText("7 of 7 formats")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "compact" } });
  expect(screen.getByRole("button", { name: /City store/ })).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Community pharmacy/ })).toBeNull();
});

it("does not request an invalid size and resets options without losing the brief", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "99" } });
  expect(screen.getByRole("status").textContent).toContain("valid grid dimensions");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "Quiet corner" } });
  fireEvent.change(screen.getByLabelText("Checkout placement"), { target: { value: "near_entrance" } });
  fireEvent.change(screen.getByLabelText("Checkout wall"), { target: { value: "left" } });
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Maximum shelf run"), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Quiet corner");
  expect((screen.getByLabelText("Checkout placement") as HTMLSelectElement).value).toBe("auto");
  expect((screen.getByLabelText("Checkout wall") as HTMLSelectElement).value).toBe("front");
  expect((screen.getByLabelText("Seating starts near") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).value).toBe("1");
  expect((screen.getByLabelText("Interior shelf direction") as HTMLSelectElement).value).toBe("horizontal");
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).value).toBe("");
  expect((screen.getByLabelText("Maximum shelf run") as HTMLSelectElement).value).toBe("");
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
  expect((screen.getByLabelText("Maximum shelf run") as HTMLSelectElement).disabled).toBe(true);
  expect(screen.getByRole("option", { name: "Format default (center)" })).toBeTruthy();
  expect(screen.getByRole("option", { name: "Format default (near entrance)" })).toBeTruthy();
  expect((screen.getByLabelText("Seating starts near") as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Seating starts near"), { target: { value: "front" } });
  fireEvent.change(screen.getByLabelText("Checkout placement"), { target: { value: "away_from_entrance" } });
  fireEvent.click(screen.getByRole("button", { name: /Community pharmacy/ }));
  expect((screen.getByLabelText("Interior shelf direction") as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByLabelText("Maximum shelf run") as HTMLSelectElement).disabled).toBe(false);
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

it("sizes area starting points from the current dimensions rather than an old preview", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("Depth (6–40 cells)"), { target: { value: "6" } });
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "event" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    width: 8, height: 6, reserved_areas: [{ label: "Event space", x: 1, y: 1, width: 6, height: 4 }],
  }), expect.any(AbortSignal)));
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

it("keeps explicit spacing and run length when density changes and supports density defaults", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Maximum shelf run"), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("Display density"), { target: { value: "dense" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ density: "dense", aisle_width: 4, max_shelf_run: 8 }), expect.any(AbortSignal),
  ));
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).value).toBe("4");
  expect((screen.getByLabelText("Maximum shelf run") as HTMLSelectElement).value).toBe("8");
  expect(screen.getByRole("option", { name: "Density default (1 cell)" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText("Maximum shelf run"), { target: { value: "" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ density: "dense", aisle_width: null, max_shelf_run: null }), expect.any(AbortSignal),
  ));
});

it("explains cross-aisle seating capacity and lets other formats select the pattern", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /Garden & outdoor center/ }));
  expect(screen.getByRole("option", { name: "Format default (Central cross aisles)" })).toBeTruthy();
  expect(screen.getByText(/Central cross aisles stay clear of shelves and tables/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Community pharmacy/ }));
  expect(screen.queryByText(/Central cross aisles stay clear of shelves and tables/)).toBeNull();
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "cross" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ template_id: "community_pharmacy", style: "cross" }), expect.any(AbortSignal),
  ));
  expect(screen.getByText(/Central cross aisles stay clear of shelves and tables/)).toBeTruthy();
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
