// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/client";
import * as recovery from "../queueRecovery";
import { CaptureUploadQueue } from "../CaptureUploadQueue";
vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(),
  getProject: vi.fn(), getModels: vi.fn(), createCapture: vi.fn(), getCapture: vi.fn() }));
vi.mock("../queueRecovery", async original => ({ ...await original<typeof import("../queueRecovery")>(),
  readRecovery: vi.fn(), saveRecovery: vi.fn(), checkRecoveryRevision: vi.fn(), forgetRecovery: vi.fn() }));
let qc: QueryClient, disk: recovery.RecoveryCopy | null;
const review = vi.fn();
const status: api.CaptureStatus = { capture_id: "cap_a", status: "completed", stage: "done", progress: 1, error: "",
  options: { detector: "classic", model: "none", currency: "USD", rack_type: "shelf", label: "" },
  image_name: "shelf.png", image_size: [200, 200], created_at: "", finished_at: "", items: 2, facings: 2, gaps: 0, levels: 1, applied_setup_ids: [] };
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto); disk = null;
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { currency: "USD" } } as api.ProjectDetail);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.createCapture).mockResolvedValue(status);
  vi.mocked(api.getCapture).mockResolvedValue({ status, result: null });
  vi.mocked(recovery.readRecovery).mockImplementation(async () => disk);
  vi.mocked(recovery.saveRecovery).mockImplementation(async (projectId, _revision, photos, options) => {
    disk = { version: 1, projectId, revision: crypto.randomUUID(), savedAt: new Date().toISOString(), options,
      photos: photos.map(p => ({ id: p.id, requestId: p.requestId, digest: p.digest, name: p.file.name, type: p.file.type, lastModified: p.file.lastModified, blob: p.file })) };
    return disk;
  });
  vi.mocked(recovery.checkRecoveryRevision).mockResolvedValue(undefined);
  vi.mocked(recovery.forgetRecovery).mockImplementation(async () => { disk = null; });
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  return render(<QueryClientProvider client={qc}><CaptureUploadQueue projectId="p" onAccepted={() => {}} onReview={review} /></QueryClientProvider>);
}
async function choose() {
  await waitFor(() => expect((screen.getByRole("button", { name: "Choose photos or drop them here" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText("Shelf photo files"), { target: { files: [new File(["first"], "Shelf 🛒.png", { type: "image/png" }), new File(["second"], "second.png", { type: "image/png" })] } });
  await screen.findByText(/0 of 2 ready/);
}
async function save() {
  fireEvent.click(screen.getByRole("button", { name: "Save queue on this browser" }));
  await screen.findByText(/Recovery copy saved in this browser/);
}
it("restores paused with original settings and replays the same upload after a lost response", async () => {
  const view = mount();
  fireEvent.change(screen.getByLabelText("Find products with"), { target: { value: "classic" } });
  fireEvent.change(screen.getByLabelText("Read products with"), { target: { value: "none" } });
  await choose(); await save();
  expect(api.createCapture).not.toHaveBeenCalled();
  vi.mocked(api.createCapture).mockRejectedValueOnce(new Error("Accepted, but response was lost"));
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByRole("button", { name: "Retry this photo" });
  const original = vi.mocked(api.createCapture).mock.calls[0]![2];
  view.unmount(); qc.clear();
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { currency: "KRW" } } as api.ProjectDetail);
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Restore saved queue" }));
  await screen.findByText(/Queue restored and paused/);
  expect((screen.getByLabelText("Prices in") as HTMLSelectElement).value).toBe("USD");
  expect((screen.getByLabelText("Read products with") as HTMLSelectElement).value).toBe("none");
  expect(api.createCapture).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/2 of 2 ready/);
  expect(vi.mocked(api.createCapture).mock.calls[1]![2]).toEqual(original);
  expect(vi.mocked(api.createCapture).mock.calls[1]![1].name).toBe("Shelf 🛒.png");
  expect(api.createCapture).toHaveBeenCalledTimes(3);
  fireEvent.click(screen.getAllByRole("button", { name: "Review photo" })[0]!);
  expect(review).toHaveBeenCalledWith("cap_a");
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  return { promise: new Promise<T>(r => { resolve = r; }), resolve: (value: T) => resolve(value) };
}

it("keeps the local queue and sends no upload when saving fails", async () => {
  mount(); await choose();
  vi.mocked(recovery.saveRecovery).mockRejectedValueOnce(new DOMException("Storage full", "QuotaExceededError"));
  fireEvent.click(screen.getByRole("button", { name: "Save queue on this browser" }));
  await screen.findByText(/Browser storage is full.*live queue was not replaced/);
  expect(screen.getByText(/0 of 2 ready/)).toBeTruthy();
  expect(api.createCapture).not.toHaveBeenCalled();
  expect(disk).toBeNull();
});

it("does not let the initial storage read overwrite a newer saved copy", async () => {
  const old = deferred<recovery.RecoveryCopy | null>();
  vi.mocked(recovery.readRecovery).mockReturnValueOnce(old.promise);
  mount(); await choose(); await save();
  await act(async () => old.resolve(null));
  expect(screen.getByText(/2 photos saved for this store/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Forget saved copy" }) as HTMLButtonElement).disabled).toBe(false);
});

it("blocks an upload from an old revision and lets the user replace local choices with the latest copy", async () => {
  mount(); await choose(); await save();
  const previous = disk!;
  disk = { ...previous, revision: crypto.randomUUID(), photos: [previous.photos[1]!] };
  vi.mocked(recovery.checkRecoveryRevision).mockRejectedValueOnce(new Error("Saved queue changed in another tab"));
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/Saved queue changed in another tab/);
  expect(api.createCapture).not.toHaveBeenCalled();
  const restore = screen.getByRole("button", { name: /Restore saved queue|Replace local queue from saved copy/ });
  expect((restore as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(restore);
  await screen.findByText(/Queue restored and paused/);
  expect(screen.getByText(/0 of 1 ready/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/1 of 1 ready/);
  expect(vi.mocked(api.createCapture).mock.calls[0]![2]?.request_id).toBe(previous.photos[1]!.requestId);
});

it("preserves local choices if a recovery copy has changed photo bytes", async () => {
  const view = mount(); await choose(); await save(); view.unmount();
  disk!.photos[0]!.blob = new Blob(["tampered"], { type: "image/png" });
  mount(); fireEvent.click(screen.getByRole("button", { name: "Restore saved queue" }));
  await screen.findByText(/integrity check.*live queue was not replaced/);
  expect(screen.getByText(/0 of 0 ready/)).toBeTruthy();
  expect(api.createCapture).not.toHaveBeenCalled();
  expect(recovery.forgetRecovery).not.toHaveBeenCalled();
});

it("pauses after the current photo even when the pause occurs during recovery verification", async () => {
  mount(); await choose(); await save();
  const checked = deferred<void>();
  vi.mocked(recovery.checkRecoveryRevision).mockReturnValueOnce(checked.promise);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await waitFor(() => expect(recovery.checkRecoveryRevision).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "Pause after current photo" }));
  await act(async () => checked.resolve());
  await screen.findByText(/1 of 2 ready/);
  expect(api.createCapture).toHaveBeenCalledTimes(1);
  expect((screen.getByRole("button", { name: "Start / resume queue" }) as HTMLButtonElement).disabled).toBe(false);
});

it("never starts an upload after leaving during the recovery check", async () => {
  const view = mount(); await choose(); await save();
  const checked = deferred<void>();
  vi.mocked(recovery.checkRecoveryRevision).mockReturnValueOnce(checked.promise);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await waitFor(() => expect(recovery.checkRecoveryRevision).toHaveBeenCalled());
  view.unmount(); await act(async () => checked.resolve());
  expect(api.createCapture).not.toHaveBeenCalled();
});

it("forgets only the saved copy and keeps the live queue available", async () => {
  mount(); await choose(); await save();
  fireEvent.click(screen.getByRole("button", { name: "Forget saved copy" }));
  await screen.findByText(/Browser recovery copy removed/);
  expect(disk).toBeNull(); expect(screen.getByText(/0 of 2 ready/)).toBeTruthy();
  expect(api.createCapture).not.toHaveBeenCalled();
});

it("persists a new recognition attempt ID before uploading and never uploads an unsaved retry", async () => {
  mount(); await choose(); await save();
  vi.mocked(api.getCapture).mockResolvedValueOnce({ status: { ...status, status: "failed", error: "Recognition failed" }, result: null });
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/1 of 2 ready/);
  const oldId = disk!.photos[0]!.requestId;
  vi.mocked(recovery.saveRecovery).mockRejectedValueOnce(new Error("Copy could not be written"));
  fireEvent.click(screen.getByRole("button", { name: "Retry recognition (new attempt)" }));
  await screen.findByText(/Copy could not be written/);
  expect(api.createCapture).toHaveBeenCalledTimes(2);
  expect(disk!.photos[0]!.requestId).toBe(oldId);
  fireEvent.click(screen.getByRole("button", { name: "Retry this photo" }));
  await screen.findByText(/2 of 2 ready/);
  const retry = vi.mocked(api.createCapture).mock.calls[2]![2]?.request_id;
  expect(retry).not.toBe(oldId); expect(disk!.photos[0]!.requestId).toBe(retry);
  const saves = vi.mocked(recovery.saveRecovery).mock.invocationCallOrder;
  const uploads = vi.mocked(api.createCapture).mock.invocationCallOrder;
  expect(saves[saves.length - 1]!).toBeLessThan(uploads[uploads.length - 1]!);
});

it("retains local choices when forgetting fails, then clears only after storage confirms removal", async () => {
  mount(); await choose(); await save();
  vi.mocked(recovery.forgetRecovery).mockRejectedValueOnce(new Error("Saved queue changed"));
  fireEvent.click(screen.getByRole("button", { name: "Clear queue and saved copy" }));
  await screen.findByText(/Saved queue changed.*live queue was not replaced/);
  expect(screen.getByText(/0 of 2 ready/)).toBeTruthy(); expect(disk).not.toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Clear queue and saved copy" }));
  await screen.findByText(/0 of 0 ready/); expect(disk).toBeNull();
});

it("keeps a saved model visible when it is absent from the current model list", async () => {
  const view = mount(); await choose(); await save(); view.unmount();
  disk!.options.model = "saved/model-not-listed";
  mount(); fireEvent.click(screen.getByRole("button", { name: "Restore saved queue" }));
  await screen.findByText(/Queue restored and paused/);
  expect(screen.getByRole("option", { name: "Saved model: saved/model-not-listed" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/2 of 2 ready/);
  expect(vi.mocked(api.createCapture).mock.calls[0]![2]?.model).toBe("saved/model-not-listed");
});

it.each(["CAD", "AUD", "CHF", "VND", "CLP", "TWD", "IDR", "CNY", "SGD"])("shows the exact %s store currency before saving and after restore", async currency => {
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { currency } } as api.ProjectDetail);
  const view = mount(); await choose();
  expect((screen.getByLabelText("Prices in") as HTMLSelectElement).value).toBe(currency);
  await save(); expect(disk?.options.currency).toBe(currency); view.unmount();
  qc.clear(); vi.mocked(api.getProject).mockResolvedValue({ metadata: { currency: "USD" } } as api.ProjectDetail);
  mount(); fireEvent.click(screen.getByRole("button", { name: "Restore saved queue" }));
  await screen.findByText(/Queue restored and paused/);
  expect((screen.getByLabelText("Prices in") as HTMLSelectElement).value).toBe(currency);
  expect(api.createCapture).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/2 of 2 ready/);
  expect(vi.mocked(api.createCapture).mock.calls.every(call => call[2]?.currency === currency)).toBe(true);
});

it("keeps new local photos when the saved revision changes during byte validation", async () => {
  const view = mount(); await choose(); await save(); view.unmount();
  mount(); await choose();
  vi.mocked(recovery.checkRecoveryRevision).mockRejectedValueOnce(new Error("Saved queue changed in another tab"));
  fireEvent.click(screen.getByRole("button", { name: "Replace local queue from saved copy" }));
  await screen.findByText(/Saved queue changed.*live queue was not replaced/);
  expect(screen.getByText(/0 of 2 ready/)).toBeTruthy();
  expect(api.createCapture).not.toHaveBeenCalled();
  expect(recovery.forgetRecovery).not.toHaveBeenCalled();
});

it("discards a restored queue after leaving during revision verification", async () => {
  const initial = mount(); await choose(); await save(); initial.unmount();
  const checked = deferred<void>();
  vi.mocked(recovery.checkRecoveryRevision).mockReturnValueOnce(checked.promise);
  const available = vi.fn();
  const view = render(<QueryClientProvider client={qc}><CaptureUploadQueue projectId="p" onAccepted={() => {}} onReview={review} onRecoveryAvailable={available} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Restore saved queue" }));
  await waitFor(() => expect(recovery.checkRecoveryRevision).toHaveBeenCalled());
  view.unmount(); available.mockClear(); await act(async () => checked.resolve());
  expect(api.createCapture).not.toHaveBeenCalled(); expect(available).not.toHaveBeenCalled();
});
