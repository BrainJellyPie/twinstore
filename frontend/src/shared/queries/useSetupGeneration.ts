import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { confirmGeneration, getGenerationStatus, getSetupGenerations, regeneratePersona } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import type { GenerationChoice, GenerationConfirm, GenerationKind, GenerationStatus } from "@/shared/types/domain";
import { queryKeys } from "@/shared/queries/keys";

const POLL_INTERVAL_MS = 3000;
export type SetupGenerationPhase = "idle" | "layout" | "persona" | "completed" | "failed";

export interface SetupGenerationState {
  phase: SetupGenerationPhase;
  kind: GenerationKind | null;
  currentGenId: string | null;
  error: string | null;
  /** What a running job is waiting for (the local model getting ready), from the server. */
  note?: string | null;
  /** Customers written so far while a generation writes them. */
  writing?: { written: number; total: number } | null;
  /** A running customer generation waits for the user to choose how many customers the model writes. */
  confirm?: GenerationConfirm | null;
  /** Sends that choice; "cancel" ends the generation as failed. */
  answer?: (choice: GenerationChoice) => void;
  answering?: boolean;
  answerError?: string | null;
  errorSource?: "status" | "generation" | null;
  loadingStatus?: boolean;
  // Read failures retry GET; only an explicit idle/failed-persona action starts generation.
  retry: () => void;
  retrying: boolean;
}

type Snapshot = Omit<SetupGenerationState, "retry" | "answer"> & { context: string };
function initialState(context: string, genId?: string | null): Snapshot {
  return { context, phase: "idle", kind: null, currentGenId: genId ?? null, error: null, errorSource: null, note: null,
    writing: null, confirm: null, answering: false, answerError: null, loadingStatus: true, retrying: false };
}

export function useSetupGeneration(projectId: string, setupId: string, initialGenId?: string | null): SetupGenerationState {
  const qc = useQueryClient();
  const context = JSON.stringify([projectId, setupId, initialGenId ?? null]);
  const [snapshot, setSnapshot] = useState(() => initialState(context, initialGenId));
  const retryRef = useRef<(() => void) | null>(null);
  const answerRef = useRef<((choice: GenerationChoice) => void) | null>(null);

  // Each project/layout owns its requests and poll timer; cleanup discards late responses.
  useEffect(() => {
    let active = true;
    let busy = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let state = initialState(context, initialGenId);
    // Jobs already answered here (or found not waiting): a status read before the answer must not ask again.
    const answered = new Set<string>();
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
      const running = status.status === "running" ? status.progress ?? null : null;
      const confirm = running && !answered.has(genId) ? running.confirm ?? null : null;
      const { written, total } = running ?? {};
      publish({ kind: status.kind, currentGenId: genId, error: null, errorSource: null,
        // An answered job's note ("Writing the customers…") is not a wait for the local model.
        note: running && !answered.has(genId) ? running.note ?? null : null,
        writing: typeof written === "number" && typeof total === "number" && total > 0 ? { written, total } : null,
        confirm, answerError: confirm ? state.answerError : null });
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
    // conflict: why a start was refused (409); shown only when this layout has no newer job to follow.
    async function readStatus(genId: string | null, conflict?: string) {
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
          if (conflict !== undefined && (!latest || (latest.status === "failed" && latest.gen_id === state.currentGenId))) {
            publish({ phase: "failed", kind: "persona", errorSource: "generation", error: conflict });
          } else if (latest) acceptStatus(latest, latest.gen_id, true);
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
        let conflict: string | undefined;
        try {
          const { gen_id } = await regeneratePersona(projectId, setupId);
          if (!active) return;
          publish({ currentGenId: gen_id, kind: "persona", phase: "persona", errorSource: null });
          schedule(gen_id, 0);
        } catch (cause) {
          // 409: another tab (or the layout chain) already started one — follow it instead of failing.
          if (cause instanceof ApiError && cause.status === 409) conflict = cause.message;
          else publish({ phase: "failed", kind: "persona", errorSource: "generation", error: cause instanceof Error ? cause.message : String(cause) });
        } finally {
          busy = false;
          if (conflict === undefined) publish({ retrying: false });
        }
        if (conflict !== undefined) void readStatus(null, conflict);
      })();
    };
    const answer = (choice: GenerationChoice) => {
      const genId = state.currentGenId;
      if (!active || !genId || !state.confirm || state.answering) return;
      publish({ answering: true, answerError: null });
      void (async () => {
        let refresh = false;
        try {
          const status = await confirmGeneration(projectId, setupId, genId, choice);
          if (!active) return;
          answered.add(genId);
          // A read in flight schedules the next poll itself; otherwise the answer's status replaces the pending poll.
          if (busy) publish({ confirm: null });
          else { clearTimeout(timer); acceptStatus(status, genId, false); }
        } catch (cause) {
          if (!active) return;
          // 409: no longer waiting (answered elsewhere, or finished) — show what it is doing now.
          if (cause instanceof ApiError && cause.status === 409) { answered.add(genId); publish({ confirm: null }); refresh = true; }
          else publish({ answerError: cause instanceof Error ? cause.message : String(cause) });
        } finally {
          publish({ answering: false });
        }
        if (refresh && !busy) { clearTimeout(timer); void readStatus(genId); }
      })();
    };
    setSnapshot(state);
    retryRef.current = retry;
    answerRef.current = answer;
    void readStatus(initialGenId ?? null);
    return () => {
      active = false;
      clearTimeout(timer);
      if (retryRef.current === retry) retryRef.current = null;
      if (answerRef.current === answer) answerRef.current = null;
    };
  }, [context, projectId, setupId, initialGenId, qc]);

  const retry = useCallback(() => { retryRef.current?.(); }, []);
  const answer = useCallback((choice: GenerationChoice) => { answerRef.current?.(choice); }, []);
  const current = snapshot.context === context ? snapshot : initialState(context, initialGenId);
  return { ...current, retry, answer };
}
