// Frontend mirror of backend/src/store_emulator/domain and server/schemas.

export type Position = [number, number];
export type Shape = number[][];
export type Face = "N" | "S" | "E" | "W";
export type RackType = "shelf" | "fridge" | "counter" | "display" | "table" | "wall" | "entrance" | "exit";
export type Action = "enter" | "move" | "browse" | "buy" | "pay" | "wander" | "exit";

export interface DaySchedule {
  day: number;
  is_open: boolean;
  open_hour: number;
  close_hour: number;
}

export interface SlotItem {
  sku: string;
  name: string;
  price: number;   // minor currency unit (US cents for USD)
  /** Usual price when `price` is temporary (a discount or a raise); 0 or absent = `price` is usual. */
  regular_price?: number;
  promo: string;
  image_url?: string | null;
}

export interface Slot {
  block: number;
  face: Face;
  level: number;
  // Multiple SKUs per coordinate; each SlotItem carries its own name/price/promo. Empty coord is items=[].
  items: SlotItem[];
}

export interface Rack {
  id: string;
  type: RackType;
  shape: Shape;
  position: Position;
  rotation: 0 | 90 | 180 | 270;
  levels: number;
  dwell_min: number;
  dwell_max: number;
  rack_name: string;
  rack_desc: string;
  rack_decoration_desc: string;
  locked_faces: Array<{ block: number; face: Face }>;
  slots: Slot[];
  // Design variant label. May be missing from backend — components default to "a".
  design_variant?: "a" | "b" | "c";
}

export type StoreDesign = "classic" | "warm" | "minimal" | "industrial" | "botanical" | "luxury" | "coastal" | "terracotta";

export interface Store {
  id: string;
  name: string;
  type: string;
  design_theme?: StoreDesign;
  currency?: string | null;
  grid_size: Position;
  weekly_schedule: DaySchedule[];
  racks: Rack[];
}

export interface Persona {
  id: string;
  day: number;
  identity: string;
  age_group: string;
  gender: string;
  description: string;
  intent: string;
  purpose: string;
  arrival_hour: number;
  preferred_categories: string[];
  budget_min: number;
  budget_max: number;
  behavior_tendency: string;
  /** Different items this trip is for; 0 or absent = the engine decides. */
  basket_size?: number;
  /** Categories those items span (e.g. from a past receipt); 0 or absent = unconstrained. */
  basket_kinds?: number;
  /** Products the shopper habitually buys (shelf names). */
  usual_products?: string[];
}

export interface TimelineEvent {
  elapsed_sec: number;
  x: number;
  y: number;
  action: string;
  duration: number;
  target_rack: string;
  face: Face | null;
  description: string;
  product_sku: string;
  product_name: string;
  price: number; // unit price, minor currency unit
  // Units on a BUY line (line total = price × quantity). Missing on runs made before v0.2.
  quantity?: number;
  // "planned" | "impulse" on browse/buy events; missing on older runs.
  origin?: string;
}

export interface CustomerResult {
  persona_id: string;
  day: number;
  arrival_time: string;
  leave_time: string;
  timeline: TimelineEvent[];
  total_spent: number;
  engine_type?: string;
}

export type ReadinessReason =
  | "layout_pending"
  | "personas_pending"
  | "no_layout"
  | "no_personas"
  | "no_items"
  | "no_entrance"
  | "no_exit"
  | "no_counter";

export interface Readiness {
  ready: boolean;
  reasons: ReadinessReason[];
}

export type GenerationKind = "layout" | "persona";
export type GenerationStatusValue = "pending" | "running" | "completed" | "failed";

export interface GenerationStatus {
  status: GenerationStatusValue;
  kind: GenerationKind;
  setup_id: string;
  error: string | null;
  // backend type is dict[str, object] | None; frontend only reads next_gen_id.
  progress: { next_gen_id?: string } | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface GenerationListItem extends GenerationStatus {
  gen_id: string;
}

export interface SlotRow {
  rack_id: string;
  block: number;        // 0-based, in rotated coordinates
  face: Face;
  level: number;        // 1..4
  sku: string;          // empty string = empty slot (excluded from registration count)
  name: string;
  price: number;        // US cents (549 = $5.49)
  promo: string;
}

export interface BlockedFaceInfo {
  rack_id: string;
  block: number;
  face: Face;
  reason: "blocked";
}

// Backend distinguishes 4 reasons (locked/out_of_bounds/occupied/unreachable)
// but the wire response collapses them into a single "blocked". The plural
// `reasons: BlockReason[]` shape is backend-internal (logging).
export interface ClearedSlotInfo {
  rack_id: string;
  block: number;
  face: Face;
  level: number;
  cleared_skus: string[];
  name: string;
  reason: "blocked";
}

export type BlockReason =
  | "locked"
  | "out_of_bounds"
  | "occupied"
  | "unreachable"
  | "occluded";

// validate_layout result. Distinct from BlockedFaceInfo (the POST /util/blocked-faces
// payload), which uses a single reason: "blocked" — this one has a plural reasons array.
export interface BlockedFaceDetail {
  rack_id: string;
  block: number;
  face: Face;
  reasons: BlockReason[];
}

export interface Issue {
  code: string;
  message: string;
  severity: "warning" | "error";
  details: Record<string, unknown>;
}
