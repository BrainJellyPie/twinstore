import { BASE } from "./client";
import { apiErrorMessage } from "./errors";

export type SensitivityScope = "staff" | "shift" | "block";
export interface PilotSensitivityReport {
  method: "fixed-block-deletion-v1"; pilot_id: string; revision: number; finalized_at: string;
  target_sku: string; planned_encounters: number; blocks: number; difference: number;
  groups: { scope: SensitivityScope; staff_id: string; shift_id: string; removed_blocks: number;
    removed_encounters: number; removed_weight: number; remaining_encounters: number;
    difference: number | null; change: number | null; opposite_sign: boolean | null }[];
  summaries: { scope: SensitivityScope; groups: number; estimable: number; minimum: number | null;
    maximum: number | null; max_absolute_change: number | null; opposite_sign_count: number }[];
  notes: string[];
}

export const sensitivityKey = (pid: string, id: string, revision: number) => ["projects", pid, "staff-pilots", id, "sensitivity", revision] as const;
export const sensitivityCsvUrl = (pid: string, id: string, revision: number) => `${BASE}/api/projects/${pid}/staff-pilots/${id}/sensitivity.csv?revision=${revision}`;
export async function getPilotSensitivity(pid: string, id: string, revision: number, signal?: AbortSignal): Promise<PilotSensitivityReport> {
  const response = await fetch(`${BASE}/api/projects/${pid}/staff-pilots/${id}/sensitivity?revision=${revision}`, { signal });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Sensitivity checks could not be loaded"));
  return response.json() as Promise<PilotSensitivityReport>;
}
