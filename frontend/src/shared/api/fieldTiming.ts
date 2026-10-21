import { BASE } from "./client";
import { apiErrorMessage } from "./errors";

export interface TimingArm { arm: "A" | "B"; planned: number; timed: number; mean_seconds: number | null; max_seconds: number | null }
export interface PilotTimingReport {
  method: "assigned-encounter-time-v1"; pilot_id: string; revision: number; source_sha256: string; source_rows: number;
  complete: boolean; planned: number; timed: number; a: TimingArm; b: TimingArm; difference_seconds: number | null;
  blocks: { staff_id: string; shift_id: string; planned: number; timed: number }[];
  rows: { assignment_id: string; staff_id: string; shift_id: string; arm: "A" | "B"; staff_seconds: number | null }[];
  notes: string[];
}
export interface TimingUpload { file: File; revision: number }

export async function timingTemplate(pid: string, id: string, revision: number): Promise<Blob> {
  const response = await fetch(`${BASE}/api/projects/${pid}/staff-pilots/${id}/timing/template.csv?revision=${revision}`);
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Staff time template failed"));
  return response.blob();
}
async function requestTiming(pid: string, id: string, request: TimingUpload, csv: boolean): Promise<Response> {
  const body = new FormData(); body.append("file", request.file); body.append("revision", String(request.revision));
  const response = await fetch(`${BASE}/api/projects/${pid}/staff-pilots/${id}/timing/${csv ? "export.csv" : "preview"}`, { method: "POST", body });
  if (!response.ok) throw new Error(apiErrorMessage(await response.text(), "Staff time review failed"));
  return response;
}
export async function previewTiming(pid: string, id: string, request: TimingUpload): Promise<PilotTimingReport> {
  return (await requestTiming(pid, id, request, false)).json() as Promise<PilotTimingReport>;
}
export async function exportTiming(pid: string, id: string, request: TimingUpload): Promise<Blob> {
  return (await requestTiming(pid, id, request, true)).blob();
}
