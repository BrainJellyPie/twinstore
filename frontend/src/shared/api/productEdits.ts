import { BASE } from "./client";
import { ApiError, apiErrorMessage, apiFetch } from "./errors";
export interface ProductRow { sku: string; names: string[]; prices: number[]; promos: string[]; placements: number; racks: string[] }
export interface ProductCatalog { source_sha256: string; currency: string; products: ProductRow[] }
export interface ProductEdit { sku: string; name?: string; price?: number; promo?: string }
export interface ProductEditsRequest { source_sha256: string; currency: string; edits: ProductEdit[] }
export interface ProductEditsSave extends ProductEditsRequest { request_id: string }
export interface ProductEditsPreview { changes: { before: ProductRow; after: ProductRow; changed_placements: number }[]; changed_placements: number }
export interface ProductEditsSaved { setup_id: string; changed_placements: number }
const url = (pid: string, sid: string) => `${BASE}/api/projects/${encodeURIComponent(pid)}/setups/${encodeURIComponent(sid)}/product-edits`;
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) throw new ApiError(apiErrorMessage(await response.text(), `Request failed (${response.status})`), response.status);
  return response.json() as Promise<T>;
}
export const getProductCatalog = (pid: string, sid: string, signal?: AbortSignal) => request<ProductCatalog>(url(pid, sid), { signal });
export const previewProductEdits = (pid: string, sid: string, body: ProductEditsRequest) => request<ProductEditsPreview>(`${url(pid, sid)}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const saveProductEdits = (pid: string, sid: string, body: ProductEditsSave) => request<ProductEditsSaved>(`${url(pid, sid)}/save`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
