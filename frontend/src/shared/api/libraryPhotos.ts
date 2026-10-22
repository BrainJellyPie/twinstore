import { BASE } from "./client";
import { apiErrorMessage } from "./errors";
export interface PhotoAsset { asset_id: string; name: string; sku: string; version: string; image_url: string }
export interface PhotoProduct { sku: string; names: string[]; image_urls: string[]; placements: number }
export interface PhotoOptions { source_sha256: string; assets: PhotoAsset[]; products: PhotoProduct[] }
export interface PhotoAssignment { sku: string; asset_id: string; version: string }
export interface PhotoRequest { source_sha256: string; assignments: PhotoAssignment[]; replace_existing: boolean }
export interface PhotoSave extends PhotoRequest { request_id: string }
export interface PhotoChange extends PhotoProduct { asset_name: string; image_url: string }
export interface PhotoPreview { changes: PhotoChange[]; changed_placements: number }
export interface PhotoSaved { setup_id: string; changed_placements: number }
const url = (pid: string, sid: string) => `${BASE}/api/projects/${encodeURIComponent(pid)}/setups/${encodeURIComponent(sid)}/library-photos`;
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), `Request failed (${response.status})`));
  return response.json() as Promise<T>;
}
export const getLibraryPhotos = (pid: string, sid: string, signal?: AbortSignal) => request<PhotoOptions>(url(pid, sid), { signal });
export const previewLibraryPhotos = (pid: string, sid: string, body: PhotoRequest) => request<PhotoPreview>(`${url(pid, sid)}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const saveLibraryPhotos = (pid: string, sid: string, body: PhotoSave) => request<PhotoSaved>(`${url(pid, sid)}/save`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
