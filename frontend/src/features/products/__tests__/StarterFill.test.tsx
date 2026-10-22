// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/starterFill";
import { StarterFill } from "../StarterFill";
import { useSimulationStore } from "@/stores/simulationStore";
vi.mock("@/shared/api/starterFill", () => ({ getStarterCatalog: vi.fn(), previewStarterFill: vi.fn(), saveStarterFill: vi.fn() }));
const product = { sku: "A", name: "Example water", price: 100, regular_price: 0, promo: "", image_url: null };
const catalog: api.StarterCatalog = { source_sha256: "a".repeat(64), currency: "USD", categories: [{ key: "water", label: "Water", products: [product] }], racks: [
  { id: "empty", name: "Empty shelf", type: "shelf", available_slots: 8, suggested_category: "water", reason: null },
  { id: "stocked", name: "Stocked shelf", type: "shelf", available_slots: 0, suggested_category: null, reason: "Already contains products; kept unchanged" },
] };
let qc: QueryClient;
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getStarterCatalog).mockResolvedValue(catalog);
  vi.mocked(api.previewStarterFill).mockResolvedValue({ placements_added: 8, new_skus: 1, reused_skus: 0,
    racks: [{ id: "empty", name: "Empty shelf", category: "water", slots_added: 8, placements_added: 8, products: [product], reused_skus: [] }] });
  vi.mocked(api.saveStarterFill).mockResolvedValue({ setup_id: "setup_stocked", placements_added: 8 });
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); useSimulationStore.getState().reset(); });
async function open() {
  render(<QueryClientProvider client={qc}><StarterFill pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Fill empty shelves" }));
  await screen.findByLabelText("Select rack empty");
}
it("selects empty racks, previews starter products, saves and explicitly opens a stocked child", async () => {
  await open();
  expect((screen.getByLabelText("Select rack stocked") as HTMLInputElement).disabled).toBe(true);
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
  fireEvent.click(screen.getByLabelText("Select rack empty"));
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
  expect(screen.getByText(/1 selected across all filters/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Products per shelf section"), { target: { value: "4" } });
  expect(screen.queryByRole("button", { name: "Save stocked layout" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await screen.findByRole("button", { name: "Save stocked layout" });
  expect(vi.mocked(api.previewStarterFill).mock.lastCall?.[2].products_per_slot).toBe(4);
  fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
  expect(screen.queryByRole("button", { name: "Save stocked layout" })).toBeNull();
});
it("preserves choices during background refresh but resets on explicit successful reload", async () => {
  await open(); fireEvent.click(screen.getByLabelText("Select rack empty"));
  await qc.invalidateQueries({ queryKey: ["starter-fill", "p", "s"] });
  expect((screen.getByLabelText("Select rack empty") as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Discard choices and reload" }));
  await waitFor(() => expect((screen.getByLabelText("Select rack empty") as HTMLInputElement).checked).toBe(false));
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
  fireEvent.click(screen.getByLabelText("Select rack empty"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  await waitFor(() => expect((screen.getByLabelText("Select rack empty") as HTMLInputElement).disabled).toBe(true));
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
  fireEvent.click(screen.getByLabelText("Select rack rack_100"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  expect((await screen.findByRole("alert")).textContent).toContain("1–100");
  expect(api.previewStarterFill).not.toHaveBeenCalled();
});

it("shows a stale-layout preview error without saving or discarding choices", async () => {
  await open();
  vi.mocked(api.previewStarterFill).mockRejectedValueOnce(new Error("The layout changed. Reload and preview again"));
  fireEvent.click(screen.getByLabelText("Select rack empty"));
  fireEvent.click(screen.getByRole("button", { name: "Preview starter products" }));
  expect((await screen.findByRole("alert")).textContent).toContain("layout changed");
  expect((screen.getByLabelText("Select rack empty") as HTMLInputElement).checked).toBe(true);
  expect(screen.queryByRole("button", { name: "Save stocked layout" })).toBeNull();
  expect(api.saveStarterFill).not.toHaveBeenCalled();
});
