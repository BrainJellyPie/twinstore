import { useQuery } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { queryKeys } from "@/shared/queries/keys";

export function useAvailableModels(enabled = true) {
  return useQuery({
    queryKey: queryKeys.models(),
    queryFn: ({ signal }) => api.getModels(signal),
    staleTime: 60_000,
    enabled,
  });
}

export function useEngines() {
  return useQuery({
    queryKey: queryKeys.engines(),
    queryFn: ({ signal }) => api.getEngines(signal),
    staleTime: 5 * 60 * 1000,
  });
}

// Every run of the project, across layouts — the A/B compare picker needs runs
// from different setups.
export function useProjectRuns(projectId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.projectRuns(projectId),
    queryFn: ({ signal }) => api.getRuns(projectId, undefined, signal),
    enabled,
    refetchInterval: (q) =>
      q.state.data?.some((r) => r.status === "running" || r.status === "pending") ? 2000 : false,
  });
}

/** How the layout's store is run, when saved (null otherwise). */
export function useLayoutOperations(projectId: string, setupId: string) {
  return useQuery({
    queryKey: queryKeys.layoutOperations(projectId, setupId),
    queryFn: async ({ signal }) => (await api.getLayoutOperations(projectId, setupId, signal)).operations,
    staleTime: 30_000,
    retry: false,
  });
}

/** The shared store's stock-outs and till lines; `null` for runs whose shoppers each had the store alone. */
export function useRunOperations(projectId: string, runId: string) {
  return useQuery({
    queryKey: queryKeys.runOperations(projectId, runId),
    queryFn: async ({ signal }) => {
      try {
        return await api.getRunOperations(projectId, runId, signal);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    staleTime: Infinity,
    retry: false,
  });
}

export function useRunDiagnostics(projectId: string, runId: string) {
  return useQuery({
    queryKey: queryKeys.runDiagnostics(projectId, runId),
    queryFn: ({ signal }) => api.getRunDiagnostics(projectId, runId, signal),
    staleTime: Infinity,
    retry: false,
  });
}

export function useCompare(projectId: string, runA: string | null, runB: string | null) {
  return useQuery({
    queryKey: queryKeys.compare(projectId, runA ?? "", runB ?? ""),
    queryFn: ({ signal }) => api.compareRuns(projectId, runA!, runB!, signal),
    enabled: !!runA && !!runB && runA !== runB,
    staleTime: Infinity,
    retry: false,
  });
}
