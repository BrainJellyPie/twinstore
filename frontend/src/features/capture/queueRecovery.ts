import type { CaptureDetector } from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { fileDigest, fileProblem, MAX_FILE_BYTES, MAX_QUEUE_BYTES, MAX_QUEUE_FILES } from "./uploadFiles";

export interface RecoveryOptions {
  detector: CaptureDetector;
  model: string;
  currency: string;
  rack_type: "shelf" | "fridge";
}
export interface QueuePhoto {
  id: string;
  requestId: string;
  digest: string;
  file: File;
}
interface StoredPhoto extends Omit<QueuePhoto, "file"> {
  name: string;
  type: string;
  lastModified: number;
  blob: Blob;
}
export interface RecoveryCopy {
  version: 1;
  projectId: string;
  revision: string;
  savedAt: string;
  options: RecoveryOptions;
  photos: StoredPhoto[];
}

const DB = "twinstore-photo-recovery";
const STORE = "queues";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const message = (key: MessageKey) => translate(useLocale.getState().locale, key);
const conflict = () => new Error(message("capRecoveryConflict"));
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object";
const text = (v: unknown, max: number): v is string => typeof v === "string" && v.length <= max;

export function recoveryErrorMessage(error: unknown): string {
  if (object(error) && error.name === "QuotaExceededError") return message("capStorageFull");
  return object(error) && typeof error.message === "string" ? error.message : message("capStorageFailed");
}

export function validateRecovery(value: unknown, projectId: string): RecoveryCopy {
  const invalid = () => new Error(message("capRecoveryInvalid"));
  if (!object(value) || value.version !== 1 || value.projectId !== projectId
    || typeof value.revision !== "string" || !uuid.test(value.revision)
    || typeof value.savedAt !== "string" || !Number.isFinite(Date.parse(value.savedAt))
    || !object(value.options) || !Array.isArray(value.photos) || !value.photos.length || value.photos.length > MAX_QUEUE_FILES) throw invalid();
  const options = value.options;
  if (typeof options.detector !== "string" || !["auto", "classic", "gdino", "vlm"].includes(options.detector)
    || !text(options.model, 512) || typeof options.currency !== "string" || options.currency.length !== 3 || !/^[A-Z]{3}$/.test(options.currency)
    || typeof options.rack_type !== "string" || !["shelf", "fridge"].includes(options.rack_type)) throw invalid();
  const ids = new Set<string>(), requests = new Set<string>(), digests = new Set<string>();
  let bytes = 0;
  for (const p of value.photos as unknown[]) {
    if (!object(p) || typeof p.id !== "string" || !uuid.test(p.id)
      || typeof p.requestId !== "string" || !/^[0-9a-f]{32}$/.test(p.requestId)
      || typeof p.digest !== "string" || !/^[0-9a-f]{64}$/.test(p.digest)
      || !text(p.name, 1024) || !p.name || !text(p.type, 100)
      || typeof p.lastModified !== "number" || !Number.isSafeInteger(p.lastModified) || p.lastModified < 0
      || !(p.blob instanceof Blob) || !p.blob.size || p.blob.size > MAX_FILE_BYTES
      || p.blob.type !== p.type || ids.has(p.id) || requests.has(p.requestId) || digests.has(p.digest)) throw invalid();
    if (!["image/jpeg", "image/png", "image/webp"].includes(p.type) && (p.type || !/\.(jpe?g|png|webp)$/i.test(p.name))) throw invalid();
    ids.add(p.id); requests.add(p.requestId); digests.add(p.digest); bytes += p.blob.size;
  }
  if (bytes > MAX_QUEUE_BYTES) throw invalid();
  return value as unknown as RecoveryCopy;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) { reject(new Error(message("capRecoveryUnsupported"))); return; }
    let finished = false;
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "projectId" });
    request.onblocked = () => { finished = true; reject(new Error(message("capRecoveryBlocked"))); };
    request.onerror = () => { finished = true; reject(request.error ?? new Error(message("capStorageUnavailable"))); };
    request.onsuccess = () => {
      if (finished) { request.result.close(); return; }
      request.result.onversionchange = () => request.result.close();
      resolve(request.result);
    };
  });
}

export async function readRecovery(projectId: string): Promise<RecoveryCopy | null> {
  const db = await open();
  try {
    const raw: unknown = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly"), request = tx.objectStore(STORE).get(projectId);
      tx.oncomplete = () => resolve(request.result);
      tx.onabort = () => reject(tx.error ?? new Error(message("capStorageReadFailed")));
    });
    return raw === undefined ? null : validateRecovery(raw, projectId);
  } finally { db.close(); }
}

async function replace(projectId: string, expected: string | null, next: RecoveryCopy | null): Promise<void> {
  const db = await open();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite"), store = tx.objectStore(STORE);
      let reason: Error | null = null;
      tx.oncomplete = () => resolve();
      tx.onabort = () => reject(reason ?? tx.error ?? new Error(message("capStorageSaveFailed")));
      const get = store.get(projectId);
      get.onsuccess = () => {
        const current: unknown = get.result;
        if ((expected === null && current !== undefined)
          || (expected !== null && (!object(current) || current.revision !== expected))) {
          reason = conflict(); tx.abort(); return;
        }
        try { if (next) store.put(next); else store.delete(projectId); }
        catch (error) { reason = error instanceof Error ? error : new Error(recoveryErrorMessage(error)); tx.abort(); }
      };
    });
  } finally { db.close(); }
}

export function queueIntent(photos: QueuePhoto[], options: RecoveryOptions): string {
  return JSON.stringify({ options, photos: photos.map(p => ({ id: p.id, requestId: p.requestId, digest: p.digest,
    name: p.file.name, type: p.file.type, size: p.file.size, lastModified: p.file.lastModified })) });
}

export async function saveRecovery(projectId: string, expected: string | null, photos: QueuePhoto[], options: RecoveryOptions): Promise<RecoveryCopy> {
  const copy = validateRecovery({ version: 1, projectId, revision: crypto.randomUUID(), savedAt: new Date().toISOString(), options,
    photos: photos.map(({ file, id, requestId, digest }) => ({ id, requestId, digest, name: file.name, type: file.type, lastModified: file.lastModified, blob: file })) }, projectId);
  await replace(projectId, expected, copy);
  return copy;
}
export async function checkRecoveryRevision(projectId: string, revision: string): Promise<void> {
  if ((await readRecovery(projectId))?.revision !== revision) throw conflict();
}
export const forgetRecovery = (projectId: string, revision: string) => replace(projectId, revision, null);

export async function restoreRecovery(copy: RecoveryCopy): Promise<QueuePhoto[]> {
  validateRecovery(copy, copy.projectId);
  const photos: QueuePhoto[] = [];
  for (const p of copy.photos) {
    const file = new File([p.blob], p.name, { type: p.type, lastModified: p.lastModified });
    if (fileProblem(file) || await fileDigest(file) !== p.digest) {
      throw new Error(message("capRecoveryIntegrity"));
    }
    photos.push({ id: p.id, requestId: p.requestId, digest: p.digest, file });
  }
  return photos;
}
