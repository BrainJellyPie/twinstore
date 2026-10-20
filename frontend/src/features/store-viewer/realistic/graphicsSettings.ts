// Realistic-mode settings that are local to the 3D viewer: render quality and the
// list of shoppers the shopper-view camera can follow (published by the camera,
// read by the HUD).

import { create } from "zustand";
import type { GraphicsQuality } from "./constants";

const QUALITY_KEY = "parastore.gfxQuality";

function readQuality(): GraphicsQuality {
  try {
    const url = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("gfxq") : null;
    if (url === "high" || url === "medium") return url;
    const v = typeof localStorage !== "undefined" ? localStorage.getItem(QUALITY_KEY) : null;
    return v === "high" ? "high" : "medium";
  } catch {
    return "medium";
  }
}

interface RealisticSettingsState {
  quality: GraphicsQuality;
  activeShopperIds: string[];
  // False while the realistic scene is being built / compiled (first frame).
  realisticReady: boolean;
  setQuality: (q: GraphicsQuality) => void;
  setRealisticReady: (ready: boolean) => void;
  setActiveShopperIds: (ids: string[]) => void;
}

export const useRealisticSettings = create<RealisticSettingsState>((set) => ({
  quality: readQuality(),
  activeShopperIds: [],
  realisticReady: false,
  setRealisticReady: (ready) => set({ realisticReady: ready }),
  setQuality: (quality) => {
    try {
      localStorage.setItem(QUALITY_KEY, quality);
    } catch {
      // Storage unavailable (private mode) — keep the in-memory value.
    }
    set({ quality });
  },
  setActiveShopperIds: (ids) => set({ activeShopperIds: ids }),
}));

export function sameIds(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}
