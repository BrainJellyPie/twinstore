// Pure state container — no UI/render decisions. blockedFaces is the union of
// computeAdjacentBlocked (frontend-derived: out_of_bounds + occluded) and
// initialSetup.blocked_faces (backend-derived: mostly unreachable).

import { useState, useMemo, useCallback } from "react";
import type { Rack, Position, RackType, BlockedFaceDetail } from "@/shared/types/domain";
import type { EditorRack, SetupDetailWithBlocked } from "./types";
import { computeAdjacentBlocked, mergeBlockedFaces } from "./adjacentBlocked";

const DEFAULT_GRID_SIZE: [number, number] = [8, 8];
const DEFAULT_LEVELS = 4;
const DEFAULT_DWELL_MIN = 2;
const DEFAULT_DWELL_MAX = 30;

function makeNewRack(
  position: Position,
  type: RackType,
  designVariant: "a" | "b" | "c",
): EditorRack {
  return {
    id: `r_${crypto.randomUUID().slice(0, 8)}`,
    type,
    shape: [[1]],
    position,
    rotation: 0,
    levels: DEFAULT_LEVELS,
    dwell_min: DEFAULT_DWELL_MIN,
    dwell_max: DEFAULT_DWELL_MAX,
    rack_name: "",
    rack_desc: "",
    rack_decoration_desc: "",
    locked_faces: [],
    slots: [],
    design_variant: designVariant,
  };
}

export function useGridEditor(initialSetup: SetupDetailWithBlocked) {
  const [racks, setRacks] = useState<Rack[]>(initialSetup.store?.racks ?? []);
  const [gridSize, setGridSize] = useState<[number, number]>(
    initialSetup.store?.grid_size ?? DEFAULT_GRID_SIZE,
  );
  const [backendBlockedFaces, setBackendBlockedFaces] = useState<BlockedFaceDetail[]>(
    initialSetup.blocked_faces,
  );

  const blockedFaces = useMemo(
    () =>
      mergeBlockedFaces(
        backendBlockedFaces,
        computeAdjacentBlocked(racks, gridSize),
      ),
    [racks, gridSize, backendBlockedFaces],
  );

  // patch lets callers seed initial fields (rack_name / rotation) in one setRacks call,
  // avoiding the extra render a follow-up updateRack would cause.
  const addRack = useCallback(
    (
      position: Position,
      type: RackType,
      design_variant: "a" | "b" | "c" = "a",
      patch: Partial<Pick<Rack, "rack_name" | "rotation">> = {},
    ): EditorRack => {
      const newRack: EditorRack = { ...makeNewRack(position, type, design_variant), ...patch };
      // EditorRack narrows Rack.design_variant to required — structurally Rack[]-compatible.
      setRacks((prev) => [...prev, newRack]);
      return newRack;
    },
    [],
  );

  const removeRack = useCallback((rackId: string) => {
    setRacks((prev) => prev.filter((r) => r.id !== rackId));
  }, []);

  const updateRack = useCallback((rackId: string, patch: Partial<Rack>) => {
    setRacks((prev) => prev.map((r) => (r.id === rackId ? { ...r, ...patch } : r)));
  }, []);

  // Update rotation only — do NOT remap faces. Multi-cell rack handling is delegated to backend validation.
  const rotateRack = useCallback(
    (rackId: string, rotation: 0 | 90 | 180 | 270) => {
      setRacks((prev) =>
        prev.map((r) => (r.id === rackId ? { ...r, rotation } : r)),
      );
    },
    [],
  );

  const reset = useCallback((newSetup: SetupDetailWithBlocked) => {
    setRacks(newSetup.store?.racks ?? []);
    setGridSize(newSetup.store?.grid_size ?? DEFAULT_GRID_SIZE);
    setBackendBlockedFaces(newSetup.blocked_faces);
  }, []);

  return {
    racks,
    gridSize,
    blockedFaces,
    addRack,
    removeRack,
    updateRack,
    rotateRack,
    reset,
    setBackendBlockedFaces,
    setGridSize,
  };
}
