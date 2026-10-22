import { BASE } from "./client";
import { apiErrorMessage } from "./errors";
export interface StarterProduct { sku: string; name: string; price: number; promo: string; regular_price: number; image_url: string | null }
export interface StarterCategory { key: string; label: string; products: StarterProduct[] }
export interface StarterRack { id: string; name: string; type: string; available_slots: number; suggested_category: string | null; reason: string | null }
export interface StarterCatalog { source_sha256: string; currency: string; racks: StarterRack[]; categories: StarterCategory[] }
export interface StarterRequest { source_sha256: string; currency: string; assignments: { rack_id: string; category: string; skus?: string[] | null }[]; products_per_slot: number }
export interface StarterAutoRequest { source_sha256: string; currency: string; requirements: string; products_per_slot: number }
export interface StarterSave extends StarterRequest { request_id: string }
export interface StarterPreview { placements_added: number; new_skus: number; reused_skus: number; racks: { id: string; name: string; category: string; slots_added: number; placements_added: number; products: StarterProduct[]; reused_skus: string[] }[] }
export interface StarterSaved { setup_id: string; placements_added: number }
const url = (pid: string, sid: string) => `${BASE}/api/projects/${encodeURIComponent(pid)}/setups/${encodeURIComponent(sid)}/starter-fill`;
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), `Request failed (${response.status})`));
  return response.json() as Promise<T>;
}
export const getStarterCatalog = (pid: string, sid: string, signal?: AbortSignal) => request<StarterCatalog>(url(pid, sid), { signal });
export const autoSelectStarterProducts = (pid: string, sid: string, body: StarterAutoRequest) => request<StarterRequest>(`${url(pid, sid)}/auto-select`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const previewStarterFill = (pid: string, sid: string, body: StarterRequest) => request<StarterPreview>(`${url(pid, sid)}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const saveStarterFill = (pid: string, sid: string, body: StarterSave) => request<StarterSaved>(`${url(pid, sid)}/save`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
