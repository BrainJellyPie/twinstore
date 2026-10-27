// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/starterFill";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { formatMoney } from "@/shared/utils/money";
import { StarterFill } from "../StarterFill";
import { useSimulationStore } from "@/stores/simulationStore";
import { queryKeys } from "@/shared/queries/keys";
vi.mock("@/shared/api/starterFill", () => ({ getStarterCatalog: vi.fn(), previewStarterFill: vi.fn(), saveStarterFill: vi.fn(), autoSelectStarterProducts: vi.fn() }));
const product = { sku: "A", name: "Example water", price: 100, regular_price: 0, promo: "", image_url: null };
const catalog: api.StarterCatalog = { source_sha256: "a".repeat(64), currency: "USD", categories: [{ key: "water", label: "Water", products: [product] }], racks: [
  { id: "empty", name: "Empty shelf", type: "shelf", available_slots: 8, suggested_category: "water", reason: null },
  { id: "stocked", name: "Stocked shelf", type: "shelf", available_slots: 0, suggested_category: null, reason: "Already contains products; kept unchanged" },
] };
let qc: QueryClient;
beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.stubGlobal("crypto", webcrypto);
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getStarterCatalog).mockResolvedValue(catalog);
  vi.mocked(api.previewStarterFill).mockResolvedValue({ placements_added: 8, new_skus: 1, reused_skus: 0,
    racks: [{ id: "empty", name: "Empty shelf", category: "water", slots_added: 8, placements_added: 8, products: [product], reused_skus: [] }] });
  vi.mocked(api.saveStarterFill).mockResolvedValue({ setup_id: "setup_stocked", placements_added: 8 });
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); useSimulationStore.getState().reset(); });
async function open() {
  render(<QueryClientProvider client={qc}><StarterFill pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Auto-place starter products" }));
  fireEvent.click(await screen.findByLabelText("Choose categories manually"));
  await screen.findByLabelText(/^Select rack .* \(empty\)$/);
}

async function openAuto() {
  render(<QueryClientProvider client={qc}><StarterFill pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Auto-place starter products" }));
  await screen.findByLabelText("Automatic by store category (default)");
}
const automatic = { source_sha256: catalog.source_sha256, currency: "USD", products_per_slot: 2,
  assignments: [{ rack_id: "empty", category: "water", skus: ["A"] }] };

it("defaults to automatic selection, previews exact selected SKUs and saves only on request", async () => {
  vi.mocked(api.autoSelectStarterProducts).mockResolvedValue(automatic);
  await openAuto();
  expect((screen.getByLabelText("Automatic by store category (default)") as HTMLInputElement).checked).toBe(true);
  expect(api.autoSelectStarterProducts).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Assortment requirements"), { target: { value: "  Cafe drinks 🌿  " } });
  fireEvent.click(screen.getByRole("button", { name: "Choose and preview automatically" }));
  await screen.findByRole("button", { name: "Save stocked layout" });
  expect(api.autoSelectStarterProducts).toHaveBeenCalledWith("p", "s", { source_sha256: catalog.source_sha256, currency: "USD", products_per_slot: 2, requirements: "Cafe drinks 🌿" });
  expect(api.previewStarterFill).toHaveBeenCalledWith("p", "s", automatic);
  expect(api.saveStarterFill).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Save stocked layout" }));
  await screen.findByRole("button", { name: "Open stocked layout" });
  expect(vi.mocked(api.saveStarterFill).mock.lastCall?.[2]).toMatchObject(automatic);
});

it("waits for the new layout to be listed before offering to open it", async () => {
  let refreshed!: () => void;
  const refresh = new Promise<void>((resolve) => { refreshed = resolve; });
  const invalidate = vi.spyOn(qc, "invalidateQueries").mockReturnValueOnce(refresh);
  await open();
  await preview();
  fireEvent.click(screen.getByRole("button", { name: "Save stocked layout" }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.setups("p") }, { throwOnError: true }));
  expect(screen.queryByRole("button", { name: "Open stocked layout" })).toBeNull();
  expect(useSimulationStore.getState().selectedSetupId).toBeNull();
  await act(async () => { refreshed(); await refresh; });
  fireEvent.click(await screen.findByRole("button", { name: "Open stocked layout" }));
  expect(useSimulationStore.getState().selectedSetupId).toBe("setup_stocked");
});

it("retries the same saved draft if refreshing the layout list fails", async () => {
  vi.spyOn(qc, "invalidateQueries").mockRejectedValueOnce(new Error("Layout list unavailable"));
  await open();
  await preview();
  fireEvent.click(screen.getByRole("button", { name: "Save stocked layout" }));
  const retry = await screen.findByRole("button", { name: "Retry saving starter draft" });
  expect(screen.queryByRole("button", { name: "Open stocked layout" })).toBeNull();
  expect(useSimulationStore.getState().selectedSetupId).toBeNull();
  fireEvent.click(retry);
  await screen.findByRole("button", { name: "Open stocked layout" });
  expect(api.saveStarterFill).toHaveBeenCalledTimes(2);
  expect(vi.mocked(api.saveStarterFill).mock.calls[0]![2]).toEqual(vi.mocked(api.saveStarterFill).mock.calls[1]![2]);
});

it("keeps a failed model selection recoverable through manual selection", async () => {
  vi.mocked(api.autoSelectStarterProducts).mockRejectedValue(new Error("Connect a text model"));
  await openAuto();
  fireEvent.click(screen.getByRole("button", { name: "Choose and preview automatically" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Connect a text model");
  expect(api.previewStarterFill).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText("Choose categories manually"));
  await preview();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("discards the preview when automatic requirements, density or mode changes", async () => {
  vi.mocked(api.autoSelectStarterProducts).mockResolvedValue(automatic);
  await openAuto();
  for (const edit of [() => fireEvent.change(screen.getByLabelText("Assortment requirements"), { target: { value: "New assortment" } }),
    () => fireEvent.change(screen.getByLabelText("Products per shelf section"), { target: { value: "3" } }),
    () => fireEvent.click(screen.getByLabelText("Choose categories manually"))]) {
    fireEvent.click(screen.getByRole("button", { name: "Choose and preview automatically" }));
    await screen.findByRole("button", { name: "Save stocked layout" });
    edit();
    expect(screen.queryByRole("button", { name: "Save stocked layout" })).toBeNull();
  }
});

it.each([0, 101])("does not call a model for %i eligible shelves", async (count) => {
  vi.mocked(api.getStarterCatalog).mockResolvedValue({ ...catalog, racks: Array.from({ length: count }, (_, i) => ({ ...catalog.racks[0]!, id: String(i) })) });
  await openAuto();
  expect((screen.getByRole("button", { name: "Choose and preview automatically" }) as HTMLButtonElement).disabled).toBe(true);
  expect(api.autoSelectStarterProducts).not.toHaveBeenCalled();
});

it("locks edits during model selection and ignores a late selection after closing", async () => {
  let resolve!: (value: api.StarterRequest) => void;
  vi.mocked(api.autoSelectStarterProducts).mockReturnValue(new Promise((done) => { resolve = done; }));
  await openAuto();
  fireEvent.click(screen.getByRole("button", { name: "Choose and preview automatically" }));
  await screen.findByRole("button", { name: "Choosing catalog products…" });
  expect((screen.getByLabelText("Assortment requirements") as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  resolve(automatic);
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(api.previewStarterFill).not.toHaveBeenCalled();
  expect(api.saveStarterFill).not.toHaveBeenCalled();
});
it("selects empty racks, previews starter products, saves and explicitly opens a stocked child", async () => {
  await open();
  expect((screen.getByLabelText("Select rack Stocked shelf (stocked)") as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Select shown empty racks" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await screen.findByRole("button", { name: "Save stocked layout" });
  expect(api.previewStarterFill).toHaveBeenCalledWith("p", "s", { source_sha256: catalog.source_sha256, currency: "USD", assignments: [{ rack_id: "empty", category: "water" }], products_per_slot: 2 });
  fireEvent.click(screen.getByRole("button", { name: "Save stocked layout" }));
  fireEvent.click(await screen.findByRole("button", { name: "Open stocked layout" }));
  await waitFor(() => expect(useSimulationStore.getState().selectedSetupId).toBe("setup_stocked"));
});

async function preview() {
  fireEvent.click(screen.getByRole("button", { name: "Select shown empty racks" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await screen.findByRole("button", { name: "Save stocked layout" });
}
it("requires explicit categories when a rack has no known suggestion", async () => {
  vi.mocked(api.getStarterCatalog).mockResolvedValue({ ...catalog, racks: [{ ...catalog.racks[0]!, suggested_category: null }] });
  await open();
  fireEvent.click(screen.getByLabelText("Select rack Empty shelf (empty)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Choose a category");
  expect(api.previewStarterFill).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Category to apply"), { target: { value: "water" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply category to selected racks" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await screen.findByRole("button", { name: "Save stocked layout" });
});
it("invalidates preview after density or selection changes and retains hidden selections", async () => {
  await open(); await preview();
  fireEvent.change(screen.getByLabelText("Search shelves"), { target: { value: "Stocked" } });
  expect(screen.getByText(/Selected across all filters: 1\./)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Products per shelf section"), { target: { value: "4" } });
  expect(screen.queryByRole("button", { name: "Save stocked layout" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await screen.findByRole("button", { name: "Save stocked layout" });
  expect(vi.mocked(api.previewStarterFill).mock.lastCall?.[2].products_per_slot).toBe(4);
  fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
  expect(screen.queryByRole("button", { name: "Save stocked layout" })).toBeNull();
});
it("preserves choices during background refresh but resets on explicit successful reload", async () => {
  await open(); fireEvent.click(screen.getByLabelText("Select rack Empty shelf (empty)"));
  await qc.invalidateQueries({ queryKey: ["starter-fill", "p", "s"] });
  expect((screen.getByLabelText("Select rack Empty shelf (empty)") as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Discard choices and reload" }));
  await waitFor(() => expect((screen.getByLabelText("Select rack Empty shelf (empty)") as HTMLInputElement).checked).toBe(false));
});
it("shows failed reload and allows an explicit retry to update the catalog", async () => {
  await open();
  vi.mocked(api.getStarterCatalog).mockRejectedValueOnce(new Error("Offline"));
  fireEvent.click(screen.getByRole("button", { name: "Discard choices and reload" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Offline");
  vi.mocked(api.getStarterCatalog).mockResolvedValueOnce({ ...catalog, racks: [{ ...catalog.racks[0]!, name: "Updated rack" }] });
  fireEvent.click(screen.getByRole("button", { name: "Discard choices and retry" }));
  await screen.findByText(/Updated rack/);
});
it("locks choice changes during preview and replays the identical uncertain save", async () => {
  await open();
  let resolve!: (value: api.StarterPreview) => void;
  vi.mocked(api.previewStarterFill).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  fireEvent.click(screen.getByLabelText("Select rack Empty shelf (empty)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await waitFor(() => expect((screen.getByLabelText("Select rack Empty shelf (empty)") as HTMLInputElement).disabled).toBe(true));
  resolve({ racks: [{ id: "empty", name: "Empty shelf", category: "water", slots_added: 8, placements_added: 8, products: [product], reused_skus: [] }], placements_added: 8, new_skus: 1, reused_skus: 0 });
  await screen.findByRole("button", { name: "Save stocked layout" });
  vi.mocked(api.saveStarterFill).mockRejectedValueOnce(new Error("Lost response"));
  fireEvent.click(screen.getByRole("button", { name: "Save stocked layout" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry saving starter draft" }));
  await screen.findByRole("button", { name: "Open stocked layout" });
  expect(vi.mocked(api.saveStarterFill).mock.calls[0]![2]).toEqual(vi.mocked(api.saveStarterFill).mock.calls[1]![2]);
});
it("does not navigate when a save completes after closing", async () => {
  let resolve!: (value: api.StarterSaved) => void;
  vi.mocked(api.saveStarterFill).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  await open(); await preview();
  fireEvent.click(screen.getByRole("button", { name: "Save stocked layout" }));
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  resolve({ setup_id: "late", placements_added: 8 });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(useSimulationStore.getState().selectedSetupId).not.toBe("late");
});

it("rejects more than 100 selections accumulated across searches before an API call", async () => {
  vi.mocked(api.getStarterCatalog).mockResolvedValue({ ...catalog, racks: Array.from({ length: 101 }, (_, n) => ({ ...catalog.racks[0]!, id: n ? `rack_${n}` : "empty", name: `Shelf ${n}` })) });
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Select shown empty racks" }));
  fireEvent.change(screen.getByLabelText("Search shelves"), { target: { value: "rack_100" } });
  fireEvent.click(screen.getByLabelText("Select rack Shelf 100 (rack_100)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  expect((await screen.findByRole("alert")).textContent).toContain("1–100");
  expect(api.previewStarterFill).not.toHaveBeenCalled();
});

it("shows a stale-layout preview error without saving or discarding choices", async () => {
  await open();
  vi.mocked(api.previewStarterFill).mockRejectedValueOnce(new Error("The layout changed. Reload and preview again"));
  fireEvent.click(screen.getByLabelText("Select rack Empty shelf (empty)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  expect((await screen.findByRole("alert")).textContent).toContain("layout changed");
  expect((screen.getByLabelText("Select rack Empty shelf (empty)") as HTMLInputElement).checked).toBe(true);
  expect(screen.queryByRole("button", { name: "Save stocked layout" })).toBeNull();
  expect(api.saveStarterFill).not.toHaveBeenCalled();
});

it.each(LOCALES)("retains automatic selection and photos in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  const pictured = { ...product, name: "원본 상품 🌿", price: 123456, image_url: "/api/catalog-images/starter-17/0.webp" };
  vi.mocked(api.previewStarterFill).mockResolvedValue({ placements_added: 8, new_skus: 0, reused_skus: 1,
    racks: [{ id: "empty", name: "Empty shelf", category: "water", slots_added: 8, placements_added: 8, products: [pictured], reused_skus: ["A"] }] });
  vi.mocked(api.autoSelectStarterProducts).mockResolvedValue(automatic);
  render(<QueryClientProvider client={qc}><StarterFill pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: translate(code, "starterEntry") }));
  const auto = await screen.findByLabelText(translate(code, "starterAutoMode"));
  expect((auto as HTMLInputElement).checked).toBe(true);
  expect(api.autoSelectStarterProducts).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText(translate(code, "starterRequirements")), { target: { value: "유아용품, 반려동물 🌿" } });
  fireEvent.click(screen.getByRole("button", { name: translate(code, "starterAutoPreview") }));
  await screen.findByRole("button", { name: translate(code, "starterSave") });
  expect(vi.mocked(api.autoSelectStarterProducts).mock.lastCall?.[2].requirements).toBe("유아용품, 반려동물 🌿");
  expect(api.previewStarterFill).toHaveBeenCalledWith("p", "s", automatic);
  const image = screen.getByRole("img", { name: pictured.name, hidden: true });
  expect(image.getAttribute("src")).toContain(pictured.image_url);
  expect(screen.getByRole("region", { name: translate(code, "starterPreviewRegion") }).textContent).toContain(formatMoney(pictured.price, "USD", { locale: code }));
  expect(screen.getByText(translate(code, "starterAutoClosing"))).toBeTruthy();
});

it("keeps pending automatic choices, preview and retry identity across language changes", async () => {
  let resolve!: (value: api.StarterRequest) => void;
  vi.mocked(api.autoSelectStarterProducts).mockReturnValueOnce(new Promise(done => { resolve = done; }));
  await openAuto();
  fireEvent.change(screen.getByLabelText("Assortment requirements"), { target: { value: "Keep this choice" } });
  fireEvent.click(screen.getByRole("button", { name: "Choose and preview automatically" }));
  await screen.findByRole("button", { name: "Choosing catalog products…" });
  act(() => useLocale.getState().setLocale("ko"));
  expect((screen.getByLabelText(translate("ko", "starterRequirements")) as HTMLTextAreaElement).value).toBe("Keep this choice");
  resolve(automatic);
  await screen.findByRole("button", { name: translate("ko", "starterSave") });
  act(() => useLocale.getState().setLocale("fr"));
  vi.mocked(api.saveStarterFill).mockRejectedValueOnce(new Error("Connection lost"));
  fireEvent.click(screen.getByRole("button", { name: translate("fr", "starterSave") }));
  await screen.findByRole("button", { name: translate("fr", "starterRetrySave") });
  act(() => useLocale.getState().setLocale("es"));
  fireEvent.click(screen.getByRole("button", { name: translate("es", "starterRetrySave") }));
  await screen.findByRole("button", { name: translate("es", "starterOpen") });
  expect(api.autoSelectStarterProducts).toHaveBeenCalledTimes(1);
  expect(api.previewStarterFill).toHaveBeenCalledTimes(1);
  expect(vi.mocked(api.saveStarterFill).mock.calls[0]![2]).toEqual(vi.mocked(api.saveStarterFill).mock.calls[1]![2]);
});

it("updates manual validation text when the language changes without losing selections", async () => {
  vi.mocked(api.getStarterCatalog).mockResolvedValue({ ...catalog, racks: [{ ...catalog.racks[0]!, suggested_category: null }] });
  await open();
  fireEvent.click(screen.getByLabelText("Select rack Empty shelf (empty)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await screen.findByRole("alert");
  act(() => useLocale.getState().setLocale("ja"));
  expect(screen.getByRole("alert").textContent).toBe(translate("ja", "starterChooseCategoryEach"));
  expect((screen.getByLabelText(translate("ja", "starterSelectRack", { rack: "Empty shelf (empty)" })) as HTMLInputElement).checked).toBe(true);
  expect(api.previewStarterFill).not.toHaveBeenCalled();
});
