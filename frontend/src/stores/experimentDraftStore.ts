import { create } from "zustand";

import type { ExperimentRequest } from "@/shared/api/marketing";

/** An A/B test drafted on another page (an online variant's prices), opened in the marketing studio's builder. */
interface ExperimentDraftState {
  pending: { projectId: string; req: ExperimentRequest } | null;
  send: (projectId: string, req: ExperimentRequest) => void;
  /** The pending draft when it is for this project; it is cleared once taken. */
  take: (projectId: string) => ExperimentRequest | null;
}

export const useExperimentDraft = create<ExperimentDraftState>((set, get) => ({
  pending: null,
  send: (projectId, req) => set({ pending: { projectId, req } }),
  take: (projectId) => {
    const p = get().pending;
    if (!p || p.projectId !== projectId) return null;
    set({ pending: null });
    return p.req;
  },
}));
