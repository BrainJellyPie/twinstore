import type { GenerateLayoutRequest, LayoutOptions, StoreTemplate } from "@/shared/api/client";
import type { Layout } from "./hooks/useLayouts";

export interface TemplateChoice extends LayoutOptions {
  templateId: string;
  sourceSetupId?: string;
  seed: number;
  currency: string;
  requirements?: string;
}

export interface OperatingHours {
  open_hour: number;
  close_hour: number;
  closed_days: number[];
}

export interface FloorSize {
  width: number;
  height: number;
}

export function resolveFloorSize(value: Pick<LayoutOptions, "width" | "height">,
  template: Pick<StoreTemplate, "grid"> | undefined): FloorSize | null {
  if (!template) return null;
  const width = value.width ?? template.grid[0];
  const height = value.height ?? template.grid[1];
  return Number.isInteger(width) && width >= 8 && width <= 40 && Number.isInteger(height) && height >= 6 && height <= 40
    ? { width, height } : null;
}

export function resolveOperatingHours(value: Pick<LayoutOptions, "open_hour" | "close_hour" | "closed_days">,
  template: Pick<StoreTemplate, "open_hours" | "closed_days"> | undefined): OperatingHours | null {
  if (!template) return null;
  const open_hour = value.open_hour ?? template.open_hours[0];
  const close_hour = value.close_hour ?? template.open_hours[1];
  const closed_days = value.closed_days ?? template.closed_days ?? [];
  if (!Number.isInteger(open_hour) || open_hour < 0 || open_hour > 23 ||
    !Number.isInteger(close_hour) || close_hour < 1 || close_hour > 24 || open_hour >= close_hour ||
    closed_days.length >= 7 || new Set(closed_days).size !== closed_days.length ||
    closed_days.some((day) => !Number.isInteger(day) || day < 1 || day > 7)) return null;
  return { open_hour, close_hour, closed_days: [...closed_days].sort((a, b) => a - b) };
}

export const DEFAULT_TEMPLATE_CHOICE: TemplateChoice = {
  templateId: "urban_cvs", seed: 0, currency: "USD", style: null,
  density: "balanced", entrance: "left", gate_wall: "front", exit_position: "shared", exit_wall: null, checkouts: null, fixture_design: "mixed", design_theme: null, dining_tables: null,
  checkout_placement: "auto", checkout_wall: "front", checkout_clearance: 0, seating_zone: "auto", reserved_areas: [], shelf_direction: "horizontal", table_clearance: 1, dining_seats: 4, table_rotation: 0,
  aisle_width: null, max_shelf_run: null, excluded_categories: [], products_per_category: null,
  open_hour: null, close_hour: null, closed_days: null, table_mix: null,
};

export const LAYOUT_STYLES = [
  ["aisles", "Parallel aisles"], ["loop", "Racetrack loop"], ["spine", "Central spine"],
  ["cross", "Central cross aisles"], ["plaza", "Central plaza"],
  ["free_flow", "Free-flow islands"], ["perimeter", "Open center / perimeter"], ["showroom", "Showroom groups"],
] as const;

export interface LayoutPriority {
  id: string; name: string; description: string; options: LayoutOptions; checkoutAtEntrance?: boolean;
}

export const LAYOUT_PRIORITIES: LayoutPriority[] = [
  { id: "wide", name: "Wide circulation", description: "Cross aisles, spacious density, 3-cell aisle gaps, shelf runs up to 3 cells and 2-cell space around dining tables.",
    options: { style: "cross", density: "spacious", aisle_width: 3, max_shelf_run: 3, table_clearance: 2 } },
  { id: "capacity", name: "More display space", description: "Parallel aisles, dense displays, 1-cell aisle gaps, shelf runs up to 8 cells and standard 1-cell space around tables.",
    options: { style: "aisles", density: "dense", aisle_width: 1, max_shelf_run: 8, table_clearance: 1 } },
  { id: "open", name: "Open center, no seating", description: "Perimeter displays, balanced density and no dining tables. Restores density-based aisle gaps and shelf runs.",
    options: { style: "perimeter", density: "balanced", dining_tables: 0, aisle_width: null, max_shelf_run: null } },
  { id: "takeaway", name: "Takeaway service", description: "Perimeter displays, balanced density, no dining tables and two counters near the entrance on its wall. Restores density-based aisle gaps and shelf runs.",
    options: { style: "perimeter", density: "balanced", dining_tables: 0, checkouts: 2, checkout_placement: "near_entrance", aisle_width: null, max_shelf_run: null }, checkoutAtEntrance: true },
  { id: "compact_cafe", name: "Compact café seating", description: "Four two-seat tables toward the back, standard 1-cell table clearance and one counter near the entrance. Uses perimeter displays and balanced density; restores density-based aisle gaps and shelf runs.",
    options: { style: "perimeter", density: "balanced", dining_tables: 4, dining_seats: 2, table_mix: null, table_clearance: 1, seating_zone: "back", checkouts: 1, checkout_clearance: 0, checkout_placement: "near_entrance", aisle_width: null, max_shelf_run: null }, checkoutAtEntrance: true },
  { id: "family_dining", name: "Family dining", description: "Six six-seat tables toward the center with 2-cell circulation, plus two counters with 1-cell spacing near the entrance. Uses perimeter displays and balanced density; restores density-based aisle gaps and shelf runs.",
    options: { style: "perimeter", density: "balanced", dining_tables: 6, dining_seats: 6, table_mix: null, table_clearance: 2, seating_zone: "center", checkouts: 2, checkout_clearance: 1, checkout_placement: "near_entrance", aisle_width: null, max_shelf_run: null }, checkoutAtEntrance: true },
  { id: "mixed_parties", name: "Mixed party sizes", description: "Two tables of each size (2, 4 and 6 seats), centered with 1-cell circulation, plus two counters with 1-cell spacing near the entrance. Uses perimeter displays and balanced density; restores density-based aisle gaps and shelf runs.",
    options: { style: "perimeter", density: "balanced", dining_tables: 6, dining_seats: 4, table_mix: { two_seat: 2, four_seat: 2, six_seat: 2 }, table_clearance: 1, seating_zone: "center", checkouts: 2, checkout_clearance: 1, checkout_placement: "near_entrance", aisle_width: null, max_shelf_run: null }, checkoutAtEntrance: true },
  { id: "service_points", name: "Separated service counters", description: "Three counters with 2-cell spacing near the entrance, a spacious central spine, 3-cell aisle gaps and shelf runs up to 3 cells. Removes dining tables.",
    options: { style: "spine", density: "spacious", dining_tables: 0, checkouts: 3, checkout_clearance: 2, checkout_placement: "near_entrance", aisle_width: 3, max_shelf_run: 3 }, checkoutAtEntrance: true },
];

export function applyLayoutPriority(value: TemplateChoice, priority: LayoutPriority): TemplateChoice {
  return { ...value, ...priority.options,
    ...(priority.options.table_mix ? { table_mix: { ...priority.options.table_mix } } : {}),
    ...(priority.options.dining_tables === 0 && value.table_mix ? { table_mix: { two_seat: 0, four_seat: 0, six_seat: 0 } } : {}),
    ...(priority.checkoutAtEntrance ? { checkout_wall: value.gate_wall ?? "front" } : {}),
  };
}

export function validTemplateChoice(value: TemplateChoice): boolean {
  if (value.table_mix != null) {
    const counts = [value.table_mix.two_seat, value.table_mix.four_seat, value.table_mix.six_seat];
    const total = counts.reduce((sum, count) => sum + count, 0);
    if (counts.some((count) => !Number.isInteger(count) || count < 0 || count > 48) || total > 48 ||
      (value.dining_tables != null && value.dining_tables !== total)) return false;
  }
  return !!value.templateId && Number.isSafeInteger(value.seed) &&
    (value.open_hour == null || (Number.isInteger(value.open_hour) && value.open_hour >= 0 && value.open_hour <= 23)) &&
    (value.close_hour == null || (Number.isInteger(value.close_hour) && value.close_hour >= 1 && value.close_hour <= 24)) &&
    (value.open_hour == null || value.close_hour == null || value.open_hour < value.close_hour) &&
    (value.closed_days == null || (value.closed_days.length < 7 && new Set(value.closed_days).size === value.closed_days.length &&
      value.closed_days.every((day) => Number.isInteger(day) && day >= 1 && day <= 7))) &&
    (value.excluded_categories?.length ?? 0) <= 64 && (value.excluded_categories ?? []).every((category) => category.length > 0 && category.length <= 80) &&
    (value.products_per_category == null || (Number.isInteger(value.products_per_category) && value.products_per_category >= 1 && value.products_per_category <= 16)) &&
    (value.width == null || (Number.isInteger(value.width) && value.width >= 8 && value.width <= 40)) &&
    (value.height == null || (Number.isInteger(value.height) && value.height >= 6 && value.height <= 40)) &&
    (value.aisle_width == null || (Number.isInteger(value.aisle_width) && value.aisle_width >= 1 && value.aisle_width <= 4)) &&
    (value.max_shelf_run == null || (Number.isInteger(value.max_shelf_run) && value.max_shelf_run >= 1 && value.max_shelf_run <= 8)) &&
    (value.checkouts == null || (Number.isInteger(value.checkouts) && value.checkouts >= 1 && value.checkouts <= 12)) &&
    (value.checkout_clearance === undefined || (Number.isInteger(value.checkout_clearance) && value.checkout_clearance >= 0 && value.checkout_clearance <= 3)) &&
    (value.dining_tables == null || (Number.isInteger(value.dining_tables) && value.dining_tables >= 0 && value.dining_tables <= 48)) &&
    (value.dining_seats === undefined || [2, 4, 6].includes(value.dining_seats)) &&
    (value.table_rotation === undefined || [0, 90].includes(value.table_rotation)) &&
    (value.table_clearance == null || (Number.isInteger(value.table_clearance) && value.table_clearance >= 1 && value.table_clearance <= 3)) &&
    (value.reserved_areas?.length ?? 0) <= 8 && (value.reserved_areas ?? []).every((area) =>
      area.label.trim().length > 0 && area.label.length <= 80 &&
      [area.x, area.y, area.width, area.height].every((n) => Number.isInteger(n) && n >= 1 && n <= 38));
}

export function templateRequest(value: TemplateChoice): GenerateLayoutRequest {
  // Explicit fields also keep the source union's `kind` out of the API request.
  return {
    template_id: value.templateId, source_setup_id: value.sourceSetupId, seed: value.seed, currency: value.currency, style: value.style,
    width: value.width, height: value.height, density: value.density, aisle_width: value.aisle_width, entrance: value.entrance, exit_position: value.exit_position, shelf_direction: value.shelf_direction,
    max_shelf_run: value.max_shelf_run,
    checkouts: value.checkouts, fixture_design: value.fixture_design, design_theme: value.design_theme,
    dining_tables: value.dining_tables, dining_seats: value.dining_seats, table_mix: value.table_mix, table_rotation: value.table_rotation, seating_zone: value.seating_zone, table_clearance: value.table_clearance,
    checkout_placement: value.checkout_placement, checkout_wall: value.checkout_wall, checkout_clearance: value.checkout_clearance, reserved_areas: value.reserved_areas, requirements: value.requirements,
    excluded_categories: value.excluded_categories,
    products_per_category: value.products_per_category,
    gate_wall: value.gate_wall,
    exit_wall: value.exit_wall,
    open_hour: value.open_hour, close_hour: value.close_hour, closed_days: value.closed_days,
  };
}

export function choiceFromGeneration(request: GenerateLayoutRequest, sourceSetupId: string): TemplateChoice {
  const { template_id, name: _name, source_setup_id: _source, ...options } = request;
  return { ...DEFAULT_TEMPLATE_CHOICE, ...options, templateId: template_id, sourceSetupId };
}

export interface BuildingFloorChoice {
  label: string;
  choice: TemplateChoice;
}

export function savedBuildingFloors(layouts: Layout[], selected: Layout | undefined): BuildingFloorChoice[] | null {
  const building = selected?.building;
  if (!selected?.generation || !building || building.floor_count < 2 || building.floor_count > 6) return null;
  const candidates = layouts.filter((layout) => layout.building?.id === building.id && layout.generation)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || b.id.localeCompare(a.id));
  const floors: BuildingFloorChoice[] = [];
  for (let level = 1; level <= building.floor_count; level++) {
    const source = selected.generation && building.level === level
      ? selected : candidates.find((layout) => layout.building?.level === level);
    if (!source?.generation || !source.building) return null;
    floors.push({ label: source.building.label, choice: choiceFromGeneration(source.generation, source.id) });
  }
  return floors;
}

export const BUILDING_PRESETS = [
  { id: "department", name: "Department store", floors: [["Ground · Beauty", "beauty_flagship"], ["Level 2 · Fashion", "fashion_boutique"], ["Level 3 · Home", "design_showroom"], ["Level 4 · Dining", "food_hall"]] },
  { id: "cafe_shop", name: "Shop with upstairs café", floors: [["Ground · Boutique", "fashion_boutique"], ["Level 2 · Book café", "book_cafe"]] },
  { id: "wellness", name: "Pharmacy & wellness", floors: [["Ground · Pharmacy", "community_pharmacy"], ["Level 2 · Wellness", "wellness_pharmacy"]] },
  { id: "dining", name: "Restaurant & coffee", floors: [["Ground · Restaurant", "quick_service"], ["Level 2 · Café", "specialty_cafe"]] },
  { id: "family", name: "Family shopping center", floors: [["Ground · Toys & hobbies", "toy_hobby_store"], ["Level 2 · Books", "bookstore"], ["Level 3 · Home", "design_showroom"], ["Level 4 · Restaurant", "family_restaurant"]] },
  { id: "tea_vintage", name: "Vintage shop & tea lounge", floors: [["Ground · Vintage", "vintage_boutique"], ["Level 2 · Tea lounge", "tea_lounge"]] },
  { id: "campus", name: "Campus hub", floors: [["Ground · Campus store", "campus_cvs"], ["Level 2 · Bookstore", "bookstore"], ["Level 3 · Dining hall", "campus_dining_hall"]] },
  { id: "family_essentials", name: "Family essentials center", floors: [["Ground · Baby & family", "baby_family_store"], ["Level 2 · Footwear", "shoe_boutique"], ["Level 3 · Family dining", "family_restaurant"]] },
  { id: "creative_living", name: "Garden, crafts & café", floors: [["Ground · Garden", "garden_center"], ["Level 2 · Arts & crafts", "art_craft_store"], ["Level 3 · Café", "specialty_cafe"]] },
  { id: "style_sound", name: "Style, sound & café", floors: [["Ground · Eyewear", "optical_shop"], ["Level 2 · Jewelry", "jewelry_boutique"], ["Level 3 · Music", "music_store"], ["Level 4 · Café", "specialty_cafe"]] },
  { id: "dining_house", name: "Dining house", floors: [["Ground · Juice bar", "juice_bar"], ["Level 2 · Noodles", "noodle_bar"], ["Level 3 · Sushi", "sushi_shop"], ["Level 4 · Pizza", "pizzeria"]] },
  { id: "neighborhood_dining", name: "Neighborhood dining center", floors: [["Ground · Ice cream", "ice_cream_parlor"], ["Level 2 · Salads", "salad_cafe"], ["Level 3 · Burgers", "burger_shop"], ["Level 4 · Korean dining", "korean_restaurant"]] },
  { id: "daily_essentials", name: "Daily essentials center", floors: [["Ground · Refill grocery", "refill_market"], ["Level 2 · Care supplies", "care_supply_store"], ["Level 3 · Fragrances", "fragrance_boutique"], ["Level 4 · Bubble tea", "bubble_tea_cafe"]] },
  { id: "design_diner", name: "Design shop & diner", floors: [["Ground · Nordic living", "nordic_lifestyle"], ["Level 2 · Retro diner", "retro_diner"]] },
  { id: "travel_dining", name: "Travel retail & dining", floors: [["Ground · Travel shopping", "airport_shopping_gallery"], ["Level 2 · Evening dining", "evening_food_court"]] },
  { id: "hospital_services", name: "Hospital services center", floors: [["Ground · Convenience & gifts", "hospital_convenience"], ["Level 2 · Pharmacy", "community_pharmacy"], ["Level 3 · Care supplies", "care_supply_store"]] },
  { id: "commuter_dining", name: "Commuter shopping & lunch", floors: [["Ground · Station food market", "station_food_market"], ["Level 2 · Office cafeteria", "office_cafeteria"]] },
  { id: "weekend_visits", name: "Weekend shopping & snacks", floors: [["Ground · Farmers' market", "weekend_farmers_market"], ["Level 2 · Books & gifts", "museum_gift_shop"], ["Level 3 · Cinema snacks", "cinema_snack_shop"]] },
] as const;

export function buildingPreset(id: string, currency = "USD"): BuildingFloorChoice[] {
  const preset = BUILDING_PRESETS.find((p) => p.id === id) ?? BUILDING_PRESETS[0];
  return preset.floors.map(([label, templateId]) => ({ label, choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId, currency } }));
}

export function validBuildingFloors(floors: BuildingFloorChoice[]): boolean {
  const labels = floors.map((f) => f.label.trim().toLowerCase());
  return floors.length >= 2 && floors.length <= 6 && new Set(labels).size === labels.length &&
    floors.every((f) => f.label.trim().length > 0 && f.label.length <= 80 && validTemplateChoice(f.choice));
}
