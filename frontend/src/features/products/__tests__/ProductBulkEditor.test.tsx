// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/productEdits";
import { ProductBulkEditor } from "../ProductBulkEditor";
import { useSimulationStore } from "@/stores/simulationStore";
vi.mock("@/shared/api/productEdits", () => ({ getProductCatalog: vi.fn(), previewProductEdits: vi.fn(), saveProductEdits: vi.fn() }));
const row: api.ProductRow = { sku: "A", names: ["Tea", "Tea large"], prices: [101, 202], promos: [""], placements: 2, racks: ["Drinks"] };
const catalog: api.ProductCatalog = { source_sha256: "a".repeat(64), currency: "USD", products: [row, { ...row, sku: "B", names: ["Water"], prices: [303], placements: 1 }] };
let qc: QueryClient;
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getProductCatalog).mockResolvedValue(catalog);
  vi.mocked(api.previewProductEdits).mockResolvedValue({ changed_placements: 2, changes: [{ before: row, after: { ...row, prices: [150] }, changed_placements: 2 }] });
  vi.mocked(api.saveProductEdits).mockResolvedValue({ setup_id: "setup_new", changed_placements: 2 });
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); useSimulationStore.getState().reset(); });
async function open() {
  const mounted = render(<QueryClientProvider client={qc}><ProductBulkEditor pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Edit products together" }));
  await screen.findByLabelText("Select A");
  return mounted;
}
it("edits selected placed SKUs, previews, saves a new layout and opens it explicitly", async () => {
  await open();
  fireEvent.click(screen.getByLabelText("Select A"));
  fireEvent.change(screen.getByLabelText("Selected product price"), { target: { value: "1.50" } });
  fireEvent.click(screen.getByRole("button", { name: "Set selected prices" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview product changes" }));
  await screen.findByRole("button", { name: "Save as new product draft" });
  expect(api.previewProductEdits).toHaveBeenCalledWith("p", "s", { source_sha256: catalog.source_sha256, currency: "USD", edits: [{ sku: "A", price: 150 }] });
  expect(api.saveProductEdits).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Save as new product draft" }));
  fireEvent.click(await screen.findByRole("button", { name: "Open edited layout" }));
  await waitFor(() => expect(useSimulationStore.getState().selectedSetupId).toBe("setup_new"));
});

it("retains local edits when the catalog is invalidated during editing", async () => {
  await open();
  fireEvent.change(screen.getByLabelText("Name for A"), { target: { value: "Keep my edit" } });
  let resolve!: (value: api.ProductCatalog) => void;
  vi.mocked(api.getProductCatalog).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const refreshing = qc.invalidateQueries({ queryKey: ["product-editor", "p", "s"] });
  try {
    await waitFor(() => expect(api.getProductCatalog).toHaveBeenCalledTimes(2));
    expect((screen.getByLabelText("Name for A") as HTMLInputElement).value).toBe("Keep my edit");
  } finally { resolve(catalog); await refreshing; }
  expect((await screen.findByLabelText("Name for A") as HTMLInputElement).value).toBe("Keep my edit");
});

it("shows a reload failure instead of silently returning an old catalog", async () => {
  await open();
  vi.mocked(api.getProductCatalog).mockRejectedValueOnce(new Error("Catalog unavailable"));
  fireEvent.click(screen.getByRole("button", { name: "Discard edits and reload products" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Catalog unavailable");
});

it("keeps hidden selections explicit and can undo a bulk edit", async () => {
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Select shown" }));
  fireEvent.change(screen.getByLabelText("Search products or racks"), { target: { value: "Water" } });
  expect(screen.getByText(/2 selected across all filters/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Selected product price"), { target: { value: "1.005" } });
  fireEvent.click(screen.getByRole("button", { name: "Set selected prices" }));
  expect((screen.getByLabelText("Price for B") as HTMLInputElement).value).toBe("1.005");
  fireEvent.click(screen.getByRole("button", { name: "Undo last edit" }));
  expect((screen.getByLabelText("Price for B") as HTMLInputElement).value).toBe("3.03");
  expect((screen.getByRole("button", { name: "Preview product changes" }) as HTMLButtonElement).disabled).toBe(true);
});

it("invalidates a preview when edited again and reuses an uncertain save request", async () => {
  await open();
  fireEvent.change(screen.getByLabelText("Price for A"), { target: { value: "2.50" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview product changes" }));
  await screen.findByRole("button", { name: "Save as new product draft" });
  fireEvent.change(screen.getByLabelText("Price for A"), { target: { value: "3.50" } });
  expect(screen.queryByRole("button", { name: "Save as new product draft" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Preview product changes" }));
  await screen.findByRole("button", { name: "Save as new product draft" });
  vi.mocked(api.saveProductEdits).mockRejectedValueOnce(new Error("Connection lost"));
  fireEvent.click(screen.getByRole("button", { name: "Save as new product draft" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry saving product draft" }));
  await screen.findByRole("button", { name: "Open edited layout" });
  expect(vi.mocked(api.saveProductEdits).mock.calls[0]![2]).toEqual(vi.mocked(api.saveProductEdits).mock.calls[1]![2]);
});

it("rejects invalid row prices before requesting a preview", async () => {
  await open();
  fireEvent.change(screen.getByLabelText("Price for A"), { target: { value: "-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview product changes" }));
  expect((await screen.findByRole("alert")).textContent).toContain("nonnegative");
  expect(api.previewProductEdits).not.toHaveBeenCalled();
});

it("does not switch layouts when a save completes after the dialog closes", async () => {
  let resolve!: (value: api.ProductEditsSaved) => void;
  vi.mocked(api.saveProductEdits).mockReturnValue(new Promise((done) => { resolve = done; }));
  await open();
  fireEvent.change(screen.getByLabelText("Price for A"), { target: { value: "1.50" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview product changes" }));
  fireEvent.click(await screen.findByRole("button", { name: "Save as new product draft" }));
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  resolve({ setup_id: "late", changed_placements: 2 });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(useSimulationStore.getState().selectedSetupId).not.toBe("late");
});

it("disables editing while an explicit discard-and-reload is pending", async () => {
  await open();
  let resolve!: (value: api.ProductCatalog) => void;
  vi.mocked(api.getProductCatalog).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  fireEvent.click(screen.getByRole("button", { name: "Discard edits and reload products" }));
  try {
    await waitFor(() => expect(api.getProductCatalog).toHaveBeenCalledTimes(2));
    expect((screen.getByLabelText("Name for A") as HTMLInputElement).disabled).toBe(true);
  } finally { resolve(catalog); }
});
