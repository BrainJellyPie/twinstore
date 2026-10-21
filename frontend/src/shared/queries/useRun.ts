import { useSuspenseQuery } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import type { Store, CustomerResult, Persona } from "@/shared/types/domain";
import type { RunSummary } from "@/shared/api/client";
import { queryKeys } from "./keys";
import { normalizeHeatmap } from "@/shared/utils/heatmap";

export interface RunHeatmaps {
  footfall: number[][];
  dwell: number[][] | null; // null for runs made before v0.2
  traffic: number[][];
}

export interface RunBundle {
  runId: string;
  store: Store;
  personas: Persona[];
  customers: CustomerResult[];
  // Footfall heatmap (kept for components that only know one layer).
  heatmap: number[][];
  heatmaps: RunHeatmaps;
  summary: RunSummary;
}

export async function fetchRunBundle(
  projectId: string,
  runId: string,
  signal?: AbortSignal,
): Promise<RunBundle> {
  const [customers, summaryData, heatmapData, serverStore] = await Promise.all([
    api.getRunTimeline(projectId, runId, signal),
    api.getRunSummary(projectId, runId, signal),
    api.getRunHeatmap(projectId, runId, signal),
    api.getRunStore(projectId, runId, signal),
  ]);
  const footfall = normalizeHeatmap(heatmapData.persona_heatmap);
  const dwell = heatmapData.dwell_heatmap?.length ? normalizeHeatmap(heatmapData.dwell_heatmap) : null;
  return {
    runId,
    store: serverStore,
    personas: Object.values(summaryData.personas),
    customers,
    heatmap: footfall,
    heatmaps: { footfall, dwell, traffic: heatmapData.pathcalc_heatmap },
    summary: summaryData.summary,
  };
}

// Run results are immutable; uploaded SKU photos decorate their store response.
// Image imports invalidate the project prefix. gcTime drops inactive runs after 30min.
export function useRun(projectId: string, runId: string) {
  return useSuspenseQuery({
    queryKey: queryKeys.run(projectId, runId),
    queryFn: ({ signal }) => fetchRunBundle(projectId, runId, signal),
    staleTime: Infinity,
    gcTime: 1000 * 60 * 30,
  });
}
