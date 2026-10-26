import { BASE } from "./client";
import { apiErrorMessage, apiFetch } from "./errors";

export interface PilotEconomicsRequest {
  revision: number; currency: string; contribution_per_conversion_minor: number; labor_per_hour_minor: number;
  seconds_per_encounter_a: number; seconds_per_encounter_b: number; eligible_encounters_per_day: number;
}
export interface ConditionalContribution { estimate_minor: number; low_minor: number; high_minor: number }
export interface PilotEconomicsReport {
  method: "fixed-pilot-cost-scenario-v1"; pilot_id: string; finalized_at: string; target_sku: string;
  planned_encounters: number; assumptions: PilotEconomicsRequest; conversion_difference: number;
  conversion_ci_low: number; conversion_ci_high: number; incremental_labor_minor: number;
  break_even_difference: number | null; per_encounter: ConditionalContribution; per_day: ConditionalContribution; notes: string[];
}

async function requestEconomics(pid: string, id: string, request: PilotEconomicsRequest, csv: boolean): Promise<Response> {
  const response = await apiFetch(`${BASE}/api/projects/${pid}/staff-pilots/${id}/economics${csv ? ".csv" : ""}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Cost scenario request failed"));
  return response;
}
export async function previewPilotEconomics(pid: string, id: string, request: PilotEconomicsRequest): Promise<PilotEconomicsReport> {
  return (await requestEconomics(pid, id, request, false)).json() as Promise<PilotEconomicsReport>;
}
export async function exportPilotEconomics(pid: string, id: string, request: PilotEconomicsRequest): Promise<Blob> {
  return (await requestEconomics(pid, id, request, true)).blob();
}
