import { BASE } from "./client";
import { apiErrorMessage } from "./errors";
import type { Store } from "@/shared/types/domain";
export interface CaptureBatchRequest {
  capture_ids: string[];
  setup_id: string;
}
export interface CaptureBatchSave extends CaptureBatchRequest {
  source_sha256: string;
  request_id: string;
  allow_reduced_facings: boolean;
}
export interface CaptureBatchPreview {
  source_sha256: string;
  store: Store;
  rack_ids: string[];
  placed_items: number;
  placed_facings: number;
  requested_facings: number;
  reduced_facings: number;
  dropped: string[];
  notes: string[];
  estimated_prices: number;
  unrecognized_items: number;
}
export interface CaptureBatchSaved {
  setup_id: string;
  rack_ids: string[];
  placed_items: number;
  placed_facings: number;
  notes: string[];
}
async function request<T>(
  pid: string,
  action: string,
  body: CaptureBatchRequest | CaptureBatchSave,
): Promise<T> {
  const response = await fetch(
    `${BASE}/api/projects/${pid}/captures/${action}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok)
    throw new Error(
      apiErrorMessage(await response.text(), "Could not combine shelves"),
    );
  return response.json() as Promise<T>;
}
export const previewCaptureBatch = (pid: string, req: CaptureBatchRequest) =>
  request<CaptureBatchPreview>(pid, "batch-preview", req);
export const saveCaptureBatch = (pid: string, req: CaptureBatchSave) =>
  request<CaptureBatchSaved>(pid, "batch-save", req);
