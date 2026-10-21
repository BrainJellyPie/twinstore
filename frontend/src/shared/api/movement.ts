import { BASE } from "./client";

export interface MovementSummary {
  tracks: number;
  samples: number;
  duplicate_samples: number;
  single_point_tracks: number;
  excluded_gaps: number;
  excluded_seconds: number;
  observed_seconds: number;
  visitors: number[][];
  occupancy_seconds: number[][];
}

export interface MovementReport {
  grid_size: [number, number];
  observed: MovementSummary;
  simulated: MovementSummary;
  visitation_similarity: number | null;
  occupancy_similarity: number | null;
  largest_gaps: { x: number; y: number; observed_visit_rate: number; simulated_visit_rate: number; difference: number }[];
  max_gap_seconds: number;
  notes: string[];
  created_at: string;
}

export async function getMovementReport(projectId: string, runId: string): Promise<MovementReport | null> {
  const response = await fetch(`${BASE}/api/projects/${projectId}/runs/${runId}/movement`);
  if (!response.ok) throw new Error("Could not load movement comparison.");
  return response.json() as Promise<MovementReport | null>;
}

export async function uploadMovement(projectId: string, runId: string, file: File, maxGap: number): Promise<MovementReport> {
  const form = new FormData();
  form.append("file", file);
  form.append("max_gap_seconds", String(maxGap));
  const response = await fetch(`${BASE}/api/projects/${projectId}/runs/${runId}/movement`, { method: "POST", body: form });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    throw new Error(typeof detail === "string" ? detail : `Track import failed (${response.status}).`);
  }
  return response.json() as Promise<MovementReport>;
}
