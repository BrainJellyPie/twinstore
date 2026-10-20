import { create } from "zustand";

export type DashboardTab = "dashboard" | "settings";

// Which per-tile layer the floor heatmap shows.
// footfall = timeline events per tile, dwell = seconds spent per tile,
// traffic = model-predicted shortest-path load between racks (layout only).
export type HeatmapMode = "off" | "footfall" | "dwell" | "traffic";

interface SimulationState {
  highlightId: string | null;
  heatmapMode: HeatmapMode;
  rackOverlayOn: boolean;
  activeTab: DashboardTab;
  // Currently selected setup (layout) id. Backend has no "active layout" concept —
  // this is purely local UI state and is not persisted across sessions.
  selectedSetupId: string | null;
  // Run shown in playback. null → the resolver picks the latest finalized run.
  viewRunId: string | null;
  // Message of the last run that failed, shown in the ready view instead of crashing.
  lastRunError: string | null;
  // ISO currency of the run being viewed (prices are integers in its minor unit).
  currency: string;

  hoveredRackId: string | null;
  selectedRackId: string | null;

  setHighlightId: (id: string | null) => void;
  setHeatmapMode: (mode: HeatmapMode) => void;
  toggleRackOverlay: () => void;
  setActiveTab: (tab: DashboardTab) => void;
  setSelectedSetupId: (id: string | null) => void;
  setViewRunId: (id: string | null) => void;
  setLastRunError: (msg: string | null) => void;
  setCurrency: (code: string) => void;
  setHoveredRackId: (id: string | null) => void;
  setSelectedRackId: (id: string | null) => void;
  reset: () => void;
}

const INITIAL = {
  highlightId: null,
  heatmapMode: "off" as HeatmapMode,
  rackOverlayOn: false,
  activeTab: "dashboard" as DashboardTab,
  selectedSetupId: null,
  viewRunId: null,
  lastRunError: null,
  currency: "USD",
  hoveredRackId: null,
  selectedRackId: null,
};

export const useSimulationStore = create<SimulationState>((set) => ({
  ...INITIAL,

  setHighlightId: (id) => set({ highlightId: id }),
  setHeatmapMode: (mode) => set({ heatmapMode: mode }),
  toggleRackOverlay: () => set((s) => ({ rackOverlayOn: !s.rackOverlayOn })),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setSelectedSetupId: (id) => set({ selectedSetupId: id, viewRunId: null }),
  setViewRunId: (id) => set({ viewRunId: id }),
  setLastRunError: (msg) => set({ lastRunError: msg }),
  setCurrency: (code) => set({ currency: code }),
  setHoveredRackId: (id) => set({ hoveredRackId: id }),
  setSelectedRackId: (id) => set({ selectedRackId: id }),
  reset: () => set(INITIAL),
}));
