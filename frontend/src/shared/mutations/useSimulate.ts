import { useMutation, useQueryClient } from "@tanstack/react-query";
import { startRun, type RunOptions } from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";

interface SimulateArgs {
  projectId: string;
  setupId: string;
  options?: RunOptions;
}

// Starts a run and returns as soon as the backend accepted it. Progress, completion
// and failure are then tracked by RunningView through the run status endpoint, so
// the UI can show live progress instead of a blocking spinner.
export function useSimulate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, setupId, options }: SimulateArgs) =>
      startRun(projectId, setupId, options ?? {}),
    onSuccess: (_run, { projectId, setupId }) => {
      void qc.invalidateQueries({ queryKey: queryKeys.runs(projectId, setupId) });
      void qc.invalidateQueries({ queryKey: queryKeys.projectRuns(projectId) });
    },
  });
}
