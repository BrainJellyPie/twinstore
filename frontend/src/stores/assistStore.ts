import { create } from "zustand";

/** Where a request typed in the command palette was routed; the page there drafts the rest from the same words. */
export type AssistDestination =
  | "ab_test" | "shelf_test" | "conjoint" | "concept_test" | "staff_script" | "layout_edit" | "area" | "run_question"
  | "find_shoppers" | "optimize" | "online_design" | "online_question";

export interface PendingAsk {
  id: number;
  projectId: string;
  destination: AssistDestination;
  text: string;
  /** When it was sent; a request nobody picked up within a couple of minutes is dropped, not drafted later. */
  at: number;
}

interface AssistState {
  pending: PendingAsk | null;
  send: (ask: Omit<PendingAsk, "id" | "at">) => void;
  /** The pending request when it is for this project and one of these places; it is cleared once taken. */
  take: (projectId: string, destinations: AssistDestination[]) => PendingAsk | null;
}

let seq = 0;
export const ASK_TTL_MS = 120_000;

export const useAssistStore = create<AssistState>((set, get) => ({
  pending: null,
  send: (ask) => set({ pending: { ...ask, id: ++seq, at: Date.now() } }),
  take: (projectId, destinations) => {
    const p = get().pending;
    if (p && Date.now() - p.at > ASK_TTL_MS) {
      set({ pending: null });
      return null;
    }
    if (!p || p.projectId !== projectId || !destinations.includes(p.destination)) return null;
    set({ pending: null });
    return p;
  },
}));
