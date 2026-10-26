import { BASE } from "./client";
import { apiErrorMessage, apiFetch } from "./errors";

export type DataStage = "not_collected" | "collected_unseen" | "results_seen";
export interface ProtocolPlan {
  title: string; evidence_type: "synthetic" | "observed"; question: string; population: string; design: string;
  primary_outcome: string; analysis_unit: string; planned_sample_size: number; exclusions_and_missing: string;
  stopping_rule: string; analysis_plan: string;
}
export interface CreateProtocol { request_id: string; plan: ProtocolPlan; data_stage: DataStage }
export interface AmendProtocol { expected_head: string; plan: ProtocolPlan; data_stage: DataStage; reason: string }
export interface ProtocolRevision {
  revision: number; recorded_at: string; reason: string; data_stage: DataStage; plan: ProtocolPlan;
  previous_sha256: string | null; sha256: string;
}
export interface ProtocolView {
  ledger: { format_version: "protocol-ledger-v1"; project_id: string; protocol_id: string; revisions: ProtocolRevision[] };
  reviews: { revision: number; changes: { field: string; before: string | number | null; after: string | number }[] }[];
  head_sha256: string; changed_from_original: string[]; planned_sample_delta: number | null; revisions_with_results_seen: number; notes: string[];
}
export interface ProtocolListing {
  protocols: { protocol_id: string; title: string; revision: number; data_stage: DataStage; evidence_type: "synthetic" | "observed"; updated_at: string }[];
  unavailable_ids: string[];
}
const root = (pid: string) => `${BASE}/api/projects/${pid}/protocols`;
async function request(url: string, init?: RequestInit): Promise<Response> {
  const response = await apiFetch(url, init);
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Protocol request failed"));
  return response;
}
export async function listProtocols(pid: string, signal?: AbortSignal): Promise<ProtocolListing> {
  return (await request(root(pid), { signal })).json() as Promise<ProtocolListing>;
}
export async function getProtocol(pid: string, id: string, signal?: AbortSignal): Promise<ProtocolView> {
  return (await request(`${root(pid)}/${id}`, { signal })).json() as Promise<ProtocolView>;
}
export async function createProtocol(pid: string, req: CreateProtocol): Promise<ProtocolView> {
  return (await request(root(pid), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) })).json() as Promise<ProtocolView>;
}
export async function amendProtocol(pid: string, id: string, req: AmendProtocol): Promise<ProtocolView> {
  return (await request(`${root(pid)}/${id}/amendments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) })).json() as Promise<ProtocolView>;
}
export async function exportProtocol(pid: string, id: string, head: string, format: "json" | "csv"): Promise<Blob> {
  return (await request(`${root(pid)}/${id}/${format === "json" ? "export.json" : "changes.csv"}?head=${encodeURIComponent(head)}`)).blob();
}
