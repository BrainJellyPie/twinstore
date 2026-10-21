import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getGenerationStatus, getSetupGenerations, regeneratePersona } from "@/shared/api/client";
import type { GenerationKind, GenerationStatus } from "@/shared/types/domain";
import { queryKeys } from "@/shared/queries/keys";

const POLL_INTERVAL_MS = 3000;
export type SetupGenerationPhase = "idle" | "layout" | "persona" | "completed" | "failed";

export interface SetupGenerationState {
  phase: SetupGenerationPhase;
  kind: GenerationKind | null;
  currentGenId: string | null;
  error: string | null;
  errorSource?: "status" | "generation" | null;
  loadingStatus?: boolean;
  // Read failures retry GET; only an explicit idle/failed-persona action starts generation.
  retry: () => void;
  retrying: boolean;
}

type Snapshot = Omit<SetupGenerationState, "retry"> & { context: string };
function initialState(context: string, genId?: string | null): Snapshot {
  return { context, phase: "idle", kind: null, currentGenId: genId ?? null, error: null, errorSource: null, loadingStatus: true, retrying: false };
}

export function useSetupGeneration(projectId: string, setupId: string, initialGenId?: string | null): SetupGenerationState {
  const qc = useQueryClient();
  const context = JSON.stringify([projectId, setupId, initialGenId ?? null]);
  const [snapshot, setSnapshot] = useState(() => initialState(context, initialGenId));
  const retryRef = useRef<(() => void) | null>(null);

  // Each project/layout owns its requests and poll timer; cleanup discards late responses.
  useEffect(() => {
    let active = true;
    let busy = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let state = initialState(context, initialGenId);
    const publish = (patch: Partial<Snapshot>) => {
      if (!active) return;
      state = { ...state, ...patch };
      setSnapshot(state);
    };
    const refreshSetup = () => {
      void qc.invalidateQueries({ queryKey: queryKeys.project(projectId) });
      void qc.invalidateQueries({ queryKey: queryKeys.setup(projectId, setupId) });
    };
    const schedule = (genId: string, delay: number) => {
      timer = setTimeout(() => { void readStatus(genId); }, delay);
    };
    const acceptStatus = (status: GenerationStatus, genId: string, fromHistory: boolean) => {
      publish({ kind: status.kind, currentGenId: genId, error: null, errorSource: null });
      if (status.status === "failed") {
        publish({ phase: "failed", error: status.error ?? "Generation failed", errorSource: "generation" });
      } else if (status.status === "completed") {
        if (status.kind === "layout" && status.progress?.next_gen_id) {
          publish({ currentGenId: status.progress.next_gen_id, kind: "persona", phase: "persona" });
          schedule(status.progress.next_gen_id, 0);
        } else {
          publish({ phase: status.kind === "persona" ? "completed" : "idle" });
          refreshSetup();
        }
      } else {
        publish({ phase: status.kind });
        schedule(genId, fromHistory ? 0 : POLL_INTERVAL_MS);
      }
    };
    async function readStatus(genId: string | null) {
      if (!active || busy) return;
      busy = true;
      try {
        if (genId) {
          const status = await getGenerationStatus(projectId, setupId, genId);
          if (active) acceptStatus(status, genId, false);
        } else {
          const list = await getSetupGenerations(projectId, setupId, { active_only: false });
          if (!active) return;
          const latest = list[0];
          if (latest) acceptStatus(latest, latest.gen_id, true);
          else publish({ phase: "idle", kind: null, currentGenId: null, error: null, errorSource: null });
        }
      } catch (cause) {
        publish({ phase: "failed", errorSource: "status", error: cause instanceof Error ? cause.message : String(cause) });
      } finally {
        busy = false;
        publish({ loadingStatus: false, retrying: false });
      }
    }
    const retry = () => {
      if (!active || busy || state.loadingStatus) return;
      if (state.errorSource === "status") {
        publish({ loadingStatus: true, retrying: true, error: null });
        void readStatus(state.currentGenId);
        return;
      }
      if (state.phase === "failed" && state.kind === "layout") {
        throw new Error("Layout regeneration is not supported — please create a new project");
      }
      if (state.phase !== "idle" && state.phase !== "failed") return;
      busy = true;
      publish({ retrying: true, error: null });
      void (async () => {
        try {
          const { gen_id } = await regeneratePersona(projectId, setupId);
          if (!active) return;
          publish({ currentGenId: gen_id, kind: "persona", phase: "persona", errorSource: null });
          schedule(gen_id, 0);
        } catch (cause) {
          publish({ phase: "failed", kind: "persona", errorSource: "generation", error: cause instanceof Error ? cause.message : String(cause) });
        } finally {
          busy = false;
          publish({ retrying: false });
        }
      })();
    };
    setSnapshot(state);
    retryRef.current = retry;
    void readStatus(initialGenId ?? null);
    return () => {
      active = false;
      clearTimeout(timer);
      if (retryRef.current === retry) retryRef.current = null;
    };
  }, [context, projectId, setupId, initialGenId, qc]);

  const retry = useCallback(() => { retryRef.current?.(); }, []);
  const current = snapshot.context === context ? snapshot : initialState(context, initialGenId);
  return { ...current, retry };
}
