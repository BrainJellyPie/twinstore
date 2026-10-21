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
  history_start_revision?: number | null;
  import_history?: ObservationImportRecord[];
}
export interface ObservationChange {
  assignment_id: string; staff_id: string; shift_id: string; sequence: number; arm: "A" | "B";
  field: "enrolled" | "delivered" | "purchased"; before: boolean | null; after: boolean | null;
}
export interface ObservationDiff {
  changed_assignments: number; changed_fields: number; new_values: number; corrected_values: number;
  cleared_values: number; removed_enrollments: number; purchase_reversals: number;
}
export interface ObservationPreview {
  pilot_id: string; revision: number; review_token: string; summary: ObservationDiff; changes: ObservationChange[];
}
export interface ObservationImportRecord {
  revision: number; imported_at: string; reason: string; source_sha256: string; summary: ObservationDiff;
}
export interface ObservationImportAudit { record: ObservationImportRecord; changes: ObservationChange[] }
export type PosMatchStatus = "proposed_purchase" | "already_recorded" | "conflicting_purchase" | "not_enrolled" | "no_target_evidence" | "unknown_assignment" | "unlinked";
export interface PilotPosPreview {
  pilot_id: string; revision: number; target_sku: string; outcome_window: string; source_sha256: string;
  source_rows: number; transactions: number; linked_assignments: number; enrolled_without_evidence: number; proposed_purchases: number;
  matches: { assignment_id: string; transaction_ids: string[]; target_units: number; status: PosMatchStatus;
    staff_id: string | null; shift_id: string | null; sequence: number | null }[];
  candidate_csv: string; notes: string[];
}
export type CollectionIssue = "purchase_unknown" | "delivery_unknown" | "enrollment_gap" | "unused_before_enrolled";
export interface CollectionCounts {
  planned: number; enrolled: number; unused: number; unrecorded: number; complete_enrolled: number;
  missing_purchase: number; missing_delivery: number; known_delivery: number; not_delivered: number;
  purchase_missing_rate: number | null; non_delivery_rate: number | null;
}
export interface CollectionBlock {
  staff_id: string; shift_id: string; counts: CollectionCounts; a: CollectionCounts; b: CollectionCounts;
  last_recorded_sequence: number | null; recording_gaps: number; unused_before_enrolled: number;
  unrecorded_tail: number; purchase_missing_gap: number | null;
}
export interface PilotCollectionReport {
  pilot_id: string; name: string; revision: number; updated_at: string; finalized_at: string; outcome_window: string;
  counts: CollectionCounts; recording_gaps: number; unused_before_enrolled: number; unrecorded_tail: number;
  can_finalize: boolean; target_completed: boolean; blocks: CollectionBlock[];
  tasks: { assignment_id: string; staff_id: string; shift_id: string; sequence: number; arm: "A" | "B"; issues: CollectionIssue[] }[];
  guidance: { issue: CollectionIssue; title: string; action: string }[]; notes: string[];
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
  collection: (pid: string, id: string) => ["projects", pid, "staff-pilots", id, "collection"] as const,
};
export const listPilots = (pid: string, signal?: AbortSignal) => json<PilotSummary[]>(root(pid), { signal });
export const getPilot = (pid: string, id: string, signal?: AbortSignal) => json<PilotView>(`${root(pid)}/${id}`, { signal });
export const getPilotCollection = (pid: string, id: string, signal?: AbortSignal) => json<PilotCollectionReport>(`${root(pid)}/${id}/collection-checks`, { signal });
export const pilotFollowupCsvUrl = (pid: string, id: string) => `${root(pid)}/${id}/follow-up.csv`;
export const previewPilotPlan = (pid: string, assumptions: PilotPlanningAssumptions, blockCounts: number[], signal?: AbortSignal) => json<PilotPlanningResult>(`${root(pid)}/plan`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ assumptions, block_counts: blockCounts }), signal,
});
export const createPilot = (pid: string, pitch: string, request: PilotRequest) => json<PilotView>(`${BASE}/api/projects/${pid}/staff-pitches/${pitch}/pilots`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
});
export const pilotCsvUrl = (pid: string, id: string) => `${root(pid)}/${id}/observations.csv`;
export async function previewPilotImport(pid: string, id: string, file: File, revision: number): Promise<ObservationPreview> {
  const form = new FormData(); form.append("file", file); form.append("revision", String(revision));
  return json<ObservationPreview>(`${root(pid)}/${id}/observations/preview`, { method: "POST", body: form });
}
export async function previewPilotPos(pid: string, id: string, file: File, revision: number): Promise<PilotPosPreview> {
  const form = new FormData(); form.append("file", file); form.append("revision", String(revision));
  return json<PilotPosPreview>(`${root(pid)}/${id}/pos/preview`, { method: "POST", body: form });
}
export async function importPilot(pid: string, id: string, file: File, revision: number, reviewToken: string, reason: string): Promise<PilotView> {
  const form = new FormData(); form.append("file", file); form.append("revision", String(revision));
  form.append("review_token", reviewToken); form.append("reason", reason);
  return json<PilotView>(`${root(pid)}/${id}/observations`, { method: "PUT", body: form });
}
export const getPilotImport = (pid: string, id: string, revision: number, signal?: AbortSignal) => json<ObservationImportAudit>(`${root(pid)}/${id}/imports/${revision}`, { signal });
export const pilotHistoryCsvUrl = (pid: string, id: string) => `${root(pid)}/${id}/imports.csv`;
export const closePilot = (pid: string, id: string, revision: number) => json<PilotView>(`${root(pid)}/${id}/close`, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision }),
});
