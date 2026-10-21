import { BASE } from "./client";
import { apiErrorMessage } from "./errors";
import type { VariantChange } from "./marketing";

export type FactorialMetric = "spend" | "units" | "bought";
export interface FactorialSource {
  available: boolean; reason: string; source_sha256: string;
  price_arms: string[]; sign_arms: string[]; combined_arms: string[];
}
export interface FactorialRequest {
  source_sha256: string; price_arm: string; sign_arm: string; combined_arm: string; metric: FactorialMetric;
}
export interface FactorialReport {
  method: string; experiment_id: string; request: FactorialRequest; currency: string; engine: string; model: string;
  simulation_seed: number; requested_panel: number; sampled_panel: number; complete_panel: number;
  intervals_available: boolean; bootstrap_resamples: number; bootstrap_seed: number; family_size: number;
  cells: { cell: string; arm: string; available: number; mean: number | null; changes: VariantChange[] }[];
  contrasts: { name: string; formula: string; estimate: number | null; ci_low: number | null; ci_high: number | null }[];
  rows: { persona_id: string; complete: boolean; values: (number | null)[] }[]; notes: string[];
}
const root = (pid: string, eid: string) => `${BASE}/api/projects/${pid}/experiments/${eid}/factorial`;
export async function getFactorialSource(pid: string, eid: string, signal?: AbortSignal): Promise<FactorialSource> {
  const response = await fetch(`${root(pid, eid)}/source`, { signal });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Could not load paired source"));
  return response.json() as Promise<FactorialSource>;
}
async function request(pid: string, eid: string, req: FactorialRequest, suffix: string): Promise<Response> {
  const response = await fetch(`${root(pid, eid)}/${suffix}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Factorial review failed"));
  return response;
}
export async function previewFactorial(pid: string, eid: string, req: FactorialRequest): Promise<FactorialReport> {
  return (await request(pid, eid, req, "preview")).json() as Promise<FactorialReport>;
}
export async function exportFactorial(pid: string, eid: string, req: FactorialRequest): Promise<Blob> {
  return (await request(pid, eid, req, "export.csv")).blob();
}
