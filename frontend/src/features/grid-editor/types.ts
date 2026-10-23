// Grid-editor types. Backend wire-shape mirrors use snake_case; client-only fields use camelCase.

import type {
  Store,
  Rack,
  Slot,
  Face,
  Position,
  Shape,
  ClearedSlotInfo,
  BlockedFaceDetail,
  BlockReason,
  Issue,
  Readiness,
} from "@/shared/types/domain";

import type { SetupSummary } from "@/shared/api/client";

export type {
  Store,
  Rack,
  Slot,
  Face,
  Position,
  Shape,
  ClearedSlotInfo,
  BlockedFaceDetail,
  BlockReason,
  Issue,
  Readiness,
  SetupSummary,
};

// design_variant is always populated here — the UI normalizes the default to "a".
export interface EditorRack extends Omit<Rack, "design_variant"> {
  design_variant: "a" | "b" | "c";
}

// Lightweight cell↔rack view for picking/highlight, keyed by block index.
export interface GridCellRack {
  rack_id: string;
  block: number;
  // Absolute grid coordinate of the cell (rack.position + rotation applied).
  cell: Position;
}

// Nested setup payload for PUT /api/projects/{pid}/setups/{sid}.
export interface SetupUpdatePayload {
  name?: string;
  store?: Store;
  memo?: string;
  discard_products?: boolean;
}

// GET /api/projects/{pid}/setups/{sid} response — SetupDetail with blocked_faces.
export interface SetupDetailWithBlocked extends SetupSummary {
  store: Store | null;
  blocked_faces: BlockedFaceDetail[];
}

export interface SaveSetupSuccess {
  ok: true;
  setup: SetupSummary;
  cleared: ClearedSlotInfo[];
  blocked_faces: BlockedFaceDetail[];
  issues: Issue[];
}

// PUT 4xx/5xx response — extracted from FastAPI's `{detail: {...}}` body.
export interface SaveSetupFailure {
  ok: false;
  status: number;
  code: string;
  reason: string;
  message: string;
  details: Record<string, unknown>;
}

export type SaveSetupResult = SaveSetupSuccess | SaveSetupFailure;

// Top-level PUT body — the backend requires the nested form.
export interface SaveSetupRequest {
  setup: SetupUpdatePayload;
}

export interface LoadSetupSuccess {
  ok: true;
  detail: SetupDetailWithBlocked;
}

export interface LoadSetupFailure {
  ok: false;
  status: number;
  code: string;
  reason: string;
  message: string;
  details: Record<string, unknown>;
}

export type LoadSetupResult = LoadSetupSuccess | LoadSetupFailure;
