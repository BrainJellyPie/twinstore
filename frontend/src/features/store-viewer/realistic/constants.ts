// Shared dimensions for the "Realistic" graphics mode.
//
// World units: one grid tile = 1 unit. Realistic mode treats a tile as 1.25 m, so
// metric sizes are multiplied by M (units per metre) before they reach the scene.

export const M = 0.8;

// Packages are drawn ~10% larger than life so labels stay legible from the
// isometric camera without looking toy-like up close.
export const PRODUCT_SCALE = 1.1;

export const WALL_HEIGHT = 2.3;
export const CUTAWAY_HEIGHT = 0.3;
export const WALL_THICKNESS = 0.12;
export const CEILING_HEIGHT = 2.28;
export const FLOOR_SLAB = 0.22;

// Scale the persona group and its labels for adult proportions. Photographic
// bodies compensate for this parent scale and keep their authored metric height.
export const PERSONA_SCALE = 2.35;

// Eye height of the shopper-view camera, per graphics mode (classic personas are small).
export const EYE_HEIGHT = { realistic: 1.24, classic: 0.52 } as const;

export type GraphicsQuality = "medium" | "high";

// "high" additionally mounts RealisticEffects (GTAO + bloom), planar floor
// reflections and the scene-wide environment map.
export interface QualityPreset {
  shadowMapSize: number;
  shadowRadius: number;
  // Max product rows stocked behind the front facing.
  maxRows: number;
  dprMax: number;
  // Re-render the shadow map every N frames while shoppers move (static store:
  // once). 1 = every frame.
  shadowEvery: number;
}

export const QUALITY_PRESETS: Record<GraphicsQuality, QualityPreset> = {
  medium: {
    shadowMapSize: 1024,
    shadowRadius: 3,
    maxRows: 3,
    dprMax: 1.5,
    shadowEvery: 3,
  },
  high: {
    shadowMapSize: 2048,
    shadowRadius: 5,
    maxRows: 4,
    dprMax: 2,
    shadowEvery: 2,
  },
};

// Palette for the store shell. Generic retail colours, no brand identity.
export const SHELL_COLORS = {
  wall: "#f2f0ea",
  band: "#0f6e78",
  bandLine: "#f4c542",
  skirting: "#6f7780",
  cut: "#3a4047",
  plinth: "#8d949c",
} as const;
