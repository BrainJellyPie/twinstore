import { BASE } from "./client";
import { ApiError, apiErrorMessage } from "./errors";
import type { StarterProduct } from "./starterFill";
export interface RackCopyChoice { id: string; name: string; type: string; placements: number; reason: string | null; reason_code?: string | null }
export interface RackCopyOptions { source_sha256: string; currency: string; source_rack_id: string | null; sources: RackCopyChoice[]; targets: RackCopyChoice[] }
export interface RackCopyRequest { source_sha256: string; currency: string; source_rack_id: string; target_rack_ids: string[] }
export interface RackCopySave extends RackCopyRequest { request_id: string }
export interface RackCopyPreview { source_name: string; slots: { block: number; face: string; level: number; items: StarterProduct[] }[]; targets: RackCopyChoice[]; placements_added: number }
export interface RackCopySaved { setup_id: string; placements_added: number }
const url = (pid: string, sid: string) => `${BASE}/api/projects/${encodeURIComponent(pid)}/setups/${encodeURIComponent(sid)}/rack-copy`;
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) throw new ApiError(apiErrorMessage(await response.text(), `Request failed (${response.status})`), response.status);
  return response.json() as Promise<T>;
}
export const getRackCopyOptions = (pid: string, sid: string, source: string, signal?: AbortSignal) => request<RackCopyOptions>(`${url(pid, sid)}${source ? `?source_rack_id=${encodeURIComponent(source)}` : ""}`, { signal });
export const previewRackCopy = (pid: string, sid: string, body: RackCopyRequest) => request<RackCopyPreview>(`${url(pid, sid)}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const saveRackCopy = (pid: string, sid: string, body: RackCopySave) => request<RackCopySaved>(`${url(pid, sid)}/save`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
