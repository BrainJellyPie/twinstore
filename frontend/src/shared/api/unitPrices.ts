import { BASE } from "./client";
import { apiErrorMessage, apiFetch } from "./errors";

export interface PriceScope { focal_retailer: string; as_of: string; max_age_days: number }
export interface PriceUpload extends PriceScope { file: File }
export interface PriceExport extends PriceUpload { source_sha256: string }
export type PriceFlag = "future" | "stale" | "out_of_stock" | "unknown_availability" | "conditional_offer";
export interface OfferReview {
  inputs: { offer_id: string; comparison_group: string; retailer: string; observed_on: string; currency: string;
    pack_count: number; quantity_per_pack: string; unit: string; price_minor: number; availability: string; terms: string };
  basis: string; quantity_in_basis: string; unit_price_minor: string; unit_price_exact: string; flags: PriceFlag[];
}
export interface PriceComparison {
  comparison_group: string; currency: string; basis: string; focal_count: number; competitor_count: number; competitor_retailers: number;
  focal_min_minor: string | null; competitor_min_minor: string | null; gap_minor: string | null; gap_exact: string | null;
  gap_percent: string | null; relation: "below" | "equal" | "above" | "unavailable";
  focal_offer_ids: string[]; competitor_offers: [string, string][];
}
export interface UnitPriceReport {
  method: "observed-unit-prices-v1"; scope: PriceScope; source_sha256: string;
  rows: OfferReview[]; comparisons: PriceComparison[]; notes: string[];
}
export async function unitPriceTemplate(pid: string): Promise<Blob> {
  const response = await apiFetch(`${BASE}/api/projects/${pid}/unit-prices/template.csv`);
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Offer template failed"));
  return response.blob();
}
async function requestPrices(pid: string, req: PriceUpload | PriceExport): Promise<Response> {
  const body = new FormData(); body.append("file", req.file); body.append("focal_retailer", req.focal_retailer);
  body.append("as_of", req.as_of); body.append("max_age_days", String(req.max_age_days));
  const csv = "source_sha256" in req;
  if (csv) body.append("source_sha256", req.source_sha256);
  const response = await apiFetch(`${BASE}/api/projects/${pid}/unit-prices/${csv ? "export.csv" : "preview"}`, { method: "POST", body });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Unit-price review failed"));
  return response;
}
export async function previewUnitPrices(pid: string, req: PriceUpload): Promise<UnitPriceReport> {
  return (await requestPrices(pid, req)).json() as Promise<UnitPriceReport>;
}
export async function exportUnitPrices(pid: string, req: PriceExport): Promise<Blob> {
  return (await requestPrices(pid, req)).blob();
}
