// Who runs the shoppers right now: polled quickly while a local model downloads or starts.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/shared/api/client";
import type { ModelSetup } from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";

const BUSY = new Set(["preparing", "downloading", "starting"]);

export function isPreparing(setup: ModelSetup | undefined): boolean {
  return !!setup && BUSY.has(setup.local.state);
}

export function useModelSetup() {
  const qc = useQueryClient();
  return useQuery({
    queryKey: queryKeys.modelSetup(),
    queryFn: async ({ signal }) => {
      const before = qc.getQueryData<ModelSetup>(queryKeys.modelSetup());
      const setup = await api.getModelSetup(signal);
      // The run dialog's engine readiness depends on whether the local model is up.
      if (before && (before.local.state === "ready") !== (setup.local.state === "ready")) {
        void qc.invalidateQueries({ queryKey: queryKeys.engines() });
      }
      return setup;
    },
    refetchInterval: (query) => (isPreparing(query.state.data) ? 2_000 : 60_000),
    retry: false,
  });
}

export function useLocalModelControl() {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: queryKeys.modelSetup() });
    void qc.invalidateQueries({ queryKey: queryKeys.providers() });
    void qc.invalidateQueries({ queryKey: queryKeys.models() });
    void qc.invalidateQueries({ queryKey: queryKeys.engines() });
  };
  const start = useMutation({ mutationFn: api.startLocalModel, onSettled: refresh });
  const stop = useMutation({ mutationFn: api.stopLocalModel, onSettled: refresh });
  return { start, stop };
}
