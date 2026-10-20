import { useQuery } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { queryKeys } from "./keys";

export function useRunStatus(projectId: string, runId: string | null) {
  return useQuery({
    queryKey: runId ? queryKeys.runStatus(projectId, runId) : ["run-status", "disabled"],
    queryFn: ({ signal }) => api.getRunStatus(projectId, runId!, signal),
    enabled: !!runId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "completed" || s === "failed" ? false : 1000;
    },
    staleTime: 0,
  });
}
