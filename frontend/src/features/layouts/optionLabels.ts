// How layout generation options read in the selected language. Option ids (style, design, seating zone, priority,
// reserved-area position) are what the backend receives; only their labels are translated.

import type { LayoutOptions } from "@/shared/api/client";
import type { MessageKey } from "@/shared/i18n/messages";
import type { InteriorColors, StoreDesign } from "@/shared/types/domain";
import { INTERIOR_COLOR_FIELDS } from "@/features/store-viewer/realistic/designThemes";
import type { AreaPosition } from "./reservedAreaPlacement";
import type { LAYOUT_STYLES } from "./templateOptions";

type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

export const STYLE_LABELS: Record<typeof LAYOUT_STYLES[number][0], MessageKey> = {
  aisles: "layStyle_aisles", loop: "layStyle_loop", spine: "layStyle_spine", cross: "layStyle_cross", plaza: "layStyle_plaza",
  free_flow: "layStyle_free_flow", perimeter: "layStyle_perimeter", showroom: "layStyle_showroom",
};

export const DESIGN_LABELS: Record<StoreDesign, MessageKey> = {
  classic: "planDesignClassic", warm: "planDesignWarm", minimal: "planDesignMinimal", industrial: "planDesignIndustrial",
  botanical: "planDesignBotanical", luxury: "planDesignLuxury", coastal: "planDesignCoastal", terracotta: "planDesignTerracotta",
  nordic: "planDesignNordic", retro: "planDesignRetro",
};

export const COLOR_LABELS: Record<typeof INTERIOR_COLOR_FIELDS[number][0], MessageKey> = {
  wall: "layColor_wall", floor: "layColor_floor", accent: "layColor_accent", counter: "layColor_counter",
};

export const COLOR_RESET_LABELS: Record<typeof INTERIOR_COLOR_FIELDS[number][0], MessageKey> = {
  wall: "layResetWall", floor: "layResetFloor", accent: "layResetAccent", counter: "layResetCounter",
};

export const SEATING_LABELS: Record<Exclude<NonNullable<LayoutOptions["seating_zone"]>, "auto">, MessageKey> = {
  front: "laySeating_front", back: "laySeating_back", left: "laySeating_left", right: "laySeating_right",
  center: "laySeating_center", near_entrance: "laySeating_near_entrance", away_from_entrance: "laySeating_away_from_entrance",
};

export const AREA_POSITION_LABELS: Record<AreaPosition, MessageKey> = {
  back_left: "layAreaPos_back_left", back_right: "layAreaPos_back_right", center: "layAreaPos_center",
  front_left: "layAreaPos_front_left", front_right: "layAreaPos_front_right",
};

const PRIORITY_LABELS: Record<string, [MessageKey, MessageKey]> = {
  wide: ["layPriority_wide", "layPriorityHint_wide"],
  capacity: ["layPriority_capacity", "layPriorityHint_capacity"],
  open: ["layPriority_open", "layPriorityHint_open"],
  takeaway: ["layPriority_takeaway", "layPriorityHint_takeaway"],
  compact_cafe: ["layPriority_compact_cafe", "layPriorityHint_compact_cafe"],
  family_dining: ["layPriority_family_dining", "layPriorityHint_family_dining"],
  mixed_parties: ["layPriority_mixed_parties", "layPriorityHint_mixed_parties"],
  service_points: ["layPriority_service_points", "layPriorityHint_service_points"],
};

const BUILDING_LABELS: Record<string, MessageKey> = {
  department: "layBuilding_department", cafe_shop: "layBuilding_cafe_shop", wellness: "layBuilding_wellness",
  dining: "layBuilding_dining", family: "layBuilding_family", tea_vintage: "layBuilding_tea_vintage", campus: "layBuilding_campus",
  family_essentials: "layBuilding_family_essentials", creative_living: "layBuilding_creative_living",
  style_sound: "layBuilding_style_sound", dining_house: "layBuilding_dining_house",
  neighborhood_dining: "layBuilding_neighborhood_dining", daily_essentials: "layBuilding_daily_essentials",
  design_diner: "layBuilding_design_diner", travel_dining: "layBuilding_travel_dining",
  hospital_services: "layBuilding_hospital_services", commuter_dining: "layBuilding_commuter_dining",
  weekend_visits: "layBuilding_weekend_visits", market_design: "layBuilding_market_design",
  neighborhood_care: "layBuilding_neighborhood_care", world_dining: "layBuilding_world_dining",
  creative_beauty: "layBuilding_creative_beauty", curry_pho: "layBuilding_curry_pho", active_living: "layBuilding_active_living",
  thai_turkish: "layBuilding_thai_turkish",
};

const has = (table: object, id: string) => Object.prototype.hasOwnProperty.call(table, id);

export function designLabel(design: StoreDesign, t: Translate): string {
  return t(DESIGN_LABELS[design]);
}

/** The design's name, marked when custom interior colors replace some of its colors. */
export function paletteLabel(design: StoreDesign | undefined, colors: InteriorColors | null | undefined, t: Translate): string {
  const name = designLabel(design ?? "classic", t);
  return INTERIOR_COLOR_FIELDS.some(([key]) => colors?.[key] != null) ? t("planCustomColors", { design: name }) : name;
}

export function priorityLabels(priority: { id: string; name: string; description: string }, t: Translate): { name: string; description: string } {
  if (!has(PRIORITY_LABELS, priority.id)) return priority;
  const [name, description] = PRIORITY_LABELS[priority.id]!;
  return { name: t(name), description: t(description) };
}

export function buildingPresetLabel(preset: { id: string; name: string }, t: Translate): string {
  return has(BUILDING_LABELS, preset.id) ? t(BUILDING_LABELS[preset.id]!) : preset.name;
}

/** "3 cells" / "1 cell" in the selected language. */
export function cellsText(count: number, t: Translate): string {
  return t(count === 1 ? "layCellOne" : "layCellMany", { count });
}
