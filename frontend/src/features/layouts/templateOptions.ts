import type { GenerateLayoutRequest, LayoutOptions } from "@/shared/api/client";
import type { Layout } from "./hooks/useLayouts";

export interface TemplateChoice extends LayoutOptions {
  templateId: string;
  sourceSetupId?: string;
  seed: number;
  currency: string;
  requirements?: string;
}

export const DEFAULT_TEMPLATE_CHOICE: TemplateChoice = {
  templateId: "urban_cvs", seed: 0, currency: "USD", style: null,
  density: "balanced", entrance: "left", exit_position: "shared", checkouts: null, fixture_design: "mixed", design_theme: null, dining_tables: null,
  checkout_placement: "auto", seating_zone: "auto", reserved_areas: [], shelf_direction: "horizontal", table_clearance: 1,
};

export const LAYOUT_STYLES = [
  ["aisles", "Parallel aisles"], ["loop", "Racetrack loop"], ["spine", "Central spine"],
  ["free_flow", "Free-flow islands"], ["perimeter", "Open center / perimeter"], ["showroom", "Showroom groups"],
] as const;

export function validTemplateChoice(value: TemplateChoice): boolean {
  return !!value.templateId && Number.isSafeInteger(value.seed) &&
    (value.width == null || (Number.isInteger(value.width) && value.width >= 8 && value.width <= 40)) &&
    (value.height == null || (Number.isInteger(value.height) && value.height >= 6 && value.height <= 40)) &&
    (value.checkouts == null || (Number.isInteger(value.checkouts) && value.checkouts >= 1 && value.checkouts <= 12)) &&
    (value.dining_tables == null || (Number.isInteger(value.dining_tables) && value.dining_tables >= 0 && value.dining_tables <= 12)) &&
    (value.table_clearance == null || (Number.isInteger(value.table_clearance) && value.table_clearance >= 1 && value.table_clearance <= 3)) &&
    (value.reserved_areas?.length ?? 0) <= 8 && (value.reserved_areas ?? []).every((area) =>
      area.label.trim().length > 0 && area.label.length <= 80 &&
      [area.x, area.y, area.width, area.height].every((n) => Number.isInteger(n) && n >= 1 && n <= 38));
}

export function templateRequest(value: TemplateChoice): GenerateLayoutRequest {
  // Explicit fields also keep the source union's `kind` out of the API request.
  return {
    template_id: value.templateId, source_setup_id: value.sourceSetupId, seed: value.seed, currency: value.currency, style: value.style,
    width: value.width, height: value.height, density: value.density, entrance: value.entrance, exit_position: value.exit_position, shelf_direction: value.shelf_direction,
    checkouts: value.checkouts, fixture_design: value.fixture_design, design_theme: value.design_theme,
    dining_tables: value.dining_tables, seating_zone: value.seating_zone, table_clearance: value.table_clearance,
    checkout_placement: value.checkout_placement, reserved_areas: value.reserved_areas, requirements: value.requirements,
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
