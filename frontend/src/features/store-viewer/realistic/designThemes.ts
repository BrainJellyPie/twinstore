import type { StoreDesign } from "@/shared/types/domain";

export interface InteriorPalette {
  label: string;
  wall: string;
  band: string;
  accent: string;
  shelf: string;
  backing: string;
  counter: string;
  wood: string;
  floor: string;
  ceiling: string;
  plinth: string;
}

// A palette belongs to the layout, independently of the app's light/dark mode.
export const INTERIOR_DESIGNS: Record<StoreDesign, InteriorPalette> = {
  classic: { label: "Classic retail", wall: "#f2f0ea", band: "#0f6e78", accent: "#f4c542", shelf: "#eceef0", backing: "#e1e4e7", counter: "#e9e6df", wood: "#ffffff", floor: "#ffffff", ceiling: "#ffffff", plinth: "#8d949c" },
  warm: { label: "Warm wood", wall: "#efe2d0", band: "#8f6245", accent: "#dbb280", shelf: "#dac5a7", backing: "#e6d6bd", counter: "#d5b58e", wood: "#d2ae82", floor: "#e8d7bf", ceiling: "#faf0df", plinth: "#8b715d" },
  minimal: { label: "Minimal white", wall: "#fafafa", band: "#aab9c1", accent: "#e8ecef", shelf: "#f8fafc", backing: "#eef2f6", counter: "#f4f5f6", wood: "#e6e4df", floor: "#f2f5f8", ceiling: "#ffffff", plinth: "#c0c8cf" },
  industrial: { label: "Industrial graphite", wall: "#b6b8ba", band: "#333c46", accent: "#d69d46", shelf: "#697581", backing: "#a0a9b1", counter: "#687078", wood: "#9a7a58", floor: "#b7b9b9", ceiling: "#cdd1d4", plinth: "#49515b" },
  botanical: { label: "Botanical sage", wall: "#e4eadf", band: "#446951", accent: "#c8b884", shelf: "#cbd6bf", backing: "#dee6d5", counter: "#c3c9ad", wood: "#ceb88e", floor: "#dfe4d4", ceiling: "#f4f5e9", plinth: "#7c8d75" },
  luxury: { label: "Luxury charcoal & brass", wall: "#d7d2ca", band: "#302d32", accent: "#c4a160", shelf: "#55515a", backing: "#aaa3a0", counter: "#eee4d2", wood: "#ad855f", floor: "#d7d0c5", ceiling: "#ece7df", plinth: "#4e4645" },
};
