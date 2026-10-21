import type { GenerateLayoutRequest, LayoutOptions } from "@/shared/api/client";

export interface TemplateChoice extends LayoutOptions {
  templateId: string;
  seed: number;
  currency: string;
  requirements?: string;
}

export const DEFAULT_TEMPLATE_CHOICE: TemplateChoice = {
  templateId: "urban_cvs", seed: 0, currency: "USD", style: null,
  density: "balanced", entrance: "left", checkouts: 1, fixture_design: "mixed",
};

export const LAYOUT_STYLES = [
  ["aisles", "Parallel aisles"], ["loop", "Racetrack loop"], ["spine", "Central spine"],
  ["free_flow", "Free-flow islands"], ["perimeter", "Open center / perimeter"], ["showroom", "Showroom groups"],
] as const;

export function validTemplateChoice(value: TemplateChoice): boolean {
  return !!value.templateId && Number.isSafeInteger(value.seed) &&
    (value.width == null || (Number.isInteger(value.width) && value.width >= 8 && value.width <= 40)) &&
    (value.height == null || (Number.isInteger(value.height) && value.height >= 6 && value.height <= 40));
}

export function templateRequest(value: TemplateChoice): GenerateLayoutRequest {
  // Explicit fields also keep the source union's `kind` out of the API request.
  return {
    template_id: value.templateId, seed: value.seed, currency: value.currency, style: value.style,
    width: value.width, height: value.height, density: value.density, entrance: value.entrance,
    checkouts: value.checkouts, fixture_design: value.fixture_design, requirements: value.requirements,
  };
}
