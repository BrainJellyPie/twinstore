import { BASE } from "./client";
import { apiErrorMessage } from "./errors";
import type { PitchVariant } from "./marketing";

export interface PilotRequest {
  name: string; eligibility: string; outcome_window: string; seed: number;
  blocks: { staff_id: string; shift_id: string; encounters: number }[];
  planning?: PilotPlanningAssumptions | null;
}
export interface PilotPlanningAssumptions {
  minimum_effect: number; target_power: number; eligible_per_day: number; available_days: number;
}
export interface PilotPlanningResult {
  method: "hoeffding-fixed-v1"; assumptions: PilotPlanningAssumptions; block_counts: number[];
  planned_encounters: number; required_encounters: number; planned_power_lower_bound: number;
  planned_ci_half_width: number; planned_days: number; required_days: number;
  suggested_block_counts: number[] | null; notes: string[];
}
export interface PilotAssignment {
  assignment_id: string; staff_id: string; shift_id: string; sequence: number; arm: "A" | "B";
  enrolled: boolean | null; delivered: boolean | null; purchased: boolean | null;
}
export interface FieldPilot {
  pilot_id: string; pitch_id: string; created_at: string; updated_at: string; finalized_at: string; revision: number;
  design: PilotRequest; product: { sku: string; name: string; price: number; currency: string; promo: string };
  variants: [PitchVariant, PitchVariant]; context: string; product_facts: string; assignments: PilotAssignment[];
  planning?: PilotPlanningResult | null;
}
export interface PilotArm {
  arm: "A" | "B"; planned: number; enrolled: number; unused: number; unrecorded: number;
  observed: number; purchases: number; missing_outcomes: number; not_delivered: number; delivery_unknown: number;
  observed_rate: number | null; missing_bound_low: number | null; missing_bound_high: number | null;
}
export interface PilotAnalysis {
  a: PilotArm; b: PilotArm;
  blocks: { staff_id: string; shift_id: string; a: PilotArm; b: PilotArm; observed_diff: number | null }[];
  target_completed: boolean; can_finalize: boolean; inference_ready: boolean;
  difference: number | null; ci_low: number | null; ci_high: number | null; interpretation: string; notes: string[];
}
export interface PilotView { pilot: FieldPilot; analysis: PilotAnalysis }
export interface PilotSummary {
  pilot_id: string; pitch_id: string; name: string; created_at: string; finalized_at: string; planned: number; enrolled: number;
}
const root = (pid: string) => `${BASE}/api/projects/${pid}/staff-pilots`;
async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(apiErrorMessage(await response.text(), `Field pilot request failed (${response.status}). Check the entered values.`));
  }
  return response.json() as Promise<T>;
}
export const pilotKeys = {
  list: (pid: string) => ["projects", pid, "staff-pilots"] as const,
  detail: (pid: string, id: string) => ["projects", pid, "staff-pilots", id] as const,
};
export const listPilots = (pid: string, signal?: AbortSignal) => json<PilotSummary[]>(root(pid), { signal });
export const getPilot = (pid: string, id: string, signal?: AbortSignal) => json<PilotView>(`${root(pid)}/${id}`, { signal });
export const previewPilotPlan = (pid: string, assumptions: PilotPlanningAssumptions, blockCounts: number[], signal?: AbortSignal) => json<PilotPlanningResult>(`${root(pid)}/plan`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ assumptions, block_counts: blockCounts }), signal,
});
export const createPilot = (pid: string, pitch: string, request: PilotRequest) => json<PilotView>(`${BASE}/api/projects/${pid}/staff-pitches/${pitch}/pilots`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
});
export const pilotCsvUrl = (pid: string, id: string) => `${root(pid)}/${id}/observations.csv`;
export async function importPilot(pid: string, id: string, file: File, revision: number): Promise<PilotView> {
  const form = new FormData(); form.append("file", file); form.append("revision", String(revision));
  return json<PilotView>(`${root(pid)}/${id}/observations`, { method: "PUT", body: form });
}
export const closePilot = (pid: string, id: string, revision: number) => json<PilotView>(`${root(pid)}/${id}/close`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision }),
});
