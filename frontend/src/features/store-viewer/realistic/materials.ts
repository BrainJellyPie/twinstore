// PBR materials for the procedural store shell and fixtures.

import * as THREE from "three";
import { SHELL_COLORS, type GraphicsQuality } from "./constants";
import type { StoreDesign } from "@/shared/types/domain";
import { INTERIOR_DESIGNS } from "./designThemes";
import type { MatKey } from "./staticBuilder";
import { canvasTexture } from "./atlasMaterial";
import { createAoCanvas, createWoodCanvas } from "./canvasArt";
import type { ScannedMaterialMaps } from "./useScannedMaterial";

export type ShellMaterials = Record<MatKey, THREE.Material>;

function std(color: string, roughness: number, metalness = 0, extra: THREE.MeshStandardMaterialParameters = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
}

function emissive(color: string, intensity: number) {
  return new THREE.MeshStandardMaterial({
    color: "#000000",
    emissive: color,
    emissiveIntensity: intensity,
    roughness: 1,
    metalness: 0,
  });
}

// `partEnv`: environment map applied only to the small reflective parts
// (ENV_KEYS) when the scene-wide environment is off.
export function createShellMaterials(
  quality: GraphicsQuality,
  signTexture: THREE.Texture,
  partEnv: THREE.Texture | null = null,
  woodMaps: ScannedMaterialMaps | null = null,
  designTheme: StoreDesign = "classic",
): ShellMaterials {
  // Material-owned clones keep hook cleanup and shell rebuilds independent.
  const wood = woodMaps?.map.clone() ?? canvasTexture(createWoodCanvas(), { anisotropy: 1 });
  const ao = canvasTexture(createAoCanvas(), { anisotropy: 1 });
  ao.colorSpace = THREE.NoColorSpace;

  const glass: THREE.Material =
    quality === "high"
      ? // Reflective glass (environment-lit). Transmission was tried: it blurs the
        // stock behind fridge doors and costs an extra scene pass.
        new THREE.MeshStandardMaterial({
          color: "#e4f2f6",
          roughness: 0.04,
          metalness: 0,
          transparent: true,
          opacity: 0.14,
          envMapIntensity: 1.4,
          side: THREE.DoubleSide,
          depthWrite: false,
        })
      : // Unlit tinted glass: large panes are expensive to shade under software GL.
        new THREE.MeshBasicMaterial({
          color: "#d9edf3",
          transparent: true,
          opacity: 0.2,
          side: THREE.DoubleSide,
          depthWrite: false,
        });

  const sign = new THREE.MeshStandardMaterial({
    map: signTexture,
    emissiveMap: signTexture,
    emissive: "#ffffff",
    emissiveIntensity: 0.55,
    roughness: 0.85,
    metalness: 0,
    envMapIntensity: 0.25,
  });

  const palette = INTERIOR_DESIGNS[designTheme];
  const mats: ShellMaterials = {
    wall: std(palette.wall, 0.92),
    band: std(palette.band, 0.6),
    bandLine: std(palette.accent, 0.5),
    trim: std("#d9dcdf", 0.5, 0.1),
    cut: std(SHELL_COLORS.cut, 0.9),
    plinth: std(palette.plinth, 0.95),
    // Powder coating is a dielectric even when the substrate is steel.
    metalWhite: std(palette.shelf, 0.42, 0),
    metalGrey: std("#9ea6ae", 0.35, 0.6),
    backPanel: std(palette.backing, 0.6, 0.15),
    kick: std("#5c636b", 0.55, 0.35),
    rail: std("#cfd4d9", 0.35, 0.2),
    darkMetal: std("#24282d", 0.38, 0.65),
    fridgeShell: std("#2d3238", 0.45, 0.5),
    fridgeInterior: std("#f2f5f7", 0.5, 0.05, { emissive: "#e8f4ff", emissiveIntensity: 0.18 }),
    wire: std("#b8c0c8", 0.35, 0.75),
    chrome: std("#e8ebee", 0.12, 1),
    led: emissive("#f4fbff", 5),
    glass,
    // Horizontal freezer lids: thinner reflection so the stock below reads.
    lidGlass: new THREE.MeshStandardMaterial({
      color: "#e6f3f7",
      roughness: 0.08,
      metalness: 0,
      transparent: true,
      opacity: 0.08,
      envMapIntensity: 0.7,
      depthWrite: false,
    }),
    freezerBody: std("#f6f7f8", 0.32, 0.05),
    freezerInterior: std("#dbe9f3", 0.5, 0.05, { emissive: "#dff0ff", emissiveIntensity: 0.12 }),
    bumper: std("#8a939c", 0.4, 0.4),
    wood: std(palette.wood, woodMaps ? 1 : 0.62, 0, {
      map: wood,
      roughnessMap: woodMaps?.roughnessMap.clone() ?? null,
      normalMap: woodMaps?.normalMap?.clone() ?? null,
      normalScale: new THREE.Vector2(0.3, 0.3),
    }),
    counterTop: quality === "high"
      ? new THREE.MeshPhysicalMaterial({ color: palette.counter, roughness: 0.32, clearcoat: 0.28, clearcoatRoughness: 0.2 })
      : std(palette.counter, 0.32),
    black: std("#17191c", 0.45, 0.2),
    screen: emissive("#4f8fe8", 0.9),
    mat: std("#2f3337", 0.98),
    aluminum: std("#b7bdc4", 0.32, 0.85),
    pavement: std("#bdbab4", 0.9),
    curb: std("#9b9893", 0.9),
    ceiling: std(palette.ceiling, 0.95),
    ceilingLight: emissive("#ffffff", 4.5),
    exitSign: emissive("#16c060", 1.5),
    plant: std("#3f7d3a", 0.8),
    pot: std("#3b3f44", 0.6, 0.2),
    sign,
    ao: new THREE.MeshBasicMaterial({
      map: ao,
      color: "#000000",
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    }),
  };
  // Photo mode converts materials by role (glass, emitters, contact-shadow decal).
  for (const [key, m] of Object.entries(mats)) m.name = key;
  if (partEnv) {
    for (const key of ENV_KEYS) {
      const m = mats[key] as THREE.MeshStandardMaterial;
      if (m.isMeshStandardMaterial) m.envMap = partEnv;
    }
  }
  return mats;
}

// Materials that should not cast shadows (light-transmitting or emissive parts,
// and the fridge cabinet so its LED-lit interior is not shadowed by the canopy).
export const NO_CAST = new Set<MatKey>([
  "glass",
  "lidGlass",
  "led",
  "ceiling",
  "ceilingLight",
  "sign",
  "ao",
  "screen",
  "fridgeShell",
  "fridgeInterior",
  "plinth",
  "pavement",
  "mat",
  "exitSign",
]);

// Small reflective parts that keep the environment map on "medium".
export const ENV_KEYS: MatKey[] = ["chrome", "aluminum", "darkMetal", "metalGrey", "wire", "bumper", "fridgeShell", "lidGlass", "counterTop"];

export const NO_RECEIVE = new Set<MatKey>(["glass", "lidGlass", "led", "ceilingLight", "ao", "screen", "exitSign", "sign"]);

export function disposeMaterials(mats: ShellMaterials) {
  for (const m of Object.values(mats)) {
    const sm = m as THREE.MeshStandardMaterial;
    // The sign atlas belongs to RealisticStore and survives material rebuilds.
    if (m !== mats.sign) sm.map?.dispose();
    sm.roughnessMap?.dispose();
    sm.normalMap?.dispose();
    m.dispose();
  }
}
