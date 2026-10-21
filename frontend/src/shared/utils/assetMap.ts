import type { Rack } from "../types/domain";

const MARKET = "/assets/market";
const CHARACTERS = "/assets/characters";

// Deterministic id hash — same rack always picks the same variant.
function hashString(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = (hash * 31 + s.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

const SHELF_VARIANT_MAP: Record<"a" | "b" | "c", string> = {
  a: "shelf-boxes.glb",
  b: "shelf-bags.glb",
  c: "shelf-end.glb",
};

const FRIDGE_VARIANT_MAP: Record<"a" | "b", string> = {
  a: "freezers-standing.glb",
  b: "freezer.glb",
};

export function marketAssetFor(rack: Rack): string | null {
  switch (rack.type) {
    case "fridge": {
      const variant = rack.design_variant === "b" ? "b" : "a";
      return `${MARKET}/${FRIDGE_VARIANT_MAP[variant]}`;
    }
    case "shelf": {
      const variant = rack.design_variant ?? "a";
      return `${MARKET}/${SHELF_VARIANT_MAP[variant]}`;
    }
    case "counter": {
      return `${MARKET}/cash-register.glb`;
    }
    case "display":
      return `${MARKET}/freezer.glb`;
    default:
      return null;
  }
}

const FEMALE_FILES = [
  "character-female-a.glb",
  "character-female-b.glb",
  "character-female-c.glb",
  "character-female-d.glb",
  "character-female-e.glb",
  "character-female-f.glb",
];

const MALE_FILES = [
  "character-male-a.glb",
  "character-male-b.glb",
  "character-male-c.glb",
  "character-male-d.glb",
  "character-male-e.glb",
  "character-male-f.glb",
];

const CHARACTER_FILES = [...FEMALE_FILES, ...MALE_FILES];

export function characterAssetFor(personaId: string, gender?: string): string {
  const pool = gender === "Female" ? FEMALE_FILES : gender === "Male" ? MALE_FILES : CHARACTER_FILES;
  const idx = hashString(personaId) % pool.length;
  return `${CHARACTERS}/${pool[idx]}`;
}

export const ALL_MARKET_ASSETS = [
  `${MARKET}/freezer.glb`,
  `${MARKET}/freezers-standing.glb`,
  `${MARKET}/shelf-boxes.glb`,
  `${MARKET}/shelf-bags.glb`,
  `${MARKET}/shelf-end.glb`,
  `${MARKET}/cash-register.glb`,
  `${MARKET}/display-fruit.glb`,
  `${MARKET}/display-bread.glb`,
];

export const ALL_CHARACTER_ASSETS = CHARACTER_FILES.map((f) => `${CHARACTERS}/${f}`);
