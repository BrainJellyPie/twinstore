// Response types mirror backend schemas.py 1:1 — keep in sync.

import { ApiError, apiErrorMessage } from "./errors";

import type {
  Face,
  Store,
  StoreDesign,
  InteriorColors,
  Persona,
  DaySchedule,
  CustomerResult,
  Readiness,
  GenerationStatus,
  GenerationListItem,
  GenerationChoice,
  SlotRow,
  BlockedFaceInfo,
  BlockedFaceDetail,
  ClearedSlotInfo,
  Issue,
} from "@/shared/types/domain";

export type { BlockedFaceDetail, GenerationChoice, GenerationConfirm, Issue, WriteChoice } from "@/shared/types/domain";

// Dev server (vite on :5173) talks to the API on :8000; a production build is served by the API
// server itself (one-click mode), so it uses the same origin. VITE_API_URL overrides both.
export const BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(apiErrorMessage(body, `${res.status} ${res.statusText}`), res.status);
  }
  return res.json() as Promise<T>;
}

/** The active layout as rectangles: [x, y, width, depth, fixture type] in grid cells. */
export interface LayoutFootprint {
  grid: [number, number];
  racks: [number, number, number, number, "shelf" | "fridge" | "counter" | "table"][];
}

export interface ProjectListItem {
  project_id: string;
  name: string;
  description: string;
  store_type: string;
  grid_size: [number, number] | null;
  weekly_schedule: DaySchedule[];
  created_at: string;
  updated_at: string;
  status: string;
  footprint?: LayoutFootprint | null;
}

export interface ProjectMetadata {
  project_id: string;
  name: string;
  description: string;
  store_type: string;
  currency?: string | null;
  grid_size: [number, number] | null;
  weekly_schedule: DaySchedule[];
  address: string;
  customer_profile: string;
  supplemental_summary: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail {
  projectId: string;
  metadata: ProjectMetadata;
  personas: Persona[];
  state: { activeSetupId: string; runningSetups: string[] };
  setups: SetupSummary[];
  personasLocked: boolean;
}

export function getHealth(signal?: AbortSignal): Promise<{ status: string }> {
  return fetchJson("/api/health", { signal });
}

export function getProjects(signal?: AbortSignal): Promise<ProjectListItem[]> {
  return fetchJson("/api/projects", { signal });
}

export function getProject(projectId: string, signal?: AbortSignal): Promise<ProjectDetail> {
  return fetchJson(`/api/projects/${projectId}`, { signal });
}

export function deleteProject(projectId: string, signal?: AbortSignal): Promise<{ status: string }> {
  return fetchJson(`/api/projects/${projectId}`, { method: "DELETE", signal });
}

export function updateProjectMetadata(
  projectId: string,
  patch: { name?: string; description?: string; address?: string; customer_profile?: string; supplemental_summary?: string },
  signal?: AbortSignal,
): Promise<{ status: "saved" }> {
  return fetchJson(`/api/projects/${projectId}/metadata`, {
    method: "PUT",
    body: JSON.stringify(patch),
    signal,
  });
}

export interface SetupSummaryShort {
  id: string;
  name: string;
  status: "draft" | "running" | "locked";
  parentId: string | null;
  building?: BuildingFloorInfo | null;
  generation?: GenerateLayoutRequest | null;
  runId: string | null;
  memo: string;
  readiness: Readiness | null;
  created_at: string;
  updated_at: string;
}

export interface CreateStoreMeta {
  layout?: GenerateLayoutRequest | null;
  starter_selection?: "automatic" | "format";
  name: string;
  description: string;
  address: string;
  store_type: string;
  customer_profile: string;
  weekly_schedule: ReadonlyArray<{
    day: number;
    is_open: boolean;
    open_hour: number;
    close_hour: number;
  }>;
}

export interface CreateStoreResponse {
  metadata: ProjectMetadata;
  setup: SetupSummaryShort;
  personaGenId: string;
}

export async function createStore(
  meta: CreateStoreMeta,
  supplemental: File | null,
): Promise<CreateStoreResponse> {
  const fd = new FormData();
  fd.append("meta", JSON.stringify(meta));
  if (supplemental) fd.append("supplemental", supplemental);

  // Direct base URL — Vite has no /api proxy, so a relative path would hit the dev server.
  const res = await fetch(`${BASE}/api/projects/create-store`, { method: "POST", body: fd });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(apiErrorMessage(body, `Failed to create store (HTTP ${res.status})`));
  }
  return res.json() as Promise<CreateStoreResponse>;
}

export interface BuildingFloorInfo {
  id: string; name: string; level: number; label: string; floor_count: number;
}

export interface SetupSummary {
  id: string;
  name: string;
  status: string;
  parentId: string | null;
  building?: BuildingFloorInfo | null;
  generation?: GenerateLayoutRequest | null;
  runId: string | null;
  memo: string;
  readiness: Readiness | null;
  created_at: string;
  updated_at: string;
}

export interface SetupDetail extends SetupSummary {
  store: Store | null;
  blocked_faces?: BlockedFaceDetail[];
}

export function getSetups(projectId: string, signal?: AbortSignal): Promise<SetupSummary[]> {
  return fetchJson(`/api/projects/${projectId}/setups`, { signal });
}

export function getSetup(
  projectId: string,
  setupId: string,
  signal?: AbortSignal,
): Promise<SetupDetail> {
  return fetchJson(`/api/projects/${projectId}/setups/${setupId}`, { signal });
}

export interface SaveSetupResponse {
  setup: SetupSummary;
  cleared: ClearedSlotInfo[];
  blocked_faces: BlockedFaceDetail[];
  issues: Issue[];
}

export function saveSetup(
  projectId: string,
  setupId: string,
  data: { store?: Store; name?: string; memo?: string },
  signal?: AbortSignal,
): Promise<SaveSetupResponse> {
  // backend expects nested { setup: ... } body
  return fetchJson(`/api/projects/${projectId}/setups/${setupId}`, {
    method: "PUT",
    body: JSON.stringify({ setup: data }),
    signal,
  });
}

export function createSetup(
  projectId: string,
  body: {
    mode: "racks_and_items" | "racks" | "empty";
    source_setup_id: string | null;
    name?: string;
    memo?: string;
  },
  signal?: AbortSignal,
): Promise<SetupSummaryShort> {
  return fetchJson(`/api/projects/${projectId}/setups`, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}

export function deleteSetup(
  projectId: string,
  setupId: string,
  signal?: AbortSignal,
): Promise<{ status: string; deleted: string[] }> {
  return fetchJson(`/api/projects/${projectId}/setups/${setupId}`, {
    method: "DELETE",
    signal,
  });
}

export interface ReplaceSlotsResponse {
  count: number;
  cleared: ClearedSlotInfo[];
}

export function replaceSlots(
  projectId: string,
  setupId: string,
  slots: SlotRow[],
  signal?: AbortSignal,
): Promise<ReplaceSlotsResponse> {
  return fetchJson(`/api/projects/${projectId}/setups/${setupId}/slots`, {
    method: "PUT",
    body: JSON.stringify({ slots }),
    signal,
  });
}

export function getSetupGenerations(
  projectId: string,
  setupId: string,
  opts?: { active_only?: boolean },
  signal?: AbortSignal,
): Promise<GenerationListItem[]> {
  const query = opts?.active_only ? "?active_only=true" : "";
  return fetchJson(
    `/api/projects/${projectId}/setups/${setupId}/generations${query}`,
    { signal },
  );
}

export function getGenerationStatus(
  projectId: string,
  setupId: string,
  genId: string,
  signal?: AbortSignal,
): Promise<GenerationStatus> {
  return fetchJson(
    `/api/projects/${projectId}/setups/${setupId}/generations/${genId}/status`,
    { signal },
  );
}

/** Answers a generation waiting for the user's choice (progress.confirm); 409 when it is not waiting. */
export function confirmGeneration(
  projectId: string,
  setupId: string,
  genId: string,
  choice: GenerationChoice,
  signal?: AbortSignal,
): Promise<GenerationStatus> {
  return fetchJson(
    `/api/projects/${projectId}/setups/${setupId}/generations/${genId}/confirm`,
    { method: "POST", body: JSON.stringify({ choice }), signal },
  );
}

export function regeneratePersona(
  projectId: string,
  setupId: string,
  signal?: AbortSignal,
): Promise<{ gen_id: string }> {
  return fetchJson(
    `/api/projects/${projectId}/setups/${setupId}/regenerate-persona`,
    { method: "POST", signal },
  );
}

export function getBlockedFaces(store: Store, signal?: AbortSignal): Promise<BlockedFaceInfo[]> {
  return fetchJson(`/api/util/blocked-faces`, {
    method: "POST",
    body: JSON.stringify({ store }),
    signal,
  });
}

export function savePersonas(
  projectId: string,
  personas: Persona[],
  signal?: AbortSignal,
): Promise<{ status: string }> {
  return fetchJson(`/api/projects/${projectId}/personas`, {
    method: "PUT",
    body: JSON.stringify({ personas }),
    signal,
  });
}

export interface RunListItem {
  run_id: string;
  project_id: string;
  setup_id: string;
  status: string;
  // Failed runs: the message, then a newline and the Python traceback.
  error?: string;
  created_at: string;
  total_customers: number;
  completed_customers?: number;
  failed_customers?: number;
  preview?: boolean;
  engine_type?: string;
  seed?: number;
  replicate?: number;
  started_at?: string;
  finished_at?: string;
  scenario?: string;
  summary?: RunSummary;
  manifest?: RunManifest;
}

export function getRuns(
  projectId: string,
  setupId?: string,
  signal?: AbortSignal,
): Promise<RunListItem[]> {
  const query = setupId ? `?setup_id=${setupId}` : "";
  return fetchJson(`/api/projects/${projectId}/runs${query}`, { signal });
}

export type EngineType = "pattern_intent_impulse" | "rule_based" | "vlm_glance";

// Per-run overrides; every field is optional and falls back to the server config.
export interface RunOptions {
  engine_type?: EngineType;
  seed?: number;
  replicate?: number;
  exposure_model?: "visibility" | "adjacency";
  route_ordering?: "planned" | "nearest";
  max_customers?: number;
  // Preview runs don't lock the layout and are allowed on finalized layouts.
  preview?: boolean;
  // Model reference for the engine, e.g. "anthropic:claude-haiku-5-5".
  model?: string;
  ensemble?: EnsembleConfig;
  // Situation: a preset id or a full scenario.
  scenario_id?: string;
  scenario?: Scenario;
  // Draw visitors from the project's neighborhood model.
  use_town?: boolean;
  town_scale?: number;
  // Vision shoppers: who decides what the shopper came for — the VLM at the door, or the rule planner.
  plan_policy?: "vlm" | "rule" | null;
  // Vision shoppers: the rendered shelf chart, or the 3D store's photo of each face above it.
  shelf_view?: ShelfViewMode | null;
  // Shoppers share the store: finite stock, restocking, a line at the tills. Omitted: the layout's saved settings.
  operations?: OperationsConfig;
  // false: each shopper has the store alone, whatever the layout saved.
  shared_store?: boolean;
}

/** How the shared store runs (backend domain/operations.py). Every field falls back to the server default. */
export interface OperationsConfig {
  stock_per_facing?: number;
  stock_overrides?: Record<string, number>;
  restock_every_min?: number | null;
  substitute_share?: number;
  open_counters?: number | null;
  // Tills staffed in single hours ("18" → 3); 0 closes the tills for that hour.
  till_schedule?: Record<string, number>;
  // Units kept behind the shelves per product (null: endless), per-product backrooms, and a delivery each morning.
  backroom_per_product?: number | null;
  backroom_overrides?: Record<string, number>;
  daily_delivery?: boolean;
  // With this many shoppers at one shelf (null: never), an unplanned pick there is skipped with crowd_skip chance.
  crowd_limit?: number | null;
  crowd_skip?: number;
  // One crew for the tills and the shelves (null: tills staffed on their own, refills in rounds), by hour too; a
  // shelf is refilled once down to refill_at of full, taking refill_face_sec plus refill_unit_sec per unit.
  crew?: number | null;
  crew_schedule?: Record<string, number>;
  refill_at?: number;
  refill_face_sec?: number;
  refill_unit_sec?: number;
  checkout_base_sec?: number;
  checkout_item_sec?: number;
  patience_sec?: number;
  patience_sd?: number;
  target_wait_sec?: number;
}

export interface StockoutStats {
  sku: string;
  name: string;
  rack_id: string;
  rack_name: string;
  stock: number;
  sold_units: number;
  lost_units: number;
  lost_revenue: number;
  substituted_units: number;
  shoppers_missed: number;
  first_out: string;
  minutes_out: number;
}

/** A time one product's shelf face stood empty (clock seconds of the day). */
export interface EmptySpell {
  day: number;
  rack_id: string;
  face: string;
  sku: string;
  name: string;
  start: number;
  end: number;
}

/** A product whose backroom ran dry: refills that came up short. */
export interface BackroomStats {
  sku: string;
  name: string;
  level: number;
  refilled: number;
  short_units: number;
  dry_day: number;
  dry_at: string;
}

export interface QueueHour {
  hour: string;
  arrivals: number;
  avg_wait_sec: number;
  max_wait_sec: number;
  abandoned: number;
  counters_open?: number;
  crew_on_duty?: number;
  counters_needed: number;
}

type CrewSettings = "crew" | "crew_schedule" | "refill_at" | "refill_face_sec" | "refill_unit_sec";

/** What one crew member did for a while (clock seconds of the day): serving at a till or refilling a shelf face. */
export interface CrewTask {
  day: number;
  member: number;
  kind: "till" | "refill";
  rack_id: string;
  face: string;
  sku: string;
  name: string;
  start: number;
  end: number;
}

/** What sharing the store did to a run (GET /runs/{rid}/operations; 404 = each shopper had the store alone). */
export interface OperationsReport {
  config: Required<Omit<OperationsConfig, "stock_overrides" | CrewSettings>> & { stock_overrides: Record<string, number> }
    & Pick<OperationsConfig, CrewSettings>;
  days: number;
  counters: number;
  counters_in_layout: number;
  stockout_faces: number;
  shoppers_hit: number;
  lost_units: number;
  lost_revenue: number;
  substituted_units: number;
  substituted_revenue: number;
  restocks: number;
  crowd_skipped_units?: number;
  crowd_skipped_revenue?: number;
  backroom_units?: number;
  refill_short_units?: number;
  deliveries?: number;
  backroom?: BackroomStats[];
  queued: number;
  avg_wait_sec: number;
  p90_wait_sec: number;
  max_wait_sec: number;
  abandoned: number;
  abandoned_units: number;
  abandoned_revenue: number;
  counter_utilization: number;
  till_hours?: number;
  counters_needed: number;
  // With a crew: staff hours on duty, at the tills and refilling; shelves refilled, how long they waited (minutes,
  // on average), the most waiting at once and those still waiting at closing.
  crew_hours?: number;
  crew_till_hours?: number;
  crew_refill_hours?: number;
  face_refills?: number;
  refill_wait_min?: number;
  refill_backlog_max?: number;
  refills_unfinished?: number;
  crew_tasks?: CrewTask[];
  hours: QueueHour[];
  stockouts: StockoutStats[];
  empty_spells?: EmptySpell[];
}

/** How the layout's store is run (null: not saved). Runs, A/B tests and the optimizer on it use these by default. */
export function getLayoutOperations(projectId: string, setupId: string, signal?: AbortSignal): Promise<{ operations: OperationsReport["config"] | null }> {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/setups/${encodeURIComponent(setupId)}/operations`, { signal });
}

export function saveLayoutOperations(projectId: string, setupId: string, operations: OperationsConfig | null): Promise<{ operations: OperationsReport["config"] | null }> {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/setups/${encodeURIComponent(setupId)}/operations`, {
    method: "PUT", body: JSON.stringify({ operations }),
  });
}

export function getRunOperations(projectId: string, runId: string, signal?: AbortSignal): Promise<OperationsReport> {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/operations`, { signal });
}

/** Costs of running the store, in the currency's minor unit. */
export interface OperationsCosts {
  till_hour?: number;
  restock_round?: number;
  stock_unit_day?: number;
}

export interface OperationsOutcome {
  revenue: number;
  lost_revenue: number;
  abandoned_revenue: number;
  abandoned: number;
  avg_wait_sec: number;
  p90_wait_sec: number;
  till_hours: number;
  crew_hours?: number;
  restocks: number;
  face_refills?: number;
  stock_units: number;
  labor_cost: number;
  restock_cost: number;
  holding_cost: number;
  net: number;
}

/** Shoppers who remember: the run's week repeated, with the shoppers a bad visit put off staying away. */
export interface MemoryConfig {
  weeks?: number;
  leave_per_missing_unit?: number;
  leave_after_line?: number;
  leave_per_wait_minute?: number;
  weekly_churn?: number;
}

export interface WeekStats {
  week: number;
  shoppers: number;
  revenue: number;
  lost_revenue: number;
  abandoned: number;
  avg_wait_sec: number;
  net: number;
  left_for_stock: number;
  left_for_tills: number;
  left_anyway: number;
  ideal_shoppers: number;
  ideal_revenue: number;
}

export interface WeeksReport {
  memory: Required<MemoryConfig>;
  weeks: WeekStats[];
  shoppers_first: number;
  shoppers_last: number;
  revenue: number;
  net: number;
  ideal_revenue: number;
  lost_to_memory: number;
}

export interface OperationsReplay {
  planned_revenue: number;
  outcome: OperationsOutcome;
  report: OperationsReport;
  weeks?: WeeksReport | null;
}

export interface OperationsPlan {
  current_config: OperationsReport["config"];
  current: OperationsOutcome;
  config: OperationsReport["config"];
  best: OperationsOutcome;
  replays: number;
  raised_skus: string[];
  // False: the search stopped at its time limit with the best plan found so far.
  complete?: boolean;
  // With shoppers who remember: the weeks under the current plan and the best one.
  current_weeks?: WeeksReport | null;
  best_weeks?: WeeksReport | null;
}

/** The run's shoppers, decisions unchanged, in a store run another way (no model call). */
export function replayOperations(
  projectId: string, runId: string, body: { operations: OperationsConfig; costs: OperationsCosts; memory?: MemoryConfig },
  signal?: AbortSignal,
): Promise<OperationsReplay> {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/operations/replay`, {
    method: "POST", body: JSON.stringify(body), signal,
  });
}

/** The best stock, refill and till plan found for the run's shoppers under these costs. */
export function planOperations(
  projectId: string, runId: string,
  body: { costs: OperationsCosts; operations?: OperationsConfig; memory?: MemoryConfig; max_crew?: number },
  signal?: AbortSignal,
): Promise<OperationsPlan> {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/operations/plan`, {
    method: "POST", body: JSON.stringify(body), signal,
  });
}

export type ShelfViewMode = "chart" | "photo_chart";

/** A stocked rack face and the key its 3D photo is stored under (GET /setups/{sid}/shelf-views). */
export interface ShelfViewFace {
  rack_id: string;
  rack_name: string;
  face: Face;
  key: string;
  ready: boolean;
}

export interface ShelfViewStatus {
  currency: string;
  faces: ShelfViewFace[];
  // The store the keys were computed from: render exactly this one.
  store: Store;
}

export function getShelfViews(projectId: string, setupId: string, signal?: AbortSignal): Promise<ShelfViewStatus> {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/setups/${encodeURIComponent(setupId)}/shelf-views`, { signal });
}

export function putShelfView(
  projectId: string, setupId: string, key: string,
  body: { rack_id: string; face: Face; image: string; boxes: Record<string, [number, number, number, number][]> },
  signal?: AbortSignal,
): Promise<ShelfViewFace> {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/setups/${encodeURIComponent(setupId)}/shelf-views/${encodeURIComponent(key)}`, {
    method: "PUT", ...json(body), signal,
  });
}

export interface EnsembleMember {
  model: string;
  weight: number;
  label?: string;
}

export interface EnsembleConfig {
  members: EnsembleMember[];
  mode: "mixture" | "vote";
  seed?: number;
}

// The SimulateRequest body, shared by starting a run and estimating one.
const runBody = (setupId: string, options: RunOptions) => JSON.stringify({ setup_id: setupId, ...options });

export function startRun(
  projectId: string,
  setupId: string,
  options: RunOptions = {},
  signal?: AbortSignal,
): Promise<{ project_id: string; run_id: string; setup_id: string }> {
  return fetchJson(`/api/projects/${projectId}/runs`, {
    method: "POST",
    body: runBody(setupId, options),
    signal,
  });
}

/** About how long and how costly a run with these options is; nothing starts. */
export interface RunEstimate {
  /** Shoppers the run simulates (after the cap, scenario days and opening hours). */
  customers: number;
  /** Distinct weekdays among them. */
  days: number;
  per_day: number;
  engine: EngineType;
  /** "" for the rule-based engine. */
  model: string;
  local: boolean;
  model_calls: number;
  minutes: number;
  cost_usd: number | null;
  /** Long (about 10 min or more) or costly (about $1 or more). */
  warn: boolean;
}

export function estimateRun(
  projectId: string,
  setupId: string,
  options: RunOptions = {},
  signal?: AbortSignal,
): Promise<RunEstimate> {
  return fetchJson(`/api/projects/${projectId}/runs/estimate`, {
    method: "POST",
    body: runBody(setupId, options),
    signal,
  });
}

export interface RunStatus {
  status: string;
  error: string;
  total_customers: number;
  completed_customers?: number;
  failed_customers?: number;
  preview?: boolean;
  engine_type?: string;
  started_at?: string;
  setup_id?: string;
}

export function getRunStatus(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<RunStatus> {
  return fetchJson(`/api/projects/${projectId}/runs/${runId}/status`, { signal });
}

export interface EngineInfo {
  engine_type: EngineType;
  label: string;
  description: string;
  uses_llm: boolean;
  model: string;
  default: boolean;
  /** False when `model` is a cloud model without an API key; `suggested_model` then has a key ("" if none does). */
  model_ready?: boolean;
  suggested_model?: string;
}

export function getEngines(signal?: AbortSignal): Promise<EngineInfo[]> {
  return fetchJson(`/api/engines`, { signal });
}

export function getRunTimeline(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<CustomerResult[]> {
  return fetchJson(`/api/projects/${projectId}/runs/${runId}/timeline`, { signal });
}

export interface SegmentStats {
  visitors: number;
  buyers: number;
  revenue: number;
  units: number;
  conversion_rate: number;
  revenue_per_visitor: number;
}

export interface RackStats {
  rack_id: string;
  rack_name: string;
  visitors: number;
  browsers: number;
  buyers: number;
  units: number;
  revenue: number;
  impulse_units: number;
}

export interface ProductStats {
  sku: string;
  name: string;
  units: number;
  revenue: number;
  buyers: number;
  impulse_units: number;
}

export interface RunSummary {
  total_customers: number;
  total_revenue: number;
  top_products: string[];
  by_purpose: Record<string, number>;
  by_identity: Record<string, number>;
  by_age: Record<string, number>;
  by_gender: Record<string, number>;
  // v0.2 KPIs — optional so runs made by older versions still load.
  currency?: string;
  buyers?: number;
  conversion_rate?: number;
  units_sold?: number;
  avg_units_per_buyer?: number;
  avg_basket_value?: number;
  revenue_per_visitor?: number;
  /** null: the run (made by an older version) did not record which purchases were impulse buys. */
  impulse_revenue_share?: number | null;
  impulse_unit_share?: number;
  avg_visit_sec?: number;
  avg_path_tiles?: number;
  top_products_by_units?: string[];
  products?: ProductStats[];
  racks?: RackStats[];
  segments?: Record<string, Record<string, SegmentStats>>;
  hourly_visitors?: Record<string, number>;
}

export interface RunManifest {
  engine_type: string;
  model: string;
  seed: number;
  replicate: number;
  exposure_model: string;
  route_ordering: string;
  store_fingerprint: string;
  persona_fingerprint: string;
  package_version: string;
  created_at: string;
  scenario?: string;
  scenario_id?: string;
}

export interface RunDiagnostics {
  diagnostics: {
    requested_customers?: number;
    succeeded_customers?: number;
    failed_customers?: { persona_id: string; reason: string }[];
    dropped_invalid_buys?: number;
    dropped_over_budget?: number;
    buy_violations?: Record<string, number>;
  };
  manifest: Partial<RunManifest>;
  token_usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    requests?: number;
    cached_requests?: number;
  };
  // Engine-specific run summary (vision shoppers: glance statistics and examples).
  engine_meta?: VisionGlanceSummary;
}

export interface VisionGlanceRecord {
  persona_id: string;
  rack: string;
  face: string;
  visibility: number;
  product: string;
  number: number;
  interest: number;
  reason: string;
  resolved_sku: string | null;
  resolved_by: string;
  level: number | null;
  outcome: string;
}

export interface VisionGlanceSummary {
  model?: string;
  glances?: number;
  errors?: number;
  noticed_rate?: number;
  mean_interest?: number;
  interest_hist?: Record<string, number>;
  buy_scale?: number;
  resolved_by?: Record<string, number>;
  outcomes?: Record<string, number>;
  picked_level?: Record<string, number>;
  // What the glances showed: the chart, or the 3D photo above it (faces without a photo show the chart).
  shelf_view?: ShelfViewMode;
  views?: Record<string, number>;
  examples?: VisionGlanceRecord[];
  plan_policy?: "vlm" | "rule";
  planning?: {
    plans: number;
    plan_errors: number;
    enter_rate: number;
    mean_items_named: number;
    mean_items_bought: number;
    resolution_rate: number;
    top_categories?: Record<string, number> | [string, number][];
  };
  plan_examples?: VisionPlanRecord[];
}

export interface VisionPlanRecord {
  persona_id: string;
  source: string;
  enter: boolean;
  mission: string;
  reason: string;
  items: [string, string, number][];
  resolved: [string, string, string, string][];
  model: string;
  error: string;
}

export function getRunDiagnostics(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<RunDiagnostics> {
  return fetchJson(`/api/projects/${projectId}/runs/${runId}/diagnostics`, { signal });
}

export interface MetricComparison {
  metric: string;
  mean_a: number;
  mean_b: number;
  diff: number;
  rel_diff: number;
  ci_low: number;
  ci_high: number;
  prob_b_greater: number;
  prob_b_less?: number | null;
  sd_paired_diff: number;
  n_for_5pct_effect: number;
}

export interface ComparisonReport {
  run_a: string;
  run_b: string;
  paired_customers: number;
  unpaired_a: number;
  unpaired_b: number;
  n_bootstrap: number;
  confidence: number;
  metrics: MetricComparison[];
  notes: string[];
  /** One per note, same order: its kind and values, to say it in the user's language. Absent from older servers. */
  note_codes?: { code: string; params: Record<string, string | number> }[];
}

/** Why run B differs from run A, read by the text model from the comparison and both runs' fact sheets. */
export interface DifferenceReading { summary: string; where: string; caveats: string; figures: string[] }
export function explainComparison(projectId: string, a: string, b: string, model = ""): Promise<DifferenceReading> {
  const q = new URLSearchParams({ a, b });
  return fetchJson(`/api/projects/${projectId}/compare/explain?${q.toString()}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model }),
  });
}

export function compareRuns(
  projectId: string,
  runA: string,
  runB: string,
  signal?: AbortSignal,
): Promise<ComparisonReport> {
  const q = new URLSearchParams({ a: runA, b: runB });
  return fetchJson(`/api/projects/${projectId}/compare?${q.toString()}`, { signal });
}

export interface FidelityMetric {
  name: string;
  value: number | null;
  better: string;
  description: string;
}

export interface FidelityReport {
  sim_customers: number;
  real_transactions: number;
  matched_skus: number;
  metrics: FidelityMetric[];
  notes: string[];
}

export async function uploadFidelity(
  projectId: string,
  runId: string,
  file: File,
  signal?: AbortSignal,
): Promise<FidelityReport> {
  const form = new FormData();
  form.append("file", file);
  // No JSON Content-Type here: the browser sets the multipart boundary itself.
  const res = await fetch(`${BASE}/api/projects/${projectId}/runs/${runId}/fidelity`, {
    method: "POST",
    body: form,
    signal,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<FidelityReport>;
}

export function runExportUrl(projectId: string, runId: string): string {
  return `${BASE}/api/projects/${projectId}/runs/${runId}/export.csv`;
}

export function getRunSummary(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<{
  summary: RunSummary;
  personas: Record<string, Persona>;
}> {
  return fetchJson(`/api/projects/${projectId}/runs/${runId}/summary`, { signal });
}

export function getRunHeatmap(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<{
  pathcalc_heatmap: number[][];
  persona_heatmap: number[][];
  // Seconds per tile; empty array for runs made before v0.2.
  dwell_heatmap?: number[][];
}> {
  return fetchJson(`/api/projects/${projectId}/runs/${runId}/heatmap`, { signal });
}

export function getRunStore(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<Store> {
  return fetchJson(`/api/projects/${projectId}/runs/${runId}/store`, { signal });
}

// ── Model providers ─────────────────────────────────────────────────────────

export type ProviderKind =
  | "openai" | "anthropic" | "gemini" | "qwen" | "vllm" | "ollama" | "llamacpp" | "openrouter" | "custom";

export interface ModelSuggestion {
  id: string;
  label: string;
  vision: boolean;
  note: string;
}

export interface ProviderStatus {
  preset: {
    kind: ProviderKind;
    label: string;
    default_api_base: string | null;
    api_key_env: string | null;
    needs_key: boolean;
    local: boolean;
    models: ModelSuggestion[];
    docs_url: string;
  };
  enabled: boolean;
  has_key: boolean;
  key_source: "settings" | "env" | "none" | "not needed";
  key_hint: string;
  /** The provider turned this key down during this session (not valid or revoked). */
  key_rejected?: boolean;
  api_base: string | null;
  default_model: string | null;
  ready: boolean;
  /** A local server at api_base answers now; absent or null when not checked (older servers, cloud, off). */
  answers?: boolean | null;
}

export interface ProviderUpdate {
  enabled?: boolean;
  api_key?: string;
  api_base?: string;
  default_model?: string;
}

export interface ConnectionTest {
  ok: boolean;
  model: string;
  latency_ms: number;
  reply: string;
  error: string;
  vision: boolean;
}

export interface ModelOption {
  ref: string;
  provider: string;
  label: string;
  vision: boolean;
  local: boolean;
}

export function getProviders(signal?: AbortSignal): Promise<ProviderStatus[]> {
  return fetchJson("/api/providers", { signal });
}

export function updateProvider(kind: ProviderKind, update: ProviderUpdate): Promise<ProviderStatus> {
  return fetchJson(`/api/providers/${kind}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export function testModel(model: string, vision: boolean): Promise<ConnectionTest> {
  return fetchJson("/api/providers/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, vision }),
  });
}

export function getModels(signal?: AbortSignal): Promise<ModelOption[]> {
  return fetchJson("/api/models", { signal });
}

// ── Who runs the shoppers: cloud keys, this computer, the local model ──────

export interface GPUInfo {
  vendor: "nvidia" | "amd" | "intel" | "apple" | "other";
  name: string;
  vram_gb: number;
  cuda: string;
}

export interface HardwareProfile {
  os: "windows" | "macos" | "linux" | "other";
  arch: "x64" | "arm64" | "other";
  cpu: string;
  cores: number;
  threads: number;
  ram_gb: number;
  ram_free_gb: number;
  gpus: GPUInfo[];
}

export interface LocalModelChoice {
  key: string;
  label: string;
  repo: string;
  download_gb: number;
  memory_gb: number;
}

export interface LocalVLMPlan {
  backend: "cuda" | "metal" | "vulkan" | "cpu";
  model: LocalModelChoice;
  device: string;
  gpu_layers: number;
  threads: number;
  parallel: number;
  context: number;
  reason: string;
}

export interface LocalVLMStatus {
  state: "off" | "disabled" | "preparing" | "downloading" | "starting" | "ready" | "error";
  message: string;
  progress: number | null;
  downloaded_mb: number;
  total_mb: number;
  api_base: string | null;
  model_ref: string;
  managed: boolean;
  runtime: string;
  /** The model and its runtime are on this computer: starting downloads nothing. Absent from older servers. */
  downloaded?: boolean;
}

export interface ModelSetup {
  cloud_providers: string[];
  warning: string | null;
  local: LocalVLMStatus;
  hardware: HardwareProfile;
  plan: LocalVLMPlan;
}

export function getModelSetup(signal?: AbortSignal): Promise<ModelSetup> {
  return fetchJson("/api/system/models", { signal });
}

export function startLocalModel(): Promise<LocalVLMStatus> {
  return fetchJson("/api/system/local-model/start", { method: "POST" });
}

export function stopLocalModel(): Promise<LocalVLMStatus> {
  return fetchJson("/api/system/local-model/stop", { method: "POST" });
}

// ── Scenarios ───────────────────────────────────────────────────────────────

export type Weather =
  | "clear" | "cloudy" | "rain" | "heavy_rain" | "snow" | "heatwave" | "cold_snap" | "fine_dust" | "typhoon";
export type DayType = "weekday" | "weekend" | "public_holiday" | "holiday_season" | "school_vacation";
export type EventKind =
  | "festival" | "sports_match" | "concert" | "exam_period" | "payday" | "competitor_opening"
  | "competitor_closed" | "road_construction" | "marathon" | "conference" | "night_market";
export type PromotionKind = "discount" | "1+1" | "2+1" | "featured";
export type Crowding = "quiet" | "normal" | "busy" | "packed";

export interface LocalEvent {
  kind: EventKind;
  intensity: number;
  start_hour: number;
  end_hour: number;
  note?: string;
}

export interface Promotion {
  target: string;
  kind: PromotionKind;
  discount_pct: number;
  label?: string;
}

export interface Scenario {
  id: string;
  name: string;
  description: string;
  weather: Weather;
  temperature_c: number | null;
  season: "spring" | "summer" | "autumn" | "winter" | null;
  day_type: DayType;
  only_days: number[];
  traffic_multiplier: number;
  hourly_traffic: Record<string, number>;
  crowding: Crowding;
  events: LocalEvent[];
  promotions: Promotion[];
  stockouts: string[];
  budget_multiplier: number;
  music: "none" | "calm" | "upbeat";
  lighting: "dim" | "normal" | "bright";
  notes: string;
}

export interface ScenarioEffects {
  situation: string;
  traffic: number;
  traffic_by_hour: Record<string, number>;
  demand: Record<string, number>;
  impulse: number;
  dwell: number;
  walkout: number;
  budget: number;
  quantity: number;
}

export interface ScenarioPreset {
  scenario: Scenario;
  effects: ScenarioEffects;
}

/** The layout whose store format sizes scenario effects (a supermarket's holiday season differs from a kiosk's). */
export interface ScenarioLayout { projectId?: string; setupId?: string }

function scenarioLayoutQuery({ projectId, setupId }: ScenarioLayout): string {
  const q = new URLSearchParams();
  if (projectId) q.set("project_id", projectId);
  if (setupId) q.set("setup_id", setupId);
  const query = q.toString();
  return query ? `?${query}` : "";
}

export function getScenarios(layout: ScenarioLayout = {}, signal?: AbortSignal): Promise<ScenarioPreset[]> {
  return fetchJson(`/api/scenarios${scenarioLayoutQuery(layout)}`, { signal });
}

export interface DescribedScenario {
  scenario: Scenario;
  effects: ScenarioEffects;
  /** Promotion or stock-out targets that matched no product (left out) or several products. */
  warnings: string[];
}

/** The text model turns a plain description of the day into a custom scenario, checked against the layout. */
export function describeScenario(
  req: { text: string; project_id?: string; setup_id?: string; model?: string },
  signal?: AbortSignal,
): Promise<DescribedScenario> {
  return fetchJson("/api/scenarios/describe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
}

export function previewScenario(scenario: Scenario, layout: ScenarioLayout = {}, signal?: AbortSignal): Promise<ScenarioEffects> {
  return fetchJson(`/api/scenarios/preview${scenarioLayoutQuery(layout)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scenario),
    signal,
  });
}

// ── Neighborhood (town) ─────────────────────────────────────────────────────

export type TownArchetype =
  | "residential" | "university" | "business_district" | "suburban" | "station_area" | "tourist" | "mixed";
export type VenueCategory =
  | "convenience" | "cafe" | "bakery" | "pharmacy" | "restaurant" | "fast_food" | "supermarket" | "bar"
  | "gym" | "bookstore" | "academy" | "laundry" | "bank" | "pc_room";
export type TownDayType = "weekday" | "weekend" | "holiday";

export interface TownBuilding {
  id: string;
  kind: string;
  name: string;
  x: number;
  y: number;
  width: number;
  depth: number;
  floors: number;
  residents: number;
  workers: number;
  students: number;
  daily_passersby: number;
  visitors: number;
}

export interface TownVenue {
  id: string;
  name: string;
  category: VenueCategory;
  x: number;
  y: number;
  attractiveness: number;
  open_hour: number;
  close_hour: number;
  is_focal: boolean;
}

export interface TownRoad {
  id: string;
  kind: "arterial" | "street" | "alley" | "footpath";
  points: [number, number][];
  name: string;
}

export interface Town {
  id: string;
  name: string;
  archetype: TownArchetype;
  size_m: number;
  buildings: TownBuilding[];
  venues: TownVenue[];
  roads: TownRoad[];
  source: "procedural" | "osm";
  center_lat: number | null;
  center_lon: number | null;
  focal_venue_id: string;
}

export interface TownSpec {
  archetype: TownArchetype;
  size_m: number;
  density: number;
  n_competitors: number | null;
  neighbor_categories: VenueCategory[];
  venue_density?: number;
  seed: number;
  name?: string;
}

export interface TownDemand {
  focal_venue_id: string;
  day_type: TownDayType;
  total_daily_visitors: number;
  direct_visitors: number;
  linked_visitors: number;
  hourly_totals: number[];
  segment_totals: Record<string, number>;
  origin_shares: {
    building_id: string; kind: string; name: string; segment: string; distance_m: number;
    expected_visitors: number; share: number;
  }[];
  linked_trips: { from_venue_id: string; from_name: string; from_category: VenueCategory; distance_m: number; expected_visitors: number }[];
  store_shares: { venue_id: string; name: string; category: VenueCategory; is_focal: boolean; distance_m: number; expected_visitors: number; share: number }[];
  market_share: number;
  catchment_radius_50_m: number;
  catchment_radius_80_m: number;
  avg_walk_distance_m: number;
}

export interface SynergyRow {
  venue_id: string;
  name: string;
  category: VenueCategory;
  distance_m: number;
  effect_on_focal_visitors: number;
  effect_on_focal_pct: number;
  role: "competitor" | "complement" | "neutral";
}

const json = (body: unknown) => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export async function getTown(projectId: string, signal?: AbortSignal): Promise<Town | null> {
  const res = await fetch(`${BASE}/api/projects/${projectId}/town`, { signal });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text().catch(() => "")}`);
  return res.json() as Promise<Town>;
}

export function generateTown(projectId: string, spec: TownSpec): Promise<Town> {
  return fetchJson(`/api/projects/${projectId}/town/generate`, { method: "POST", ...json(spec) });
}

/** Where a plain-words request belongs: an A/B test, a shelf test, a conjoint study, a concept test, a staff script, the neighborhood, a question
 * about the last run, or none of these. */
export function routeAssist(req: { text: string; has_run: boolean }): Promise<{
  destination: "ab_test" | "shelf_test" | "conjoint" | "concept_test" | "staff_script" | "layout_edit" | "area" | "run_question"
    | "find_shoppers" | "optimize" | "none";
  reason: string;
}> {
  return fetchJson(`/api/assist/route`, { method: "POST", ...json(req) });
}

/** The create-store form filled from one description: only what it says, the format from the generator's list. */
export interface StoreSetupDraft {
  name: string; description: string; address: string; store_type: string; template_id: string;
  open_days: "7" | "weekday" | "weekend" | null; open_hour: number | null; close_hour: number | null;
  currency: "USD" | "KRW" | "JPY" | null; rationale: string; warnings: string[];
}
export function draftStoreSetup(req: { text: string; locale: string }): Promise<StoreSetupDraft> {
  return fetchJson(`/api/assist/store-setup`, { method: "POST", ...json(req) });
}

/** A customer profile drafted by the text model from the create-store form; nothing is saved. */
export function draftCustomerProfile(req: {
  name: string; description: string; address: string; store_type: string; hours: string; locale: string;
}): Promise<{ profile: string }> {
  return fetchJson(`/api/assist/customer-profile`, { method: "POST", ...json(req) });
}

/** The text model turns a description of the area into a generator spec; nothing is generated. */
export function describeTown(projectId: string, req: { text: string; seed: number; model?: string }): Promise<{ spec: TownSpec; rationale: string }> {
  return fetchJson(`/api/projects/${projectId}/town/describe`, { method: "POST", ...json(req) });
}

export function importTownFromMap(
  projectId: string,
  req: { address?: string; lat?: number; lon?: number; radius_m: number },
): Promise<Town> {
  return fetchJson(`/api/projects/${projectId}/town/import-osm`, { method: "POST", ...json(req) });
}

export function addTownVenue(
  projectId: string,
  venue: { category: VenueCategory; x: number; y: number; name?: string },
): Promise<Town> {
  return fetchJson(`/api/projects/${projectId}/town/venues`, { method: "POST", ...json(venue) });
}

export function removeTownVenue(projectId: string, venueId: string): Promise<Town> {
  return fetchJson(`/api/projects/${projectId}/town/venues/${venueId}`, { method: "DELETE" });
}

export function getTownDemand(
  projectId: string, dayType: TownDayType, scenarioId: string | null, signal?: AbortSignal,
): Promise<TownDemand> {
  const qs = new URLSearchParams({ day_type: dayType, ...(scenarioId ? { scenario_id: scenarioId } : {}) });
  return fetchJson(`/api/projects/${projectId}/town/demand?${qs}`, { signal });
}

export function getTownSynergy(projectId: string, dayType: TownDayType): Promise<SynergyRow[]> {
  return fetchJson(`/api/projects/${projectId}/town/synergy?day_type=${dayType}`);
}

export interface CategoryShift {
  category: string;
  spend_with: number;
  spend_without: number;
  units_with: number;
  units_without: number;
  spend_diff: number;
}

export interface SynergyExample {
  persona_id: string;
  context_with: string;
  context_without: string;
  mission_with: string;
  mission_without: string;
  spend_with: number;
  spend_without: number;
}

export interface VLMSynergyResult {
  currency?: string | null;
  venue_id: string;
  venue_name: string;
  category: string;
  distance_m: number;
  model: string;
  visitors_with: number;
  visitors_without: number;
  delta_visitors: number;
  linked_visitors_from_venue: number;
  panel_customers: number;
  affected_customers: number;
  affected_share: number;
  spend_per_visitor_with: number;
  spend_per_visitor_without: number;
  delta_spend_per_visitor: number;
  delta_spend_ci_low: number | null;
  delta_spend_ci_high: number | null;
  prob_spend_higher: number | null;
  conversion_with: number;
  conversion_without: number;
  delta_conversion: number;
  category_shifts: CategoryShift[];
  revenue_per_day_with: number;
  revenue_per_day_without: number;
  delta_revenue_per_day: number;
  delta_revenue_from_visitors: number;
  delta_revenue_from_baskets: number;
  examples: SynergyExample[];
  vlm_requests: number;
  failed_customers: number;
  seconds: number;
  notes: string[];
}

export interface SynergyJobStatus {
  job_id: string;
  venue_id: string;
  venue_name: string;
  setup_id: string;
  status: "pending" | "running" | "completed" | "failed" | "canceled";
  phase: string;
  done: number;
  total: number;
  error: string;
  created_at: string;
  finished_at: string;
}

export function startVlmSynergy(
  projectId: string, venueId: string,
  body: { model?: string | null; ensemble?: EnsembleConfig | null; customers: number; scenario_id?: string | null; day_type: TownDayType },
): Promise<SynergyJobStatus> {
  return fetchJson(`/api/projects/${projectId}/town/venues/${venueId}/synergy-vlm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getVlmSynergyJob(
  projectId: string, jobId: string, signal?: AbortSignal,
): Promise<{ status: SynergyJobStatus; result: VLMSynergyResult | null }> {
  return fetchJson(`/api/projects/${projectId}/town/synergy-jobs/${jobId}`, { signal });
}

export function listVlmSynergyJobs(projectId: string, venueId?: string, signal?: AbortSignal): Promise<SynergyJobStatus[]> {
  return fetchJson(`/api/projects/${projectId}/town/synergy-jobs${venueId ? `?venue_id=${venueId}` : ""}`, { signal });
}

// ── Layout optimization ─────────────────────────────────────────────────────

export type OptimizeObjective =
  | "revenue_per_visitor" | "total_revenue" | "conversion_rate" | "impulse_revenue" | "units_per_visitor" | "walking_distance";
export type OptimizeScope = "planogram" | "placement" | "both";
export type OptimizeAlgorithm = "hill_climb" | "anneal" | "genetic";

export interface OptimizeSpec {
  objective: OptimizeObjective;
  scope: OptimizeScope;
  algorithm: OptimizeAlgorithm;
  budget: number;
  eval_customers: number;
  validation_customers?: number | null;
  seed: number;
  constraints: { keep_fridges_on_walls: boolean; lock_rack_ids: string[]; max_moves: number; min_improvement: number };
}

export type OptimizeJudge = "rule" | "vlm";

export interface JudgeSpec {
  judge: OptimizeJudge;
  model?: string | null;
  ensemble?: EnsembleConfig | null;
  vlm_customers: number;
  top_k: number;
  calibrate: boolean;
}

export interface ImpulseProfile {
  impulse_rate: number;
  impulse_revenue_share: number;
  level_distribution: Record<string, number>;
}

export interface SurrogateCalibration {
  pilot_customers: number;
  surrogate_customers: number;
  target: ImpulseProfile;
  before: ImpulseProfile;
  after: ImpulseProfile;
  gap_before: number;
  gap_after: number;
  impulse_base_before: number;
  impulse_base_after: number;
  grid_points: number;
  notes: string[];
}

export interface JudgedCandidate {
  label: string;
  iteration: number;
  moves: string[];
  surrogate_score: number;
  surrogate_rank: number;
  vlm_score: number | null;
  vlm_rank: number | null;
  delta_mean: number | null;
  delta_ci_low: number | null;
  delta_ci_high: number | null;
  prob_better: number | null;
  relative_improvement: number | null;
  failed_customers: number;
  plan_errors: number;
  winner: boolean;
}

export interface VLMJudgeReport {
  model: string;
  customers: number;
  metric: string;
  candidates: JudgedCandidate[];
  winner: string;
  surrogate_winner: string;
  spearman: number | null;
  calibration: SurrogateCalibration | null;
  vlm_requests: number;
  seconds: number;
  notes: string[];
}

export interface OptimizationStatus {
  job_id: string;
  setup_id: string;
  status: "pending" | "running" | "completed" | "failed" | "canceled";
  phase?: string;
  judge?: JudgeSpec;
  error: string;
  evaluations: number;
  budget: number;
  baseline_score: number | null;
  best_score: number | null;
  scenario: string;
  spec: OptimizeSpec;
  created_at: string;
  finished_at: string;
  applied_setup_id: string | null;
  // Candidates were judged with shoppers sharing the store run this way (null: each had the store alone).
  operations?: OperationsConfig | null;
}

export interface OptimizeResult {
  baseline_score: number;
  best_score: number;
  relative_improvement: number;
  applied_moves: string[];
  history: { iteration: number; score: number; accepted: boolean; move: string; best_score: number }[];
  evaluations: number;
  seconds: number;
  baseline_summary: RunSummary | null;
  best_summary: RunSummary | null;
  validation: ComparisonReport | null;
  validation_metric: string;
  validation_relative_improvement: number | null;
  validation_prob_better: number | null;
  notes: string[];
  judge?: VLMJudgeReport | null;
}

export interface OptimizationView {
  status: OptimizationStatus;
  result: OptimizeResult | null;
}

/** An optimization's settings read from the goal the manager writes; nothing starts. */
export interface OptimizeGoal {
  objective: OptimizeObjective; scope: OptimizeScope; max_moves: number | null; keep_fridges_on_walls: boolean | null;
  lock_rack_ids: string[]; locked: string[]; min_improvement: number | null; rationale: string; warnings: string[];
}
export function readOptimizeGoal(projectId: string, setupId: string, text: string): Promise<OptimizeGoal> {
  return fetchJson(`/api/projects/${projectId}/setups/${setupId}/optimize/goal`, { method: "POST", ...json({ text }) });
}

export function startOptimization(
  projectId: string, setupId: string, spec: OptimizeSpec, scenarioId: string | null, judge?: JudgeSpec,
): Promise<OptimizationStatus> {
  return fetchJson(`/api/projects/${projectId}/setups/${setupId}/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec, scenario_id: scenarioId, ...(judge ?? {}) }),
  });
}

export function cancelOptimization(projectId: string, jobId: string): Promise<OptimizationStatus> {
  return fetchJson(`/api/projects/${projectId}/optimizations/${jobId}/cancel`, { method: "POST" });
}

export function getOptimization(projectId: string, jobId: string, signal?: AbortSignal): Promise<OptimizationView> {
  return fetchJson(`/api/projects/${projectId}/optimizations/${jobId}`, { signal });
}

export function applyOptimization(projectId: string, jobId: string): Promise<{ id: string; name: string }> {
  return fetchJson(`/api/projects/${projectId}/optimizations/${jobId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

// ── Store-format templates ──────────────────────────────────────────────────

export interface StoreTemplate {
  id: string;
  name: string;
  description: string;
  store_type: string;
  grid: [number, number];
  racks: number;
  skus: number;
  open_hours: [number, number];
  closed_days?: number[];
  default_style: NonNullable<LayoutOptions["style"]>;
  default_design: StoreDesign;
  default_dining_tables: number;
  default_checkouts?: number;
  default_seating_zone?: LayoutOptions["seating_zone"];
  default_checkout_placement?: LayoutOptions["checkout_placement"];
  categories?: { id: string; label: string }[];
}

export interface ReservedArea {
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DiningTableMix {
  two_seat: number;
  four_seat: number;
  six_seat: number;
}

export interface LayoutOptions {
  style?: "aisles" | "loop" | "spine" | "cross" | "plaza" | "free_flow" | "perimeter" | "showroom" | null;
  width?: number | null;
  height?: number | null;
  density?: "spacious" | "balanced" | "dense";
  aisle_width?: number | null;
  max_shelf_run?: number | null;
  shelf_direction?: "horizontal" | "vertical";
  entrance?: "left" | "center" | "right";
  gate_wall?: "front" | "back" | "left" | "right";
  exit_position?: "shared" | "left" | "center" | "right";
  exit_wall?: "front" | "back" | "left" | "right" | null;
  checkouts?: number | null;
  checkout_placement?: "auto" | "near_entrance" | "away_from_entrance";
  checkout_wall?: "front" | "back" | "left" | "right";
  checkout_clearance?: number;
  fixture_design?: "mixed" | "a" | "b" | "c";
  design_theme?: StoreDesign | null;
  design_colors?: InteriorColors | null;
  dining_tables?: number | null;
  dining_seats?: 2 | 4 | 6;
  table_mix?: DiningTableMix | null;
  table_rotation?: 0 | 90;
  table_clearance?: number;
  table_clearance_x?: number | null;
  table_clearance_y?: number | null;
  seating_zone?: "auto" | "front" | "back" | "left" | "right" | "center" | "near_entrance" | "away_from_entrance";
  reserved_areas?: ReservedArea[];
  excluded_categories?: string[];
  products_per_category?: number | null;
  category_product_limits?: Record<string, number>;
  open_hour?: number | null;
  close_hour?: number | null;
  closed_days?: number[] | null;
  weekly_hours?: DaySchedule[] | null;
}

export interface GenerateLayoutRequest extends LayoutOptions {
  template_id: string;
  source_setup_id?: string | null;
  seed: number;
  currency: string;
  name?: string;
  requirements?: string;
}

export interface LayoutPreset {
  format: "twinstore-layout-options";
  version: 1;
  layout: GenerateLayoutRequest;
}

export function validateLayoutPreset(value: unknown, signal?: AbortSignal): Promise<LayoutPreset> {
  return fetchJson("/api/store-templates/preset/validate", { method: "POST", body: JSON.stringify(value), signal });
}

/** A design brief read into the generator's options: a patch of checked options, each in words, and what the options
 * cannot express. Nothing is built. */
export interface BriefReading {
  options: Partial<LayoutOptions>; applied: string[]; not_expressible: string[]; warnings: string[]; rationale: string;
}
export function readLayoutBrief(templateId: string, req: { brief: string; options: Record<string, unknown> }): Promise<BriefReading> {
  return fetchJson(`/api/store-templates/${encodeURIComponent(templateId)}/brief`, { method: "POST", ...json(req) });
}

export function getStoreTemplates(signal?: AbortSignal): Promise<StoreTemplate[]> {
  return fetchJson("/api/store-templates", { signal });
}

export function previewStoreTemplate(request: GenerateLayoutRequest, signal?: AbortSignal): Promise<Store> {
  const { name: _name, source_setup_id: _source, requirements: _requirements, ...options } = request;
  return fetchJson("/api/store-templates/preview", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(options), signal,
  });
}

export function generateLayout(projectId: string, body: GenerateLayoutRequest): Promise<SetupSummaryShort> {
  return fetchJson(`/api/projects/${projectId}/setups/generate`, { method: "POST", body: JSON.stringify(body) });
}

export interface GenerateBuildingRequest {
  name: string;
  floors: { label: string; layout: GenerateLayoutRequest }[];
}

export interface BuildingPreset {
  format: "twinstore-building-options";
  version: 1;
  floors: GenerateBuildingRequest["floors"];
}

export function validateBuildingPreset(value: unknown, signal?: AbortSignal): Promise<BuildingPreset> {
  return fetchJson("/api/store-templates/building-preset/validate", { method: "POST", body: JSON.stringify(value), signal });
}

export function generateBuilding(projectId: string, body: GenerateBuildingRequest): Promise<{ setups: SetupSummaryShort[]; active_setup_id: string }> {
  return fetchJson(`/api/projects/${projectId}/setups/generate-building`, { method: "POST", body: JSON.stringify(body) });
}

// ── Shelf capture (photo → planogram) ───────────────────────────────────────

export type CaptureDetector = "auto" | "gdino" | "vlm" | "classic";

export interface CaptureBox { x1: number; y1: number; x2: number; y2: number }

export interface CaptureBand {
  index: number;
  level: number;
  top: number;
  bottom: number;
  polygon: [number, number][];
}

export interface CaptureItem {
  id: string;
  band: number;
  level: number;
  order: number;
  facings: number;
  boxes: CaptureBox[];
  sku: string;
  name: string;
  brand: string;
  size: string;
  category: string;
  raw_category: string;
  price: number | null;
  price_estimated: boolean;
  price_text: string;
  confidence: number;
  labeled: boolean;
}

export interface CaptureGap { band: number; level: number; box: CaptureBox; facings: number }

export interface CaptureResult {
  image_size: [number, number];
  tilt_deg: number;
  detector: string;
  detection_sources: Record<string, number>;
  model: string;
  currency: string;
  rack_type: "shelf" | "fridge";
  bands: CaptureBand[];
  items: CaptureItem[];
  gaps: CaptureGap[];
  dominant_category: string;
  notes: string[];
  timings: Record<string, number>;
  vlm_calls: number;
  edited: boolean;
}

export interface CaptureStatus {
  capture_id: string;
  status: "pending" | "running" | "completed" | "failed";
  stage: string;
  progress: number;
  error: string;
  options: { detector: CaptureDetector; model: string; currency: string; rack_type: "shelf" | "fridge"; label: string };
  image_name: string;
  image_size: [number, number];
  created_at: string;
  finished_at: string;
  items: number;
  facings: number;
  gaps: number;
  levels: number;
  applied_setup_ids: string[];
}

export interface CaptureView { status: CaptureStatus; result: CaptureResult | null }

export interface CaptureEdit {
  id?: string;
  name: string;
  brand: string;
  size: string;
  category: string;
  price?: number | null;
  facings: number;
  level?: number;
  merged_from?: string[];
}

export interface CaptureApplyResult {
  setup_id: string;
  rack_ids: string[];
  face: string;
  placed_items: number;
  placed_facings: number;
  dropped: string[];
  notes: string[];
}

export async function createCapture(
  projectId: string, image: File,
  opts: { detector: CaptureDetector; model: string; currency: string; rack_type: "shelf" | "fridge"; label?: string; request_id?: string },
  signal?: AbortSignal,
): Promise<CaptureStatus> {
  const form = new FormData();
  form.append("image", image);
  form.append("detector", opts.detector);
  form.append("model", opts.model);
  form.append("currency", opts.currency);
  form.append("rack_type", opts.rack_type);
  if (opts.label) form.append("label", opts.label);
  if (opts.request_id) form.append("request_id", opts.request_id);
  const res = await fetch(`${BASE}/api/projects/${projectId}/captures`, { method: "POST", body: form, signal });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(apiErrorMessage(body, `Upload failed (HTTP ${res.status})`));
  }
  return res.json() as Promise<CaptureStatus>;
}

export function listCaptures(projectId: string, signal?: AbortSignal): Promise<CaptureStatus[]> {
  return fetchJson(`/api/projects/${projectId}/captures`, { signal });
}

export function getCapture(projectId: string, captureId: string, signal?: AbortSignal): Promise<CaptureView> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}`, { signal });
}

export function captureImageUrl(projectId: string, captureId: string, overlay = false): string {
  return `${BASE}/api/projects/${projectId}/captures/${captureId}/image${overlay ? "?overlay=1" : ""}`;
}

export function updateCapture(projectId: string, captureId: string, items: CaptureEdit[]): Promise<CaptureView> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}`, { method: "PUT", body: JSON.stringify({ items }) });
}

export function applyCapture(
  projectId: string, captureId: string,
  body: { setup_id: string; rack_id?: string; face?: string; new_rack?: boolean; name?: string },
): Promise<CaptureApplyResult> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/apply`, { method: "POST", body: JSON.stringify(body) });
}

export async function deleteCapture(projectId: string, captureId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/projects/${projectId}/captures/${captureId}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(apiErrorMessage(await res.text().catch(() => ""), `Delete failed (HTTP ${res.status})`), res.status);
}

// ── Shelf Lab (counterfactual edits, sim2real, compliance audit) ─────────────

export type EditKind = "swap" | "remove" | "replace" | "price" | "promo" | "duplicate";
export type Sim2RealCondition = "render" | "photo" | "photo_raw";

export interface PhotoEdit {
  kind: EditKind;
  item_id: string;
  other_id?: string;
  price?: number | null;
  promo?: string;
  name?: string;
  brand?: string;
  category?: string;
  asset_id?: string;
}

export interface EditChange { kind: EditKind; item_id: string; box: CaptureBox; before: string; after: string }

export interface EditedShelf {
  edit_id: string;
  capture_id: string;
  edits: PhotoEdit[];
  changes: EditChange[];
  result: CaptureResult;
  promos: Record<string, string>;
  image_size: [number, number];
  created_at: string;
}

export interface PackageAsset {
  asset_id: string;
  name: string;
  width: number;
  height: number;
  brand?: string;
  /** The store product this image shows, if linked. */
  sku?: string;
  /** The background was removed on upload. */
  cut_out?: boolean;
  created_at?: string;
}

export interface LabJobStatus {
  job_id: string;
  kind: "sim2real" | "audit";
  capture_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  stage: string;
  error: string;
  created_at: string;
  finished_at: string;
}

export interface GlanceAnswer {
  persona_id: string;
  condition: Sim2RealCondition;
  sku: string;
  name: string;
  level: number;
  interest: number;
  resolved_by: string;
  reason: string;
  error: string;
}

export interface ConditionStats {
  condition: Sim2RealCondition;
  answers: number;
  errors: number;
  none_rate: number;
  mean_interest: number;
  level_share: Record<string, number>;
  picks: Record<string, number>;
}

export interface Agreement {
  condition: Sim2RealCondition;
  pairs: number;
  same_pick: number;
  ci_low: number;
  ci_high: number;
  interest_spearman: number | null;
}

export interface Sim2RealReport {
  job_id: string;
  capture_id: string;
  edit_id: string;
  model: string;
  personas: number;
  conditions: Sim2RealCondition[];
  products: Record<string, string>;
  stats: ConditionStats[];
  agreement: Agreement[];
  answers: GlanceAnswer[];
  notes: string[];
  seconds: number;
}

export interface AuditFinding {
  kind: "missing" | "unexpected" | "misplaced" | "facings" | "price" | "gap";
  level: number;
  sku: string;
  name: string;
  expected: string;
  found: string;
  box: CaptureBox | null;
  loss_per_day: number | null;
  loss_ci: [number, number] | null;
}

export interface LevelCompliance { level: number; expected_facings: number; found_facings: number; matched_facings: number; score: number }

export interface AuditReport {
  job_id: string;
  capture_id: string;
  setup_id: string;
  rack_id: string;
  face: string;
  currency: string;
  compliance: number;
  levels: LevelCompliance[];
  findings: AuditFinding[];
  impact: MetricComparison | null;
  /** Estimated visitors a day: what per-day money scales by. */
  visitors_per_day: number;
  /** Customers simulated a day (a sample of the estimate); 0 or absent = the same as visitors_per_day. */
  simulated_visitors_per_day?: number;
  revenue_delta_per_day: number | null;
  revenue_delta_ci: [number, number] | null;
  panel_size: number;
  notes: string[];
  seconds: number;
}

export interface LabJobView { status: LabJobStatus; sim2real: Sim2RealReport | null; audit: AuditReport | null }

export async function uploadPackage(
  projectId: string, file: File, meta: { name?: string; brand?: string; sku?: string; remove_background?: boolean } = {},
): Promise<PackageAsset> {
  const form = new FormData();
  form.append("image", file);
  for (const [k, v] of Object.entries(meta)) if (v !== undefined && v !== "") form.append(k, String(v));
  // Empty headers let the browser set the multipart boundary.
  return fetchJson(`/api/projects/${projectId}/lab/packages`, { method: "POST", body: form, headers: {} });
}

export function listPackages(projectId: string, signal?: AbortSignal): Promise<PackageAsset[]> {
  return fetchJson(`/api/projects/${projectId}/lab/packages`, { signal });
}

export interface PackReading { name: string; brand: string; size: string; category: string; shelf_product: string; confidence: number }

/** A vision model reads the pack: printed name and brand replace the file-name guess; an exact layout product is linked. */
export function readPackage(projectId: string, assetId: string, req: { setup_id?: string; model?: string } = {}): Promise<{ asset: PackageAsset; reading: PackReading; model: string; linked: boolean }> {
  return fetchJson(`/api/projects/${projectId}/lab/packages/${assetId}/read`, { method: "POST", body: JSON.stringify(req) });
}

export function updatePackage(projectId: string, assetId: string, update: { name?: string; brand?: string; sku?: string }): Promise<PackageAsset> {
  return fetchJson(`/api/projects/${projectId}/lab/packages/${assetId}`, { method: "PATCH", body: JSON.stringify(update) });
}

export async function deletePackage(projectId: string, assetId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/projects/${projectId}/lab/packages/${assetId}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(apiErrorMessage(await res.text().catch(() => ""), `Delete failed (HTTP ${res.status})`), res.status);
}

export function packageUrl(projectId: string, assetId: string): string {
  return `${BASE}/api/projects/${projectId}/lab/packages/${assetId}`;
}

export function createEdit(projectId: string, captureId: string, edits: PhotoEdit[]): Promise<EditedShelf> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/edits`, { method: "POST", body: JSON.stringify({ edits }) });
}

export function listEdits(projectId: string, captureId: string, signal?: AbortSignal): Promise<EditedShelf[]> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/edits`, { signal });
}

export function editFileUrl(projectId: string, captureId: string, editId: string, kind: "image" | "mask"): string {
  return `${BASE}/api/projects/${projectId}/captures/${captureId}/edits/${editId}/${kind}`;
}

export async function deleteEdit(projectId: string, captureId: string, editId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/projects/${projectId}/captures/${captureId}/edits/${editId}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(apiErrorMessage(await res.text().catch(() => ""), `Delete failed (HTTP ${res.status})`), res.status);
}

export function startSim2Real(
  projectId: string, captureId: string,
  body: { conditions?: Sim2RealCondition[]; personas?: number; model?: string; edit_id?: string; seed?: number; situation?: string },
): Promise<LabJobStatus> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/sim2real`, { method: "POST", body: JSON.stringify(body) });
}

export function startAudit(
  projectId: string, captureId: string,
  body: { setup_id: string; rack_id: string; face?: string | null; edit_id?: string; panel?: number; max_stockouts?: number },
): Promise<LabJobStatus> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/audit`, { method: "POST", body: JSON.stringify(body) });
}

export function listLabJobs(projectId: string, captureId: string, signal?: AbortSignal): Promise<LabJobStatus[]> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/lab/jobs`, { signal });
}

export function getLabJob(projectId: string, captureId: string, jobId: string, signal?: AbortSignal): Promise<LabJobView> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/lab/jobs/${jobId}`, { signal });
}

// ── Floor plan import (sketch / CAD / PDF page → new layout) ─────────────────

export interface FloorPlanImport {
  setup_id: string;
  setup: SetupSummaryShort;
  reading: { width_m: number; depth_m: number; reader: string; fixtures: { kind: string; label: string }[]; notes: string[] };
  grid_size: [number, number];
  racks: number;
  notes: string[];
  warnings: string[];
  source_page: number;
  source_pages: number;
  source_rotation: number;
}

export interface FloorPlanPreview {
  page_number: number;
  page_count: number;
  rotation: number;
  width: number;
  height: number;
  image: string;
}

export async function previewFloorPlan(
  projectId: string, file: File, opts: { pageNumber: number; rotation: number; signal?: AbortSignal },
): Promise<FloorPlanPreview> {
  const form = new FormData();
  form.append("plan", file);
  form.append("page_number", String(opts.pageNumber));
  form.append("rotation", String(opts.rotation));
  const res = await fetch(`${BASE}/api/projects/${projectId}/floorplan/preview`, { method: "POST", body: form, signal: opts.signal });
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    throw new Error(typeof detail === "string" ? detail : `Preview failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<FloorPlanPreview>;
}

export async function importFloorPlan(
  projectId: string, file: File, opts: { reader: "auto" | "classic" | "vlm"; model?: string; name?: string; pageNumber?: number; rotation?: number },
): Promise<FloorPlanImport> {
  const form = new FormData();
  form.append("plan", file);
  form.append("reader", opts.reader);
  form.append("model", opts.model ?? "");
  form.append("name", opts.name ?? "");
  form.append("page_number", String(opts.pageNumber ?? 1));
  form.append("rotation", String(opts.rotation ?? 0));
  const res = await fetch(`${BASE}/api/projects/${projectId}/floorplan`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(apiErrorMessage(body, `Import failed (HTTP ${res.status})`));
  }
  return res.json() as Promise<FloorPlanImport>;
}

// ── Photo inputs (storefront appeal, receipts) ───────────────────────────────

export interface StorefrontAppeal {
  method: "vlm" | "image_stats";
  model: string;
  signage: number;
  entrance: number;
  window: number;
  upkeep: number;
  overall: number;
  attractiveness: number;
  reasons: string;
}

export interface StorefrontResult { venue_id: string; appeal: StorefrontAppeal; previous_attractiveness: number; town: Town }

export interface ReceiptLine { name: string; quantity: number; unit_price: number | null; line_total: number | null; sku: string; matched: boolean }
export interface ReceiptReading { receipt_id: string; store: string; timestamp: string; currency: string; lines: ReceiptLine[]; total: number | null; notes: string[] }
export interface ReceiptsResult { receipts: ReceiptReading[]; matched_lines: number; unmatched_lines: number; csv: string; products: Record<string, string>; currency: string }
export interface ReceiptIssue { receipt_id: string; line_index: number | null; severity: "error" | "warning"; code: string; message: string }
export interface ReceiptReview { receipts: ReceiptReading[]; issues: ReceiptIssue[]; ready: boolean; included_lines: number; currency: string; csv: string }

export function reviewReceipts(projectId: string, runId: string, receipts: ReceiptReading[]): Promise<ReceiptReview> {
  return fetchJson(`/api/projects/${projectId}/receipts/review`, {
    method: "POST", body: JSON.stringify({ run_id: runId, receipts }),
  });
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(apiErrorMessage(body, `HTTP ${res.status}`));
  }
  return res.json() as Promise<T>;
}

export function rateStorefront(projectId: string, venueId: string, photo: File, model = ""): Promise<StorefrontResult> {
  const form = new FormData();
  form.append("photo", photo);
  form.append("model", model);
  return postForm(`/api/projects/${projectId}/town/venues/${venueId}/storefront`, form);
}

export function readReceipts(projectId: string, photos: File[], target: { setupId?: string; runId?: string }, model = ""): Promise<ReceiptsResult> {
  if (photos.length > 100) return Promise.reject(new Error("Choose at most 100 receipt photos per batch."));
  const form = new FormData();
  for (const p of photos) form.append("photos", p);
  form.append("setup_id", target.setupId ?? "");
  form.append("run_id", target.runId ?? "");
  form.append("model", model);
  return postForm(`/api/projects/${projectId}/receipts`, form);
}

export interface RivalComparison {
  matched: number;
  rival_products: number;
  our_products_in_categories: number;
  price_index: number | null;
  overlap: number;
  only_rival: string[];
  only_ours: string[];
  prices: { name: string; rival_price: number; our_price: number; ratio: number }[];
  suggested_pull_factor: number | null;
}

export interface RivalReport {
  comparison: RivalComparison;
  venue_id: string;
  previous_attractiveness: number | null;
  attractiveness: number | null;
  /** Rival name → our name for products the text model matched although their names differ. */
  model_matches?: Record<string, string>;
  match_note?: string;
}

export function compareRival(
  projectId: string, captureId: string, body: { setup_id: string; venue_id?: string; apply?: boolean },
): Promise<RivalReport> {
  return fetchJson(`/api/projects/${projectId}/captures/${captureId}/rival`, { method: "POST", body: JSON.stringify(body) });
}
