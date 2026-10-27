// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/rackCopy";
import { RackCopy } from "../RackCopy";
import { useSimulationStore } from "@/stores/simulationStore";
vi.mock("@/shared/api/rackCopy", () => ({ getRackCopyOptions: vi.fn(), previewRackCopy: vi.fn(), saveRackCopy: vi.fn() }));
const product = { sku: "茶", name: "Tea", price: 231, regular_price: 299, promo: "Local", image_url: "/tea.png" };
const source = { id: "stocked", name: "Stocked shelf", type: "shelf", placements: 1, reason: null };
const empty = { ...source, id: "empty", name: "Empty shelf" };
const options: api.RackCopyOptions = { source_sha256: "a".repeat(64), currency: "USD", source_rack_id: null, sources: [source], targets: [] };
const report: api.RackCopyPreview = { source_name: source.name, slots: [{ block: 0, face: "S", level: 4, items: [product] }], targets: [empty], placements_added: 1 };
let qc: QueryClient;
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getRackCopyOptions).mockImplementation(async (_p, _s, id) => ({ ...options, source_rack_id: id || null, targets: id ? [empty, { ...source, reason: "This is the source rack" }] : [] }));
  vi.mocked(api.previewRackCopy).mockResolvedValue(report);
  vi.mocked(api.saveRackCopy).mockResolvedValue({ setup_id: "setup_copied", placements_added: 1 });
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); useSimulationStore.getState().reset(); });
const view = (sid = "s", pid = "p") => <QueryClientProvider client={qc}><RackCopy pid={pid} sid={sid} /></QueryClientProvider>;
async function open() {
  const rendered = render(view());
  fireEvent.click(screen.getByRole("button", { name: "Reuse shelf products" }));
  await screen.findByRole("option", { name: /Stocked shelf/ });
  fireEvent.change(screen.getByLabelText("Copy products from"), { target: { value: "stocked" } });
  await screen.findByLabelText(/^Copy to rack .* \(empty\)$/);
  return rendered;
}
async function preview() {
  fireEvent.click(screen.getByRole("button", { name: "Select shown compatible shelves" }));
  fireEvent.click(screen.getByRole("button", { name: "Preview shelf copies" }));
  await screen.findByRole("button", { name: "Save layout with shelf copies" });
}
it("chooses a stocked source, previews exact products, saves and explicitly opens a new layout", async () => {
  await open();
  expect((screen.getByLabelText("Copy to rack Stocked shelf (stocked)") as HTMLInputElement).disabled).toBe(true);
  await preview();
  expect(api.previewRackCopy).toHaveBeenCalledWith("p", "s", { source_sha256: options.source_sha256, currency: "USD", source_rack_id: "stocked", target_rack_ids: ["empty"] });
  expect(screen.getByRole("region", { name: "Shelf copy preview" }).textContent).toContain("Tea · 茶 · $2.31");
  fireEvent.click(screen.getByRole("button", { name: "Save layout with shelf copies" }));
  const openCopy = await screen.findByRole("button", { name: "Open copied layout" });
  // The confirmation replaces the save button, so focus moves to it.
  expect(document.activeElement).toBe(screen.getByRole("status"));
  fireEvent.click(openCopy);
  await waitFor(() => expect(useSimulationStore.getState().selectedSetupId).toBe("setup_copied"));
});

it("retains hidden selections and discards preview on changed choices", async () => {
  await open(); await preview();
  fireEvent.change(screen.getByLabelText("Search destination shelves"), { target: { value: "茶" } });
  expect(screen.getByText(/1 selected across all filters/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
  expect(screen.queryByRole("region", { name: "Shelf copy preview" })).toBeNull();
  expect(api.saveRackCopy).not.toHaveBeenCalled();
});
it("does not relabel a USD preview with a refreshed currency and requires a new preview", async () => {
  await open(); await preview();
  vi.mocked(api.getRackCopyOptions).mockResolvedValue({ ...options, source_sha256: "b".repeat(64), currency: "KRW", source_rack_id: "stocked", targets: [empty] });
  await qc.invalidateQueries({ queryKey: ["rack-copy", "p", "s"] });
  await waitFor(() => expect(screen.queryByRole("button", { name: "Save layout with shelf copies" })).toBeNull());
  expect(screen.queryByRole("region", { name: "Shelf copy preview" })).toBeNull();
  expect(api.saveRackCopy).not.toHaveBeenCalled();
});
it("keeps the identical request identity after an uncertain save and locks editing while pending", async () => {
  await open();
  let finish!: (value: api.RackCopyPreview) => void;
  vi.mocked(api.previewRackCopy).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  fireEvent.click(screen.getByLabelText("Copy to rack Empty shelf (empty)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview shelf copies" }));
  await waitFor(() => expect(screen.getByLabelText("Copy products from").matches(":disabled")).toBe(true));
  finish(report);
  await screen.findByRole("button", { name: "Save layout with shelf copies" });
  vi.mocked(api.saveRackCopy).mockRejectedValueOnce(new Error("Lost response"));
  fireEvent.click(screen.getByRole("button", { name: "Save layout with shelf copies" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry saving shelf copies" }));
  await screen.findByRole("button", { name: "Open copied layout" });
  expect(vi.mocked(api.saveRackCopy).mock.calls[0]![2]).toEqual(vi.mocked(api.saveRackCopy).mock.calls[1]![2]);
});
it("shows preview failure while retaining the selections for correction", async () => {
  await open();
  vi.mocked(api.previewRackCopy).mockRejectedValueOnce(new Error("Layout changed. Reload shelves"));
  fireEvent.click(screen.getByLabelText("Copy to rack Empty shelf (empty)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview shelf copies" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Layout changed");
  expect((screen.getByLabelText("Copy to rack Empty shelf (empty)") as HTMLInputElement).checked).toBe(true);
  expect(screen.queryByRole("button", { name: "Save layout with shelf copies" })).toBeNull();
});
it("handles loading failure and explicit retry without an API save", async () => {
  vi.mocked(api.getRackCopyOptions).mockRejectedValueOnce(new Error("Offline"));
  render(view()); fireEvent.click(screen.getByRole("button", { name: "Reuse shelf products" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Offline");
  fireEvent.click(screen.getByRole("button", { name: "Retry shelves" }));
  await screen.findByRole("option", { name: /Stocked shelf/ });
  expect(api.saveRackCopy).not.toHaveBeenCalled();
});
it("does not show previous source targets while the next source loads", async () => {
  await open();
  let finish!: (value: api.RackCopyOptions) => void;
  vi.mocked(api.getRackCopyOptions).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  fireEvent.change(screen.getByLabelText("Copy products from"), { target: { value: "" } });
  expect(screen.queryByLabelText("Copy to rack Empty shelf (empty)")).toBeNull();
  finish(options);
  await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
});
it.each(["close", "layout"])("ignores late saved result after %s", async action => {
  let finish!: (value: api.RackCopySaved) => void;
  vi.mocked(api.saveRackCopy).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  const rendered = await open(); await preview();
  fireEvent.click(screen.getByRole("button", { name: "Save layout with shelf copies" }));
  await waitFor(() => expect(api.saveRackCopy).toHaveBeenCalledTimes(1));
  if (action === "close") {
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByRole("button", { name: "Reuse shelf products" }));
  } else rendered.rerender(view("new"));
  finish({ setup_id: "late", placements_added: 1 });
  await screen.findByRole("option", { name: /Stocked shelf/ });
  expect(screen.queryByRole("button", { name: "Open copied layout" })).toBeNull();
  expect(useSimulationStore.getState().selectedSetupId).not.toBe("late");
});
it("enforces the 100 destination limit across searches before calling the API", async () => {
  vi.mocked(api.getRackCopyOptions).mockImplementation(async (_p, _s, id) => ({ ...options, source_rack_id: id || null, targets: id ? Array.from({ length: 101 }, (_, n) => ({ ...empty, id: n ? `rack_${n}` : "empty", name: `Shelf ${n}` })) : [] }));
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Select shown compatible shelves" }));
  fireEvent.change(screen.getByLabelText("Search destination shelves"), { target: { value: "rack_100" } });
  fireEvent.click(screen.getByLabelText("Copy to rack Shelf 100 (rack_100)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview shelf copies" }));
  expect((await screen.findByRole("alert")).textContent).toContain("at most 100");
  expect(api.previewRackCopy).not.toHaveBeenCalled();
});
it("retries an uncertain save after refresh using its original snapshot and currency", async () => {
  await open(); await preview();
  vi.mocked(api.saveRackCopy).mockRejectedValueOnce(new Error("Lost response"));
  fireEvent.click(screen.getByRole("button", { name: "Save layout with shelf copies" }));
  await screen.findByRole("button", { name: "Retry saving shelf copies" });
  vi.mocked(api.getRackCopyOptions).mockResolvedValue({ ...options, source_sha256: "b".repeat(64), currency: "KRW", source_rack_id: "stocked", targets: [empty] });
  await qc.invalidateQueries({ queryKey: ["rack-copy", "p", "s"] });
  await waitFor(() => expect(screen.queryByText("Checking shelves…")).toBeNull());
  expect(screen.getByRole("region", { name: "Shelf copy preview" }).textContent).toContain("$2.31");
  expect(screen.getByRole("region", { name: "Shelf copy preview" }).textContent).not.toContain("KRW");
  fireEvent.click(screen.getByRole("button", { name: "Retry saving shelf copies" }));
  await screen.findByRole("button", { name: "Open copied layout" });
  expect(vi.mocked(api.saveRackCopy).mock.calls[0]![2]).toEqual(vi.mocked(api.saveRackCopy).mock.calls[1]![2]);
});
it("keeps the source selector's accessible name independent of its product options", async () => {
  await open();
  expect(screen.getByRole("combobox", { name: "Copy products from" })).toBeTruthy();
});

it.each(["close", "layout", "project"].flatMap(scope => ["success", "failure"].map(result => ({ scope, result }))))(
  "discards a late preview $result after changing $scope", async ({ scope, result }) => {
    let resolve!: (value: api.RackCopyPreview) => void;
    let reject!: (error: Error) => void;
    vi.mocked(api.previewRackCopy).mockReturnValueOnce(new Promise((yes, no) => { resolve = yes; reject = no; }));
    const rendered = await open();
    fireEvent.click(screen.getByLabelText("Copy to rack Empty shelf (empty)"));
    fireEvent.click(screen.getByRole("button", { name: "Preview shelf copies" }));
    await waitFor(() => expect(api.previewRackCopy).toHaveBeenCalledTimes(1));
    if (scope === "close") {
      fireEvent.click(screen.getByRole("button", { name: "Close" }));
      fireEvent.click(screen.getByRole("button", { name: "Reuse shelf products" }));
    } else rendered.rerender(view(scope === "layout" ? "new" : "s", scope === "project" ? "new" : "p"));
    await act(async () => { if (result === "success") resolve(report); else reject(new Error("Old preview failed")); });
    await screen.findByRole("option", { name: /Stocked shelf/ });
    expect(screen.queryByRole("region", { name: "Shelf copy preview" })).toBeNull();
    expect(screen.queryByText("Old preview failed")).toBeNull();
    expect((screen.getByLabelText("Copy products from") as HTMLSelectElement).value).toBe("");
    expect(api.saveRackCopy).not.toHaveBeenCalled();
  },
);

it.each(["snapshot", "currency", "failure"])("never saves a pending preview invalidated by an options %s", async change => {
  let finish!: (value: api.RackCopyPreview) => void;
  vi.mocked(api.previewRackCopy).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  await open();
  fireEvent.click(screen.getByLabelText("Copy to rack Empty shelf (empty)"));
  fireEvent.click(screen.getByRole("button", { name: "Preview shelf copies" }));
  await waitFor(() => expect(api.previewRackCopy).toHaveBeenCalledTimes(1));
  if (change === "failure") vi.mocked(api.getRackCopyOptions).mockRejectedValue(new Error("Source unavailable"));
  else vi.mocked(api.getRackCopyOptions).mockResolvedValue({ ...options, source_rack_id: "stocked", targets: [empty],
    source_sha256: change === "snapshot" ? "b".repeat(64) : options.source_sha256,
    currency: change === "currency" ? "JPY" : "USD" });
  await act(async () => { await qc.invalidateQueries({ queryKey: ["rack-copy", "p", "s"] }); finish(report); });
  await screen.findByText("The layout changed. Preview again before saving.");
  expect(screen.queryByRole("region", { name: "Shelf copy preview" })).toBeNull();
  expect(api.saveRackCopy).not.toHaveBeenCalled();
});

it("recovers an uncertain save even when the source options have become unavailable", async () => {
  await open(); await preview();
  vi.mocked(api.saveRackCopy).mockRejectedValueOnce(new Error("Lost response"));
  fireEvent.click(screen.getByRole("button", { name: "Save layout with shelf copies" }));
  await screen.findByRole("button", { name: "Retry saving shelf copies" });
  vi.mocked(api.getRackCopyOptions).mockRejectedValue(new Error("Source removed"));
  await act(async () => { await qc.invalidateQueries({ queryKey: ["rack-copy", "p", "s"] }); });
  fireEvent.click(screen.getByRole("button", { name: "Retry saving shelf copies" }));
  await screen.findByRole("button", { name: "Open copied layout" });
  expect(vi.mocked(api.saveRackCopy).mock.calls[0]![2]).toEqual(vi.mocked(api.saveRackCopy).mock.calls[1]![2]);
});

it.each(["USD", "CAD", "CNY", "KRW", "JPY", "VND"])("shows exact safe-integer prices in a %s preview", async currency => {
  vi.mocked(api.getRackCopyOptions).mockImplementation(async (_p, _s, id) => ({ ...options, currency, source_rack_id: id || null, targets: id ? [empty] : [] }));
  vi.mocked(api.previewRackCopy).mockResolvedValue({ ...report, slots: [{ block: 0, face: "S", level: 1,
    items: [{ ...product, price: 9007199254740991, regular_price: 9007199254740990 }] }] });
  await open(); await preview();
  const previewText = screen.getByRole("region", { name: "Shelf copy preview" }).textContent;
  const unit = ["KRW", "JPY", "VND"].includes(currency);
  expect(previewText).toContain(unit ? "9,007,199,254,740,991" : "90,071,992,547,409.91");
  expect(previewText).toContain("regular price");
  expect(previewText).toContain(unit ? "9,007,199,254,740,990" : "90,071,992,547,409.90");
});
