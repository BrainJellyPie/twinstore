// Force-edit hook — when the user tries to edit a store that already has items,
// save a single PUT with all slot items cleared and return the resulting
// SetupDetailWithBlocked so the caller can reset() the editor state. On failure it
// returns the server's message; the caller surfaces it.

import { useCallback, useState } from "react";
import { saveSetup } from "./gridEditorApi";
import type { SetupDetailWithBlocked } from "./types";
import type { Store } from "@/shared/types/domain";

export function useForceEdit(pid: string, sid: string) {
  const [running, setRunning] = useState(false);

  const forceEdit = useCallback(
    async (
      currentSetup: SetupDetailWithBlocked,
    ): Promise<{ ok: true; setup: SetupDetailWithBlocked } | { ok: false; message: string }> => {
      setRunning(true);
      try {
        const cleared: Store | null = currentSetup.store
          ? {
              ...currentSetup.store,
              racks: currentSetup.store.racks.map((r) => ({
                ...r,
                slots: r.slots.map((s) => ({ ...s, items: [] })),
              })),
            }
          : null;

        const result = await saveSetup(pid, sid, {
          store: cleared ?? undefined,
        });
        if (!result.ok) {
          return { ok: false, message: result.message || "Failed to save force edit." };
        }

        // Spread order: existing setup ← API SetupSummary ← cleared-store override.
        const newSetup: SetupDetailWithBlocked = {
          ...currentSetup,
          ...result.setup,
          store: cleared,
          blocked_faces: result.blocked_faces,
        };
        return { ok: true, setup: newSetup };
      } finally {
        setRunning(false);
      }
    },
    [pid, sid],
  );

  return { forceEdit, running };
}
