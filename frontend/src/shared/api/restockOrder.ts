import { BASE } from "./client";
import { apiErrorMessage } from "./errors";

export interface RestockOrderItem {
  sku: string; required_units: number; stockroom_units: number; pack_size: number;
  pack_cost_minor: number; max_packs: number; priority: number;
}
export interface RestockOrderRequest {
  currency: string; budget_minor: number; delivery_fee_minor: number; items: RestockOrderItem[];
}
export interface RestockOrderPlan {
  audit_id: string; capture_id: string; setup_id: string; rack_id: string; face: string; currency: string;
  budget_minor: number; delivery_fee_minor: number; delivery_charged_minor: number; goods_cost_minor: number;
  total_cost_minor: number; remaining_budget_minor: number; omitted_skus: string[]; unidentified_findings: number;
  actions: { item: RestockOrderItem; name: string; levels: number[]; stockroom_used: number; packs_needed: number;
    packs_ordered: number; units_ordered: number; surplus_units: number; unfilled_units: number; cost_minor: number;
    supplier_limited: boolean; budget_limited: boolean }[];
  notes: string[];
}
async function requestOrder(pid: string, cid: string, jid: string, request: RestockOrderRequest, csv: boolean): Promise<Response> {
  const response = await fetch(`${BASE}/api/projects/${pid}/captures/${cid}/lab/jobs/${jid}/restock-order${csv ? ".csv" : ""}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Restocking plan request failed"));
  return response;
}
export async function previewRestockOrder(pid: string, cid: string, jid: string, request: RestockOrderRequest): Promise<RestockOrderPlan> {
  return (await requestOrder(pid, cid, jid, request, false)).json() as Promise<RestockOrderPlan>;
}
export async function exportRestockOrder(pid: string, cid: string, jid: string, request: RestockOrderRequest): Promise<Blob> {
  return (await requestOrder(pid, cid, jid, request, true)).blob();
}
