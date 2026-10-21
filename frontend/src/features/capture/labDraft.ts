import type { EditKind } from "@/shared/api/client";

// The counterfactual being composed: which edit, on which product(s), and which slot the next click fills.
export interface LabDraft {
  kind: EditKind;
  target: string | null;
  other: string | null;
  slot: "target" | "other";
}

export const EMPTY_DRAFT: LabDraft = { kind: "swap", target: null, other: null, slot: "target" };

export const needsOther = (kind: EditKind) => kind === "swap" || kind === "duplicate";
