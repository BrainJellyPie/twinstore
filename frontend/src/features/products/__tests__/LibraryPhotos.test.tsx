// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/libraryPhotos";
import { LibraryPhotos } from "../LibraryPhotos";
import { useSimulationStore } from "@/stores/simulationStore";
vi.mock("@/shared/api/libraryPhotos", () => ({ getLibraryPhotos: vi.fn(), previewLibraryPhotos: vi.fn(), saveLibraryPhotos: vi.fn() }));
const asset = { asset_id: "pkg_1", name: "Tea photo", sku: "茶", version: "b".repeat(64), image_url: "/photo.png" };
const product = { sku: "茶", names: ["Tea"], image_urls: [], placements: 2 };
const options: api.PhotoOptions = { source_sha256: "a".repeat(64), assets: [asset], products: [product] };
const report: api.PhotoPreview = { changed_placements: 2, changes: [{ ...product, asset_name: asset.name, image_url: "/snapshot" }] };
let qc: QueryClient;
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getLibraryPhotos).mockResolvedValue(options);
  vi.mocked(api.previewLibraryPhotos).mockResolvedValue(report);
  vi.mocked(api.saveLibraryPhotos).mockResolvedValue({ setup_id: "setup_photos", changed_placements: 2 });
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); useSimulationStore.getState().reset(); });
const view = (sid = "s") => <QueryClientProvider client={qc}><LibraryPhotos pid="p" sid={sid} /></QueryClientProvider>;
async function open() {
  const rendered = render(view()); fireEvent.click(screen.getByRole("button", { name: "Use library photos" }));
  await screen.findByRole("combobox", { name: "Photo for 茶" }); return rendered;
}
async function preview() {
  fireEvent.click(screen.getByRole("button", { name: "Use unique links for shown products" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview product photos" }));
  await screen.findByRole("button", { name: "Save layout with photos" });
}
it("reviews unique links, previews immutable photos, saves and opens a separate layout", async () => {
  await open(); await preview();
  expect(api.previewLibraryPhotos).toHaveBeenCalledWith("p", "s", { source_sha256: options.source_sha256, assignments: [{ sku: "茶", asset_id: asset.asset_id, version: asset.version }], replace_existing: false });
  expect((screen.getByAltText("Saved photo for 茶") as HTMLImageElement).src).toContain("/snapshot");
  fireEvent.click(screen.getByRole("button", { name: "Save layout with photos" }));
  fireEvent.click(await screen.findByRole("button", { name: "Open photo layout" }));
  expect(useSimulationStore.getState().selectedSetupId).toBe("setup_photos");
});
it("leaves ambiguous links for manual choice", async () => {
  vi.mocked(api.getLibraryPhotos).mockResolvedValue({ ...options, assets: [asset, { ...asset, asset_id: "pkg_2" }] });
  await open(); fireEvent.click(screen.getByRole("button", { name: "Use unique links for shown products" }));
  expect((screen.getByRole("combobox", { name: "Photo for 茶" }) as HTMLSelectElement).value).toBe("");
  expect(screen.getByText(/Multiple photos link/)).toBeTruthy();
  fireEvent.change(screen.getByRole("combobox", { name: "Photo for 茶" }), { target: { value: "pkg_2" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview product photos" }));
  await screen.findByRole("button", { name: "Save layout with photos" });
  expect(vi.mocked(api.previewLibraryPhotos).mock.lastCall?.[2].assignments[0]?.asset_id).toBe("pkg_2");
});
it("requires opt-in to replace an existing photo and resets choices on changing the mode", async () => {
  vi.mocked(api.getLibraryPhotos).mockResolvedValue({ ...options, products: [{ ...product, image_urls: ["/old"] }] });
  await open(); expect(screen.getByRole("combobox", { name: "Photo for 茶" }).matches(":disabled")).toBe(true);
  fireEvent.click(screen.getByRole("checkbox")); await preview();
  expect(vi.mocked(api.previewLibraryPhotos).mock.lastCall?.[2].replace_existing).toBe(true);
  fireEvent.click(screen.getByRole("checkbox")); expect(screen.queryByRole("button", { name: "Save layout with photos" })).toBeNull();
});

// Separate boundary phase after the basic workflow.
it.each(["__proto__", "constructor", "toString"])("treats %s as an ordinary SKU", async sku => {
  vi.mocked(api.getLibraryPhotos).mockResolvedValue({ ...options, products: [{ ...product, sku }], assets: [{ ...asset, sku }] });
  render(view()); fireEvent.click(screen.getByRole("button", { name: "Use library photos" }));
  await screen.findByRole("combobox", { name: `Photo for ${sku}` });
  fireEvent.click(screen.getByRole("button", { name: "Use unique links for shown products" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview product photos" }));
  await waitFor(() => expect(api.previewLibraryPhotos).toHaveBeenCalled());
  expect(vi.mocked(api.previewLibraryPhotos).mock.lastCall?.[2].assignments[0]?.sku).toBe(sku);
});
it("keeps the same request identity after a lost save response", async () => {
  await open(); await preview();
  vi.mocked(api.saveLibraryPhotos).mockRejectedValueOnce(new Error("Lost response"));
  fireEvent.click(screen.getByRole("button", { name: "Save layout with photos" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry saving photo layout" }));
  await screen.findByRole("button", { name: "Open photo layout" });
  expect(vi.mocked(api.saveLibraryPhotos).mock.calls[0]![2]).toEqual(vi.mocked(api.saveLibraryPhotos).mock.calls[1]![2]);
});
it("locks controls while preview runs and retains corrections after failure", async () => {
  await open(); let fail!: (reason: Error) => void;
  vi.mocked(api.previewLibraryPhotos).mockReturnValueOnce(new Promise((_r, reject) => { fail = reject; }));
  fireEvent.click(screen.getByRole("button", { name: "Use unique links for shown products" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview product photos" }));
  await waitFor(() => expect(screen.getByRole("checkbox").matches(":disabled")).toBe(true));
  fail(new Error("Photo changed"));
  expect((await screen.findByRole("alert")).textContent).toContain("Photo changed");
  expect((screen.getByRole("combobox", { name: "Photo for 茶" }) as HTMLSelectElement).value).toBe("pkg_1");
});
it.each(["source", "asset"])("invalidates a preview after a refreshed %s revision", async kind => {
  await open(); await preview();
  vi.mocked(api.getLibraryPhotos).mockResolvedValue({ ...options, ...(kind === "source" ? { source_sha256: "c".repeat(64) } : { assets: [{ ...asset, version: "c".repeat(64) }] }) });
  await qc.invalidateQueries({ queryKey: ["library-photos", "p", "s"] });
  await waitFor(() => expect(screen.queryByRole("button", { name: "Save layout with photos" })).toBeNull());
});
it.each(["close", "layout"])("does not open a late save after %s", async kind => {
  const rendered = await open(); await preview();
  let finish!: (value: api.PhotoSaved) => void;
  vi.mocked(api.saveLibraryPhotos).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  fireEvent.click(screen.getByRole("button", { name: "Save layout with photos" }));
  await waitFor(() => expect(api.saveLibraryPhotos).toHaveBeenCalledTimes(1));
  if (kind === "close") {
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByRole("button", { name: "Use library photos" }));
  } else rendered.rerender(view("other"));
  finish({ setup_id: "late", changed_placements: 2 });
  await screen.findByRole("combobox", { name: "Photo for 茶" });
  expect(screen.queryByRole("button", { name: "Open photo layout" })).toBeNull();
  expect(useSimulationStore.getState().selectedSetupId).not.toBe("late");
});
it("retains filtered choices and blocks batches larger than 100 before the API", async () => {
  vi.mocked(api.getLibraryPhotos).mockResolvedValue({ ...options, products: Array.from({ length: 101 }, (_, i) => ({ ...product, sku: `sku${i}` })), assets: Array.from({ length: 101 }, (_, i) => ({ ...asset, asset_id: `pkg_${i}`, sku: `sku${i}` })) });
  render(view()); fireEvent.click(screen.getByRole("button", { name: "Use library photos" }));
  await screen.findByRole("combobox", { name: "Photo for sku0" });
  fireEvent.click(screen.getByRole("button", { name: "Use unique links for shown products" }));
  fireEvent.change(screen.getByLabelText("Search shelf products"), { target: { value: "sku100" } });
  fireEvent.click(screen.getByRole("button", { name: "Use unique links for shown products" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview product photos" }));
  expect((await screen.findByRole("alert")).textContent).toContain("at most 100");
  expect(api.previewLibraryPhotos).not.toHaveBeenCalled();
}, 15000);
it("shows empty-state actions and retries an API load error", async () => {
  vi.mocked(api.getLibraryPhotos).mockRejectedValueOnce(new Error("Offline"));
  render(view()); fireEvent.click(screen.getByRole("button", { name: "Use library photos" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Offline");
  vi.mocked(api.getLibraryPhotos).mockResolvedValue({ ...options, assets: [], products: [] });
  fireEvent.click(screen.getByRole("button", { name: "Reload products and photos" }));
  await screen.findByText(/No library photos yet/); expect(screen.getByText(/Place products first/)).toBeTruthy();
});
it("searches photos without losing a selected image outside the filter", async () => {
  vi.mocked(api.getLibraryPhotos).mockResolvedValue({ ...options, assets: [asset, { ...asset, asset_id: "pkg_other", sku: "", name: "Coffee" }] });
  await open(); await preview();
  fireEvent.change(screen.getByLabelText("Search library photos"), { target: { value: "Coffee" } });
  expect((screen.getByRole("combobox", { name: "Photo for 茶" }) as HTMLSelectElement).value).toBe("pkg_1");
  expect(screen.getByRole("option", { name: /Coffee/ })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Save layout with photos" })).toBeTruthy();
  fireEvent.change(screen.getByRole("combobox", { name: "Photo for 茶" }), { target: { value: "pkg_other" } });
  expect(screen.queryByRole("button", { name: "Save layout with photos" })).toBeNull();
});
