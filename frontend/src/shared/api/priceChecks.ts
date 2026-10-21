import { BASE } from "./client";
import { apiErrorMessage } from "./errors";

export interface PriceCheckScope { store_ref: string; audit_date: string }
export interface CheckUpload extends PriceCheckScope { labels: File; checkouts: File }
export interface CheckExport extends CheckUpload { source_sha256: string }
export interface PriceObservation { check_id: string; sku: string; pack_reference: string; checked_on: string; currency: string; price_minor: number; terms: "public" | "conditional" | "unknown" }
export type CheckFlag = "missing_label" | "missing_checkout" | "sku_mismatch" | "pack_mismatch" | "currency_mismatch" | "outside_audit_date" | "terms_unverified";
export interface PriceCheck { check_id: string; label: PriceObservation | null; checkout: PriceObservation | null; flags: CheckFlag[]; difference_minor: number | null; relation: "checkout_higher" | "checkout_lower" | "equal" | "unavailable" }
export interface PriceCheckTotals { currency: string; comparable: number; higher: number; lower: number; equal: number; positive_difference_minor: number; negative_difference_minor: number; net_difference_minor: number }
export interface PriceCheckReport { method: "observed-price-checks-v1"; scope: PriceCheckScope; source_sha256: string; label_count: number; checkout_count: number; excluded_count: number; rows: PriceCheck[]; totals: PriceCheckTotals[]; notes: string[] }
export async function priceCheckTemplate(pid: string): Promise<Blob> {
  const response = await fetch(`${BASE}/api/projects/${pid}/price-checks/template.csv`);
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Price-check template failed"));
  return response.blob();
}
async function requestChecks(pid: string, req: CheckUpload | CheckExport): Promise<Response> {
  const body = new FormData(); body.append("labels", req.labels); body.append("checkouts", req.checkouts);
  body.append("store_ref", req.store_ref); body.append("audit_date", req.audit_date);
  const csv = "source_sha256" in req;
  if (csv) body.append("source_sha256", req.source_sha256);
  const response = await fetch(`${BASE}/api/projects/${pid}/price-checks/${csv ? "export.csv" : "preview"}`, { method: "POST", body });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Price-check review failed"));
  return response;
}
export async function previewPriceChecks(pid: string, req: CheckUpload): Promise<PriceCheckReport> { return (await requestChecks(pid, req)).json() as Promise<PriceCheckReport>; }
export async function exportPriceChecks(pid: string, req: CheckExport): Promise<Blob> { return (await requestChecks(pid, req)).blob(); }
