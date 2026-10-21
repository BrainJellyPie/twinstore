// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE } from "../templateOptions";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn(), validateLayoutPreset: vi.fn() }));

function Picker() {
  const [value, onChange] = useState(DEFAULT_TEMPLATE_CHOICE);
  return <TemplatePicker value={value} onChange={onChange} budgetCurrency="USD" />;
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
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
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

it.each(LOCALES)("finds translated store categories and clears search with focus in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); mountCompact();
  await screen.findByRole("radio", { name: /^Community pharmacy/ });
  const search = screen.getByLabelText(translate(code, "findStoreFormat"));
  expect((screen.getByRole("combobox", { name: translate(code, "storeCategory") }) as HTMLSelectElement).value).toBe("");
  fireEvent.change(search, { target: { value: translate(code, "pharmacy") } });
  const results = within(screen.getByLabelText(translate(code, "storeFormats")));
  expect(results.getAllByRole("radio")).toHaveLength(1);
  expect(results.getByRole("radio", { name: /^Community pharmacy/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "clearFormatSearch") }));
  expect(document.activeElement).toBe(search);
  expect(results.getAllByRole("radio")).toHaveLength(7);
});

it.each(["ＣＡＦＥ", "community_pharmacy", "COMMUNITY-PHARMACY", "  specialty  CAFE  "])("finds formats by normalized input %s", async (query) => {
  mountCompact(); await screen.findByRole("radio", { name: /^Community pharmacy/ });
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: query } });
  expect(within(screen.getByLabelText("Store formats")).getAllByRole("radio")).toHaveLength(1);
});

it("clears only the search on Escape and preserves filters, selection and dimensions", async () => {
  mountCompact(); fireEvent.click(await screen.findByRole("radio", { name: /^Community pharmacy/ }));
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  fireEvent.change(screen.getByLabelText("Store category"), { target: { value: "pharmacy" } });
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "medium" } });
  const search = screen.getByLabelText("Find a store format"); search.focus();
  fireEvent.change(search, { target: { value: "no-such-format" } });
  expect(screen.getByText(/No matching formats/)).toBeTruthy();
  fireEvent.keyDown(search, { key: "Escape" });
  expect(document.activeElement).toBe(search);
  expect((search as HTMLInputElement).value).toBe("");
  expect((screen.getByLabelText("Store category") as HTMLSelectElement).value).toBe("pharmacy");
  expect((screen.getByLabelText("Default floor size") as HTMLSelectElement).value).toBe("medium");
  expect(screen.getByRole("radio", { name: /^Community pharmacy/ }).getAttribute("aria-checked")).toBe("true");
  expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("24");
  fireEvent.click(screen.getByRole("button", { name: "Clear format filters" }));
  expect(document.activeElement).toBe(search);
  expect((screen.getByLabelText("Store category") as HTMLSelectElement).value).toBe("");
  expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("24");
});

it("keeps a translated search and raw category filter working after a language switch", async () => {
  useLocale.getState().setLocale("ko"); mountCompact(); await screen.findByRole("radio", { name: /^Community pharmacy/ });
  fireEvent.change(screen.getByLabelText(translate("ko", "findStoreFormat")), { target: { value: "약국" } });
  fireEvent.change(screen.getByLabelText(translate("ko", "storeCategory")), { target: { value: "pharmacy" } });
  act(() => useLocale.getState().setLocale("fr"));
  expect((screen.getByLabelText(translate("fr", "findStoreFormat")) as HTMLInputElement).value).toBe("약국");
  expect((screen.getByLabelText(translate("fr", "storeCategory")) as HTMLSelectElement).value).toBe("pharmacy");
  expect(within(screen.getByRole("radiogroup", { name: translate("fr", "storeFormats") })).getAllByRole("radio")).toHaveLength(1);
  expect(screen.getByRole("option", { name: translate("fr", "pharmacy") }).getAttribute("value")).toBe("pharmacy");
});

it.each(LOCALES)("searches less common translated categories in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); mountCompact(); await screen.findByRole("radio", { name: /^Garden/ });
  fireEvent.change(screen.getByLabelText(translate(code, "findStoreFormat")), { target: { value: translate(code, "gardenShop") } });
  const results = within(screen.getByRole("radiogroup", { name: translate(code, "storeFormats") }));
  expect(results.getAllByRole("radio")).toHaveLength(1);
  expect(results.getByRole("radio", { name: /^Garden/ })).toBeTruthy();
});

it.each(LOCALES)("retries a failed catalog without clearing the search in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); vi.mocked(api.getStoreTemplates).mockRejectedValueOnce(new Error("Catalog unavailable"));
  mountCompact(); await screen.findByText(translate(code, "loadFormatsError"), { exact: false });
  fireEvent.change(screen.getByLabelText(translate(code, "findStoreFormat")), { target: { value: translate(code, "pharmacy") } });
  fireEvent.click(screen.getByRole("button", { name: translate(code, "tryAgain") }));
  const results = within(screen.getByRole("radiogroup", { name: translate(code, "storeFormats") }));
  await waitFor(() => expect(results.getAllByRole("radio")).toHaveLength(1));
  expect(results.getByRole("radio", { name: /^Community pharmacy/ })).toBeTruthy();
  expect(api.getStoreTemplates).toHaveBeenCalledTimes(2);
});

it("distinguishes loading and an empty catalog from no search matches, then recovers", async () => {
  let resolve!: (formats: api.StoreTemplate[]) => void;
  vi.mocked(api.getStoreTemplates).mockReturnValueOnce(new Promise(done => { resolve = done; }));
  mountCompact(); expect(screen.getByText("Loading store formats…")).toBeTruthy();
  expect(screen.queryByText(/No matching formats/)).toBeNull();
  expect(screen.queryByText("Selected format:")).toBeNull();
  await act(async () => resolve([]));
  expect(await screen.findByText(translate("en", "emptyFormats"), { exact: false })).toBeTruthy();
  expect(screen.queryByText(/No matching formats/)).toBeNull();
  expect(screen.queryByText("Selected format:")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByRole("radio", { name: /^City store/ });
  expect(screen.getByText("7 of 7 formats")).toBeTruthy();
});

it("keeps checkout spacing across walls, priorities and count changes and resets it explicitly", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  for (const [wall, spacing] of [["front", "0"], ["back", "1"], ["left", "2"], ["right", "3"]]) {
    fireEvent.change(screen.getByLabelText("Checkout wall"), { target: { value: wall } });
    fireEvent.change(screen.getByLabelText("Space beside counters"), { target: { value: spacing } });
    await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ checkout_wall: wall, checkout_clearance: Number(spacing) }), expect.any(AbortSignal)));
  }
  fireEvent.change(screen.getByLabelText("Checkout counters"), { target: { value: "3" } });
  fireEvent.click(screen.getByText("Apply a layout priority"));
  fireEvent.change(screen.getByLabelText("Layout priority"), { target: { value: "wide" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply priority" }));
  expect((screen.getByLabelText("Space beside counters") as HTMLSelectElement).value).toBe("3");
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ checkout_clearance: 3, checkouts: 3, style: "cross" }), expect.any(AbortSignal)));
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Space beside counters") as HTMLSelectElement).value).toBe("0");
});

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

it("starts a mix from the seating that actually fits when the format count is automatic", async () => {
  const table = { id: "table1", type: "table" as const, shape: [[1, 1], [1, 1]], position: [2, 2] as [number, number], rotation: 0 as const,
    levels: 1, dwell_min: 0, dwell_max: 0, rack_name: "Table", rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [] };
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Small restaurant", type: "restaurant", grid_size: [8, 6], weekly_schedule: [], racks: [table] });
  mount();
  fireEvent.click(await screen.findByRole("radio", { name: /Family restaurant/ }));
  await screen.findByText("1 dining tables · 4 seats");
  fireEvent.click(screen.getByText("Mixed table sizes"));
  fireEvent.click(screen.getByRole("checkbox", { name: "Use mixed table sizes" }));
  expect((screen.getByLabelText("4-seat tables") as HTMLInputElement).value).toBe("1");
  expect((screen.getByLabelText("Dining tables (mixed sizes)") as HTMLInputElement).value).toBe("1");
});

it("edits mixed counts, guards the total, applies seating priorities and restores uniform tables", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Mixed table sizes"));
  fireEvent.click(screen.getByRole("checkbox", { name: "Use mixed table sizes" }));
  fireEvent.change(screen.getByLabelText("2-seat tables"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("4-seat tables"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("6-seat tables"), { target: { value: "1" } });
  const mix = { two_seat: 3, four_seat: 2, six_seat: 1 };
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ dining_tables: 6, table_mix: mix }), expect.any(AbortSignal)));
  expect((screen.getByLabelText("Dining tables (mixed sizes)") as HTMLInputElement).value).toBe("6");
  expect((screen.getByLabelText("Dining tables (mixed sizes)") as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText("Seats per table") as HTMLSelectElement).disabled).toBe(true);
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("6-seat tables"), { target: { value: "49" } });
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  expect((screen.getByRole("button", { name: "Export options" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("6-seat tables"), { target: { value: "1" } });
  fireEvent.click(screen.getByText("Apply a layout priority"));
  fireEvent.change(screen.getByLabelText("Layout priority"), { target: { value: "wide" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply priority" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ table_mix: mix, dining_tables: 6, table_clearance: 2 }), expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText("Layout priority"), { target: { value: "takeaway" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply priority" }));
  expect((screen.getByLabelText("2-seat tables") as HTMLInputElement).value).toBe("0");
  expect((screen.getByLabelText("4-seat tables") as HTMLInputElement).value).toBe("0");
  expect((screen.getByLabelText("6-seat tables") as HTMLInputElement).value).toBe("0");
  expect((screen.getByLabelText("Table rotation") as HTMLSelectElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("2-seat tables"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Use mixed table sizes" }));
  expect((screen.getByLabelText("Dining tables (4 seats each)") as HTMLInputElement).value).toBe("2");
  expect((screen.getByLabelText("Seats per table") as HTMLSelectElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByRole("checkbox", { name: "Use mixed table sizes" }) as HTMLInputElement).checked).toBe(false);
}, 15_000);

it("previews table sizes, retains the choice with zero tables and resets to four seats", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect((screen.getByLabelText("Seats per table") as HTMLSelectElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Dining tables (4 seats each)"), { target: { value: "2" } });
  for (const seats of [2, 6, 4]) {
    fireEvent.change(screen.getByLabelText("Seats per table"), { target: { value: String(seats) } });
    expect((screen.getByLabelText(`Dining tables (${seats} seats each)`) as HTMLInputElement).value).toBe("2");
    await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ dining_tables: 2, dining_seats: seats }), expect.any(AbortSignal)));
  }
  fireEvent.change(screen.getByLabelText("Seats per table"), { target: { value: "6" } });
  fireEvent.change(screen.getByLabelText("Dining tables (6 seats each)"), { target: { value: "0" } });
  expect((screen.getByLabelText("Seats per table") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Seats per table") as HTMLSelectElement).value).toBe("6");
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Seats per table") as HTMLSelectElement).value).toBe("4");
}, 15_000);

it("rotates dining footprints independently of shelves and retains the choice while seating is disabled", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect((screen.getByLabelText("Table rotation") as HTMLSelectElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Dining tables (4 seats each)"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Seats per table"), { target: { value: "6" } });
  fireEvent.change(screen.getByLabelText("Table rotation"), { target: { value: "90" } });
  expect(screen.getByText("2×3 cells, including chairs.")).toBeTruthy();
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ table_rotation: 90, dining_seats: 6, shelf_direction: "horizontal" }), expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText("Dining tables (6 seats each)"), { target: { value: "0" } });
  expect((screen.getByLabelText("Table rotation") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Table rotation") as HTMLSelectElement).value).toBe("90");
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Table rotation") as HTMLSelectElement).value).toBe("0");
});

it.each(["front", "back", "left", "right"] as const)("applies priorities on the %s entrance wall without losing unrelated requirements", async (gateWall) => {
  const starting = { ...DEFAULT_TEMPLATE_CHOICE, width: 24, height: 18, seed: 7, currency: "JPY", gate_wall: gateWall,
    design_theme: "coastal" as const, dining_tables: 3, table_rotation: 90 as const, checkouts: 4, checkout_wall: "back" as const,
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
    open_hour: 6, close_hour: 15, closed_days: [6, 7], products_per_category: 1, excluded_categories: ["beer_alcohol"], reserved_areas: starting.reserved_areas, table_rotation: 90 };
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
}, 15_000);

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

it.each(["front", "back", "left", "right"] as const)("switches dining and service priorities on the %s wall without mixing incompatible counts", async (gateWall) => {
  const changed = vi.fn();
  const starting = { ...DEFAULT_TEMPLATE_CHOICE, width: 32, height: 28, seed: 7, currency: "JPY", gate_wall: gateWall,
    design_theme: "nordic" as const, table_rotation: 90 as const, dining_tables: 5, dining_seats: 6 as const,
    table_mix: { two_seat: 1, four_seat: 1, six_seat: 3 }, open_hour: 6, close_hour: 20, closed_days: [7],
    requirements: "Keep a quiet seating corner", products_per_category: 2, excluded_categories: ["beer_alcohol"],
    reserved_areas: [{ label: "Pickup", x: 24, y: 20, width: 3, height: 2 }] };
  function PrioritizedPicker() {
    const [choice, setChoice] = useState<typeof DEFAULT_TEMPLATE_CHOICE>(starting);
    return <TemplatePicker value={choice} onChange={(next) => { changed(next); setChoice(next); }} />;
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PrioritizedPicker /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Apply a layout priority"));
  const unchanged = { width: 32, height: 28, seed: 7, currency: "JPY", gate_wall: gateWall, design_theme: "nordic", table_rotation: 90,
    open_hour: 6, close_hour: 20, closed_days: [7], products_per_category: 2, excluded_categories: ["beer_alcohol"], reserved_areas: starting.reserved_areas };
  for (const [id, expected] of [
    ["compact_cafe", { dining_tables: 4, dining_seats: 2, table_mix: null, table_clearance: 1, seating_zone: "back", checkouts: 1, checkout_clearance: 0 }],
    ["family_dining", { dining_tables: 6, dining_seats: 6, table_mix: null, table_clearance: 2, seating_zone: "center", checkouts: 2, checkout_clearance: 1 }],
    ["mixed_parties", { dining_tables: 6, dining_seats: 4, table_mix: { two_seat: 2, four_seat: 2, six_seat: 2 }, table_clearance: 1, checkouts: 2, checkout_clearance: 1 }],
    ["service_points", { style: "spine", density: "spacious", dining_tables: 0, table_mix: { two_seat: 0, four_seat: 0, six_seat: 0 }, checkouts: 3, checkout_clearance: 2, aisle_width: 3, max_shelf_run: 3 }],
    ["mixed_parties", { dining_tables: 6, table_mix: { two_seat: 2, four_seat: 2, six_seat: 2 } }],
    ["family_dining", { dining_tables: 6, dining_seats: 6, table_mix: null }],
  ] as const) {
    const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
    fireEvent.change(screen.getByLabelText("Layout priority"), { target: { value: id } });
    expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
    fireEvent.click(screen.getByRole("button", { name: "Apply priority" }));
    const applied = { ...unchanged, ...expected, checkout_wall: gateWall, checkout_placement: "near_entrance" };
    expect(changed).toHaveBeenLastCalledWith(expect.objectContaining(applied));
    // Returning to a previous priority can reuse its already-cached preview.
    await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenCalledWith(expect.objectContaining(applied), expect.any(AbortSignal)));
    expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe(starting.requirements);
  }
  fireEvent.change(screen.getByLabelText("Dining tables (6 seats each)"), { target: { value: "3" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ dining_tables: 3, dining_seats: 6 }), expect.any(AbortSignal)));
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Space beside counters") as HTMLSelectElement).value).toBe("0");
});

it("applies the actual default palette or explicit design and currency without submitting the form", async () => {
  const design = vi.fn(), currency = vi.fn(), submit = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { rerender } = render(<QueryClientProvider client={client}><form onSubmit={submit}>
    <TemplatePicker value={DEFAULT_TEMPLATE_CHOICE} onChange={vi.fn()} onApplyDesignToAll={design} onApplyCurrencyToAll={currency} />
  </form></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect(screen.getByText("Default design: Classic retail")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Apply design to all floors" }));
  expect(design).toHaveBeenLastCalledWith("classic", null);
  const value = { ...DEFAULT_TEMPLATE_CHOICE, design_theme: "terracotta" as const, currency: "JPY" };
  rerender(<QueryClientProvider client={client}><form onSubmit={submit}>
    <TemplatePicker value={value} onChange={vi.fn()} onApplyDesignToAll={design} onApplyCurrencyToAll={currency} />
  </form></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Apply design to all floors" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply currency to all floors" }));
  expect(design).toHaveBeenLastCalledWith("terracotta", null);
  expect(screen.queryByText(/^Default design:/)).toBeNull();
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

it("previews moved and swapped areas without losing floor requirements", async () => {
  mount(); await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  fireEvent.change(screen.getByLabelText("Depth (6–40 cells)"), { target: { value: "18" } });
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "Keep quiet consultation" } });
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "consultation" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  fireEvent.click(screen.getByRole("button", { name: "Move area 1 to back left" }));
  fireEvent.click(screen.getByRole("button", { name: "Swap area 1 width and depth" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    width: 24, height: 18, reserved_areas: [
      { label: "Consultation", x: 1, y: 1, width: 3, height: 4 },
      { label: "Consultation 2", x: 18, y: 2, width: 4, height: 3 },
    ],
  }), expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("Depth (6–40 cells)"), { target: { value: "6" } });
  // Resizing keeps coordinates until the user explicitly moves the second area.
  expect((screen.getByLabelText("Area 2 start column") as HTMLInputElement).value).toBe("19");
  fireEvent.click(screen.getByRole("button", { name: "Move area 2 to front right" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({
    width: 8, height: 6, reserved_areas: [
      { label: "Consultation", x: 1, y: 1, width: 3, height: 4 },
      { label: "Consultation 2", x: 3, y: 2, width: 4, height: 3 },
    ],
  }), expect.any(AbortSignal)));
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Keep quiet consultation");
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
  await screen.findByRole("radio", { name: /Community pharmacy/ });
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "pharmacy" } });
  fireEvent.change(screen.getByLabelText("Store category"), { target: { value: "pharmacy" } });
  fireEvent.change(screen.getByLabelText("Default seating"), { target: { value: "without" } });
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "specialty_cafe", seed: 2, currency: "JPY", requirements: "Quiet seating" } });
  const file = Object.assign(new File(["{}"], "options.json"), { text: async () => "{}" });
  fireEvent.change(screen.getByLabelText("Import layout options file"), { target: { files: [file] } });
  const imported = await screen.findByRole("radio", { name: /Specialty café/ });
  expect(imported.getAttribute("aria-checked")).toBe("true");
  expect(screen.getByText("7 of 7 formats")).toBeTruthy();
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Quiet seating");
});

it("filters formats and sends selected requirements to the preview", async () => {
  mount();
  await screen.findByRole("radio", { name: /Community pharmacy/ });
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "pharmacy" } });
  expect(screen.queryByRole("radio", { name: /City store/ })).toBeNull();
  fireEvent.click(screen.getByRole("radio", { name: /Community pharmacy/ }));
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
  expect(screen.getByRole("radio", { name: /Specialty café/ })).toBeTruthy();
  expect(screen.queryByRole("radio", { name: /City store/ })).toBeNull();
  expect(screen.getByText("1 of 7 formats")).toBeTruthy();
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "café" } });
  expect(screen.getByRole("radio", { name: /Specialty café/ })).toBeTruthy();
});

it("combines default floor size and seating filters and sorts the matching formats", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("More format filters"));
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "large" } });
  fireEvent.change(screen.getByLabelText("Default seating"), { target: { value: "with" } });
  const results = within(screen.getByLabelText("Store formats"));
  expect(results.getAllByRole("radio")).toHaveLength(1);
  expect(results.getByRole("radio", { name: /Campus dining hall/ })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "medium" } });
  fireEvent.change(screen.getByLabelText("Sort formats"), { target: { value: "seats" } });
  expect(results.getAllByRole("radio").map((button) => button.textContent)).toEqual([
    expect.stringContaining("Family restaurant"), expect.stringContaining("Specialty café"),
  ]);
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "large" } });
  fireEvent.change(screen.getByLabelText("Default seating"), { target: { value: "without" } });
  fireEvent.change(screen.getByLabelText("Sort formats"), { target: { value: "largest" } });
  expect(results.getAllByRole("radio").map((button) => button.textContent)).toEqual([
    expect.stringContaining("Warehouse club"), expect.stringContaining("Garden & outdoor center"),
  ]);
  fireEvent.change(screen.getByLabelText("Sort formats"), { target: { value: "smallest" } });
  expect(results.getAllByRole("radio")[0]?.textContent).toContain("Garden & outdoor center");
});

it("clears an empty search without discarding the selected format, custom dimensions or brief", async () => {
  mount();
  fireEvent.click(await screen.findByRole("radio", { name: /Community pharmacy/ }));
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "28" } });
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "Keep consultation space" } });
  fireEvent.change(screen.getByLabelText("Store category"), { target: { value: "pharmacy" } });
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "large" } });
  expect(screen.getByText(/No matching formats/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear format filters" }));
  expect(screen.getByRole("radio", { name: /Community pharmacy/ }).getAttribute("aria-checked")).toBe("true");
  expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("28");
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Keep consultation space");
  expect((screen.getByLabelText("Default floor size") as HTMLSelectElement).value).toBe("all");
  expect(screen.getByText("7 of 7 formats")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Default floor size"), { target: { value: "compact" } });
  expect(screen.getByRole("radio", { name: /City store/ })).toBeTruthy();
  expect(screen.queryByRole("radio", { name: /Community pharmacy/ })).toBeNull();
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
  await screen.findByRole("radio", { name: /Family restaurant/ });
  fireEvent.click(screen.getByRole("radio", { name: /Family restaurant/ }));
  expect((screen.getByLabelText("Interior shelf direction") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText("Maximum shelf run") as HTMLSelectElement).disabled).toBe(true);
  expect(screen.getByRole("option", { name: "Format default (center)" })).toBeTruthy();
  expect(screen.getByRole("option", { name: "Format default (near entrance)" })).toBeTruthy();
  expect((screen.getByLabelText("Seating starts near") as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByLabelText("Space around dining tables") as HTMLSelectElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Seating starts near"), { target: { value: "front" } });
  fireEvent.change(screen.getByLabelText("Checkout placement"), { target: { value: "away_from_entrance" } });
  fireEvent.click(screen.getByRole("radio", { name: /Community pharmacy/ }));
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
  fireEvent.click(await screen.findByRole("radio", { name: /Warehouse club/ }));
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

it("previews a central plaza while retaining dimensions and table rotation and allowing surrounding aisle settings", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "32" } });
  fireEvent.change(screen.getByLabelText("Dining tables (4 seats each)"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("Table rotation"), { target: { value: "90" } });
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "plaza" } });
  expect(screen.getByText(/The central plaza stays clear of shelves and tables/)).toBeTruthy();
  expect((screen.getByLabelText("Interior aisle gap") as HTMLSelectElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Interior aisle gap"), { target: { value: "4" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ style: "plaza", width: 32, dining_tables: 3, table_rotation: 90, aisle_width: 4 }), expect.any(AbortSignal)));
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Layout pattern") as HTMLSelectElement).value).toBe("");
  expect(screen.queryByText(/The central plaza stays clear/)).toBeNull();
});

it("explains cross-aisle seating capacity and lets other formats select the pattern", async () => {
  mount();
  fireEvent.click(await screen.findByRole("radio", { name: /Garden & outdoor center/ }));
  expect(within(screen.getByLabelText("Layout pattern")).getByRole("option", { name: "Format default" })).toBeTruthy();
  expect(screen.getByText("Default pattern: Central cross aisles")).toBeTruthy();
  expect(screen.getByText(/Central cross aisles stay clear of shelves and tables/)).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: /Community pharmacy/ }));
  expect(screen.getByText("Default pattern: Central spine")).toBeTruthy();
  expect(screen.queryByText(/Central cross aisles stay clear of shelves and tables/)).toBeNull();
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "cross" } });
  expect(screen.queryByText(/^Default pattern:/)).toBeNull();
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ template_id: "community_pharmacy", style: "cross" }), expect.any(AbortSignal),
  ));
  expect(screen.getByText(/Central cross aisles stay clear of shelves and tables/)).toBeTruthy();
});

it("accepts any whole dining count through 48, rejects invalid counts, and restores automatic seating when cleared", async () => {
  mount();
  fireEvent.click(await screen.findByRole("radio", { name: /Campus dining hall/ }));
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

function CompactPicker() {
  const [value, onChange] = useState(DEFAULT_TEMPLATE_CHOICE);
  return <TemplatePicker value={value} onChange={onChange} budgetCurrency="USD" defaultCustomizationOpen={false} showOperatingHours={false} />;
}
function mountCompact() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><CompactPicker /></QueryClientProvider>);
}

it("keeps the live plan, size and currency available while customization starts folded", async () => {
  mountCompact(); await screen.findByRole("img", { name: "Floor plan preview" });
  const button = screen.getByRole("button", { name: "Customize layout" });
  expect(button.getAttribute("aria-expanded")).toBe("false");
  for (const id of button.getAttribute("aria-controls")!.split(" ")) expect(document.getElementById(id)?.hidden).toBe(true);
  expect(screen.getByRole("spinbutton", { name: "Width (8–40 cells)" })).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "Price currency" })).toBeTruthy();
  expect(screen.queryByRole("combobox", { name: "Display density" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Add reserved area" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Import options" })).toBeNull();
});

it("preserves edits and avoids new preview requests when customization is folded", async () => {
  mountCompact(); await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  fireEvent.click(screen.getByRole("button", { name: "Customize layout" }));
  fireEvent.change(screen.getByLabelText("Display density"), { target: { value: "dense" } });
  fireEvent.change(screen.getByLabelText("Entrance position"), { target: { value: "right" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ width: 24, density: "dense", entrance: "right", reserved_areas: [expect.any(Object)] }), expect.any(AbortSignal)));
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.click(screen.getByRole("button", { name: "Hide layout settings" }));
  expect(screen.queryByRole("button", { name: "Remove area 1" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Customize layout" }));
  expect((screen.getByLabelText("Display density") as HTMLSelectElement).value).toBe("dense");
  expect((screen.getByLabelText("Entrance position") as HTMLSelectElement).value).toBe("right");
  expect(screen.getByRole("button", { name: "Remove area 1" })).toBeTruthy();
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
});

it.each(["-1", "49", "1.5"])("explains an invalid hidden table count (%s) and recovers after correction", async (count) => {
  mountCompact(); await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByRole("button", { name: "Customize layout" }));
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Dining tables (4 seats each)"), { target: { value: count } });
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.click(screen.getByRole("button", { name: "Hide layout settings" }));
  expect(screen.getByRole("alert").textContent).toBe("Check the size and layout settings before continuing.");
  fireEvent.click(screen.getByRole("button", { name: "Customize layout" }));
  expect((screen.getByLabelText("Dining tables (4 seats each)") as HTMLInputElement).value).toBe(count);
  fireEvent.change(screen.getByLabelText("Dining tables (4 seats each)"), { target: { value: "0" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ dining_tables: 0 }), expect.any(AbortSignal)));
});

it("keeps a currency mismatch visible outside the folded customization", async () => {
  mountCompact(); await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByRole("combobox", { name: "Price currency" }), { target: { value: "JPY" } });
  const warning = await screen.findByText(/This project uses USD shopper budgets/);
  expect(warning.closest("[hidden]")).toBeNull();
  expect(screen.getByRole("button", { name: "Customize layout" }).getAttribute("aria-expanded")).toBe("false");
});

it("retains custom size when selecting another format from the simple view", async () => {
  mountCompact(); await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  fireEvent.click(screen.getByRole("radio", { name: /^Community pharmacy/ }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ template_id: "community_pharmacy", width: 24 }), expect.any(AbortSignal)));
  expect(screen.getByRole("button", { name: "Customize layout" }).getAttribute("aria-expanded")).toBe("false");
});
