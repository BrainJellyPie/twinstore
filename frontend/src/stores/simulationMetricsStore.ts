import { create } from "zustand";
import type { SkuSales } from "@/features/playback/utils/playback";
import type { RackMetric } from "@/features/playback/utils/eventQueue";

interface SimulationMetricsState {
  currentDay: number;
  currentMinute: number;
  entered: number;
  exited: number;
  inStore: number;
  revenue: number;
  impulseRevenue: number;
  paidCount: number;
  skuSales: SkuSales[];
  rackMetrics: RackMetric[];
  finished: boolean;

  setCurrentMinute: (minute: number) => void;
  setMetrics: (patch: Partial<Omit<SimulationMetricsState, "setCurrentMinute" | "setMetrics" | "reset">>) => void;
  reset: () => void;
}

const INITIAL: Omit<SimulationMetricsState, "setCurrentMinute" | "setMetrics" | "reset"> = {
  currentDay: 1,
  currentMinute: 0,
  entered: 0,
  exited: 0,
  inStore: 0,
  revenue: 0,
  impulseRevenue: 0,
  paidCount: 0,
  skuSales: [],
  rackMetrics: [],
  finished: false,
};

export const useSimulationMetricsStore = create<SimulationMetricsState>((set) => ({
  ...INITIAL,
  setCurrentMinute: (minute) => set({ currentMinute: minute }),
  setMetrics: (patch) => set(patch),
  reset: () => set(INITIAL),
}));
