import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { IDBFactory, IDBObjectStore } from "fake-indexeddb";
import { createHash } from "node:crypto";
import { readRecovery, saveRecovery, restoreRecovery, forgetRecovery, validateRecovery, type QueuePhoto, type RecoveryOptions } from "../queueRecovery";
import { MAX_FILE_BYTES } from "../uploadFiles";

const options: RecoveryOptions = { detector: "classic", model: "none", currency: "USD", rack_type: "shelf" };
function photo(name = "Shelf 🛒.png", data = "image bytes"): QueuePhoto {
  return { id: crypto.randomUUID(), requestId: crypto.randomUUID().replace(/-/g, ""), digest: createHash("sha256").update(data).digest("hex"),
    file: new File([data], name, { type: "image/png", lastModified: 17 }) };
}
beforeEach(() => {
  vi.stubGlobal("indexedDB", new IDBFactory());
  // Node has native File/Blob structured cloning but no FileReader; adapt that browser boundary.
  vi.stubGlobal("FileReader", class {
    result: ArrayBuffer | null = null;
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    readAsArrayBuffer(blob: Blob) { void blob.arrayBuffer().then(result => { this.result = result; this.onload?.(); }, () => this.onerror?.()); }
  });
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("saves photo bytes and exact upload intent, restores them and forgets only that project", async () => {
  const first = photo();
  const saved = await saveRecovery("project_a", null, [first], options);
  await saveRecovery("project_b", null, [photo("Other.png")], options);
  const copy = await readRecovery("project_a");
  expect(copy?.revision).toBe(saved.revision);
  const restored = await restoreRecovery(copy!);
  expect(restored[0]?.requestId).toBe(first.requestId);
  expect(restored[0]?.file.name).toBe(first.file.name);
  expect(restored[0]?.file.lastModified).toBe(17);
  expect(await restored[0]?.file.text()).toBe("image bytes");
  expect(copy?.options).toEqual(options);
  await forgetRecovery("project_a", saved.revision);
  expect(await readRecovery("project_a")).toBeNull();
  expect(await readRecovery("project_b")).not.toBeNull();
});

it("rejects competing writes and stale deletion without replacing the winning queue", async () => {
  const initial = await saveRecovery("p", null, [photo()], options);
  const attempts = await Promise.allSettled([
    saveRecovery("p", initial.revision, [photo("one.png", "one")], options),
    saveRecovery("p", initial.revision, [photo("two.png", "two")], options),
  ]);
  expect(attempts.filter(v => v.status === "fulfilled")).toHaveLength(1);
  const winner = await readRecovery("p");
  expect(winner?.revision).not.toBe(initial.revision);
  await expect(forgetRecovery("p", initial.revision)).rejects.toThrow(/another tab/);
  await expect(saveRecovery("p", null, [photo()], options)).rejects.toThrow(/another tab/);
  expect((await readRecovery("p"))?.revision).toBe(winner?.revision);
});

it.each(["QuotaExceededError", "DataCloneError", "AbortError"])("preserves the prior snapshot and live files on %s", async (name) => {
  const files = [photo()], initial = await saveRecovery("p", null, files, options);
  vi.spyOn(IDBObjectStore.prototype, "put").mockImplementationOnce(() => { throw new DOMException("Injected storage failure", name); });
  await expect(saveRecovery("p", initial.revision, [photo("new.png", "new")], options)).rejects.toThrow("Injected storage failure");
  expect((await readRecovery("p"))?.revision).toBe(initial.revision);
  expect(await files[0]!.file.text()).toBe("image bytes");
});

it("retains an actionable quota error when a browser exception is not an Error instance", async () => {
  const initial = await saveRecovery("p", null, [photo()], options);
  vi.spyOn(IDBObjectStore.prototype, "put").mockImplementationOnce(() => { throw { name: "QuotaExceededError", message: "The quota has been exceeded." }; });
  await expect(saveRecovery("p", initial.revision, [photo("new.png", "new")], options)).rejects.toThrow(/Browser storage is full/);
  expect((await readRecovery("p"))?.revision).toBe(initial.revision);
});

it("refuses changed photo bytes even when metadata still contains the old digest", async () => {
  const copy = await saveRecovery("p", null, [photo()], options);
  copy.photos[0]!.blob = new Blob(["different bytes"], { type: "image/png" });
  await expect(restoreRecovery(copy)).rejects.toThrow(/integrity check/);
  expect(await (await restoreRecovery((await readRecovery("p"))!))[0]!.file.text()).toBe("image bytes");
});

it.each([
  ["version", 2], ["projectId", "elsewhere"], ["revision", "-".repeat(36)], ["savedAt", "not a date"],
  ["photos", []], ["options", { ...options, currency: "usd" }], ["options", { ...options, model: "a".repeat(513) }],
  ["options", { ...options, detector: "unknown" }], ["options", { ...options, rack_type: "counter" }],
])("rejects malformed recovery field %s without touching the stored copy", async (field, value) => {
  const saved = await saveRecovery("p", null, [photo()], options);
  expect(() => validateRecovery({ ...saved, [String(field)]: value }, "p")).toThrow(/unreadable/);
  expect((await readRecovery("p"))?.revision).toBe(saved.revision);
});

it.each([
  ["id", "bad"], ["requestId", "A".repeat(32)], ["digest", "0".repeat(63)], ["name", ""],
  ["name", "x".repeat(1025)], ["lastModified", -1], ["lastModified", NaN], ["lastModified", Infinity],
  ["lastModified", 1.5], ["type", "text/html"], ["blob", new Blob([], { type: "image/png" })],
])("rejects malformed saved photo field %s", async (field, value) => {
  const saved = await saveRecovery("p", null, [photo()], options);
  expect(() => validateRecovery({ ...saved, photos: [{ ...saved.photos[0], [String(field)]: value }] }, "p")).toThrow(/unreadable/);
});

it("keeps empty/duplicate and oversize queues out of storage; accepts the exact count boundary", async () => {
  await expect(saveRecovery("p", null, [], options)).rejects.toThrow();
  const files = Array.from({ length: 20 }, (_, n) => photo(`${n}.png`, String(n)));
  const saved = await saveRecovery("p", null, files, options);
  await expect(saveRecovery("p", saved.revision, [...files, photo("extra.png")], options)).rejects.toThrow();
  await expect(saveRecovery("p", saved.revision, [files[0]!, files[0]!], options)).rejects.toThrow();
  expect((await readRecovery("p"))?.photos).toHaveLength(20);
});

it("accepts 100 MB but rejects total or per-file overflow before replacing the copy", async () => {
  const files = Array.from({ length: 4 }, (_, n) => ({ ...photo(`${n}.png`, String(n)), file: new File([new Uint8Array(MAX_FILE_BYTES)], `${n}.png`, { type: "image/png" }) }));
  const saved = await saveRecovery("p", null, files, options);
  await expect(saveRecovery("p", saved.revision, [...files, photo("extra.png")], options)).rejects.toThrow();
  await expect(saveRecovery("p", saved.revision, [{ ...photo(), file: new File([new Uint8Array(MAX_FILE_BYTES + 1)], "large.png", { type: "image/png" }) }], options)).rejects.toThrow();
  expect((await readRecovery("p"))?.revision).toBe(saved.revision);
});

it("reports unavailable browser storage", async () => {
  vi.stubGlobal("indexedDB", undefined);
  await expect(readRecovery("p")).rejects.toThrow(/does not support/);
});

it.each(["USD", "EUR", "GBP", "CAD", "AUD", "NZD", "CHF", "PLN", "KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR", "CNY", "SGD"])(
  "preserves a store's %s currency through a saved queue", async currency => {
    const original = photo();
    const copy = await saveRecovery("p", null, [original], { ...options, currency });
    expect((await readRecovery("p"))?.options.currency).toBe(currency);
    expect((await restoreRecovery(copy))[0]?.requestId).toBe(original.requestId);
  },
);

it.each(["", "usd", "US", "USDD", "USD\n", "ＵＳＤ", "U D"])("rejects malformed currency %j without replacing a valid copy", async currency => {
  const initial = await saveRecovery("p", null, [photo()], options);
  await expect(saveRecovery("p", initial.revision, [photo()], { ...options, currency })).rejects.toThrow(/unreadable/);
  expect((await readRecovery("p"))?.revision).toBe(initial.revision);
});

it.each(["revision", "id", "requestId", "digest"])("rejects a newline suffix on saved %s before a restored upload can use it", async field => {
  const initial = await saveRecovery("p", null, [photo()], options);
  const copy = structuredClone(initial);
  if (field === "revision") copy.revision += "\n";
  else copy.photos[0]![field as "id" | "requestId" | "digest"] += "\n";
  expect(() => validateRecovery(copy, "p")).toThrow(/unreadable/);
  expect((await readRecovery("p"))?.revision).toBe(initial.revision);
});
