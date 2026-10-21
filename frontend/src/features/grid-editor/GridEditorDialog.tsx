// Race handling (flushPendingText → saveSetup):
//   RackEditPanel.flushPendingText() synchronously calls onChange({ rack_name }),
//   which calls editor.updateRack to queue a setState. Reading editor.racks right
//   afterward in the same handler returns a stale closure value.
//   Fix: mirror editor.racks into racksRef via useLayoutEffect, and wrap
//   flushPendingText in react-dom's flushSync so setState + useLayoutEffect commit
//   synchronously. Then racksRef.current is the latest racks. This is solved inside
//   GridEditorDialog without changing RackEditPanel's API (minimally invasive).

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { flushSync } from "react-dom";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import type { Position, Rack } from "@/shared/types/domain";
import { GridEditor } from "./GridEditor";
import { rackCells } from "@/shared/utils/grid";
import { RackEditPanel, type RackEditPanelHandle } from "./RackEditPanel";
import { LegacyDetectModal, checkLegacy } from "./LegacyDetectModal";
import { useGridEditor } from "./useGridEditor";
import { saveSetup } from "./gridEditorApi";
import { MIN_DIM, MAX_DIM, clampDim } from "./gridDimensions";
import { useProject } from "@/shared/queries/useProject";
import type { Store } from "@/shared/types/domain";
import type { EditorRack, SetupDetailWithBlocked } from "./types";

// onSaved: parent only invalidates queries — do NOT mutate setup state or selectedSetupId.
// No `next` argument by design: removes the temptation to sync via local state.
// invalidate → refetch handles propagation automatically.
// onCreateNewSetup is only used by LegacyDetectModal's "create new setup" button — optional.
interface GridEditorDialogProps {
  open: boolean;
  pid: string;
  sid: string;
  initialSetup: SetupDetailWithBlocked;
  onClose: () => void;
  onSaved: () => void;
  onCreateNewSetup?: () => void;
}

export function GridEditorDialog({
  open,
  pid,
  sid,
  initialSetup,
  onClose,
  onSaved,
  onCreateNewSetup,
}: GridEditorDialogProps) {
  const editor = useGridEditor(initialSetup);
  const project = useProject(pid).data;

  // Local snapshot of the setup the dialog operates on. Updated after legacy reset.
  // Not updated after a successful Save — the dialog closes and the parent invalidates.
  const [setup, setSetup] = useState<SetupDetailWithBlocked>(initialSetup);

  const [selectedCell, setSelectedCell] = useState<Position | null>(null);
  const [selectedRackId, setSelectedRackId] = useState<string | null>(null);
  const [legacyDismissed, setLegacyDismissed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [legacyResetError, setLegacyResetError] = useState<string | null>(null);

  const panelRef = useRef<RackEditPanelHandle>(null);

  // Race-safe latest-racks ref — inside flushSync, the setState commits and the
  // useLayoutEffect fires synchronously, so the ref is updated.
  const racksRef = useRef<Rack[]>(editor.racks);
  useLayoutEffect(() => {
    racksRef.current = editor.racks;
  }, [editor.racks]);

  const legacyState = useMemo(() => checkLegacy(setup), [setup]);

  // All racks at the selected cell — up to two coexist (entrance + exit).
  const selectedCellRacks: EditorRack[] = useMemo(() => {
    if (selectedCell == null) return [];
    return editor.racks
      .filter(
        (r) => rackCells(r).some(([x, y]) => x === selectedCell[0] && y === selectedCell[1]),
      )
      .map((r) => ({ ...r, design_variant: r.design_variant ?? "a" }) as EditorRack);
  }, [editor.racks, selectedCell]);

  // Single edit target (name/design/rotation). In the gate case, entrance wins over exit.
  const selectedRack: EditorRack | null = useMemo(() => {
    if (selectedRackId != null) {
      const found = selectedCellRacks.find((r) => r.id === selectedRackId);
      if (found) return found;
    }
    if (selectedCellRacks.length === 0) return null;
    const entrance = selectedCellRacks.find((r) => r.type === "entrance");
    return entrance ?? selectedCellRacks[0]!;
  }, [selectedCellRacks, selectedRackId]);

  const onCellClick = useCallback(
    (pos: Position) => {
      const existing = editor.racks.find(
        (r) => rackCells(r).some(([x, y]) => x === pos[0] && y === pos[1]),
      );
      // Empty cell: do NOT create a draft yet — wait for type selection.
      // The draft is created in onRackChange when RackEditPanel's Type radio first emits.
      setSelectedCell(pos);
      setSelectedRackId(existing?.id ?? null);
    },
    [editor],
  );

  const onRackChange = useCallback(
    (patch: Partial<EditorRack> | null) => {
      // No selectedRack yet (empty cell) — create the draft on the first Type selection.
      if (selectedRack == null) {
        if (patch == null || selectedCell == null) return;
        const type = patch.type ?? "shelf";
        const variant = patch.design_variant ?? "a";
        const { type: _t, design_variant: _v, ...rest } = patch;
        const created = editor.addRack(selectedCell, type, variant, rest);
        setSelectedRackId(created.id);
        return;
      }
      if (patch === null) {
        // Delete the whole cell — includes both entrance+exit in the gate case.
        for (const r of selectedCellRacks) editor.removeRack(r.id);
        setSelectedCell(null);
        setSelectedRackId(null);
        return;
      }
      editor.updateRack(selectedRack.id, patch);
    },
    [editor, selectedRack, selectedCell, selectedCellRacks],
  );

  // Gate config toggle (entrance / exit / both): add/remove the entrance and exit racks
  // at the cell. If a non-gate rack (shelf/counter) is present, remove it and replace
  // with the requested gate(s).
  const onGateConfigChange = useCallback(
    (config: "entrance" | "exit" | "both") => {
      if (selectedCell == null) return;
      const cellRacks = editor.racks.filter(
        (r) => rackCells(r).some(([x, y]) => x === selectedCell[0] && y === selectedCell[1]),
      );
      // Drop non-gate racks in this cell (shelf/counter → gate transition).
      for (const r of cellRacks) {
        if (r.type !== "entrance" && r.type !== "exit") editor.removeRack(r.id);
      }
      const entrance = cellRacks.find((r) => r.type === "entrance");
      const exit = cellRacks.find((r) => r.type === "exit");
      const wantEntrance = config === "entrance" || config === "both";
      const wantExit = config === "exit" || config === "both";

      let nextSelectedId: string | null = null;
      if (wantEntrance) {
        if (entrance) nextSelectedId = entrance.id;
        else nextSelectedId = editor.addRack(selectedCell, "entrance", "a").id;
      } else if (entrance) {
        editor.removeRack(entrance.id);
      }
      if (wantExit) {
        if (exit) {
          if (nextSelectedId == null) nextSelectedId = exit.id;
        } else {
          const created = editor.addRack(selectedCell, "exit", "a");
          if (nextSelectedId == null) nextSelectedId = created.id;
        }
      } else if (exit) {
        editor.removeRack(exit.id);
      }
      setSelectedRackId(nextSelectedId);
    },
    [editor, selectedCell],
  );

  // Save — flushSync any pending text via flushPendingText, then saveSetup.
  // The "Build from scratch" case (setup.store == null) synthesizes a fresh Store
  // from project metadata; the id is generated frontend-side.
  const onSave = useCallback(async () => {
    flushSync(() => {
      panelRef.current?.flushPendingText();
    });
    const racksForSave = racksRef.current;
    setSaveError(null);
    // shelf/fridge/counter require a name for identification; entrance/exit do not.
    const NAMED_TYPES = new Set(["shelf", "fridge", "counter"]);
    const unnamed = racksForSave.filter(
      (r) => NAMED_TYPES.has(r.type) && !r.rack_name.trim(),
    );
    if (unnamed.length > 0) {
      const coords = unnamed
        .map((r) => `(${r.position[0]},${r.position[1]})`)
        .join(", ");
      setSaveError(`Unnamed rack/counter: ${coords}`);
      return;
    }
    setSaving(true);
    try {
      const baseStore: Store = setup.store ?? {
        id: `store_${crypto.randomUUID().slice(0, 8)}`,
        name: project.metadata.name,
        type: project.metadata.store_type,
        currency: project.metadata.currency,
        grid_size: editor.gridSize,
        weekly_schedule: [...project.metadata.weekly_schedule],
        racks: [],
      };
      const result = await saveSetup(pid, sid, {
        store: {
          ...baseStore,
          grid_size: editor.gridSize,
          racks: racksForSave,
        },
      });
      if (!result.ok) {
        setSaveError(result.message || "Save failed");
        return;
      }
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  }, [pid, sid, setup, editor.gridSize, project, onSaved, onClose]);

  // Legacy reset (2-step PUT) — same flow as GridEditorPage.
  const onLegacyReset = useCallback(async () => {
    if (!setup.store) return;
    setLegacyResetError(null);
    const itemsEmpty = {
      ...setup.store,
      racks: setup.store.racks.map((r) => ({
        ...r,
        slots: r.slots.map((s) => ({ ...s, items: [] })),
      })),
    };
    const r1 = await saveSetup(pid, sid, { store: itemsEmpty });
    if (!r1.ok) {
      setLegacyResetError(r1.message || "Reset step 1 failed");
      return;
    }
    const empty = {
      ...setup.store,
      grid_size: setup.store.grid_size,
      racks: [],
    };
    const r2 = await saveSetup(pid, sid, { store: empty });
    if (!r2.ok) {
      setLegacyResetError(r2.message || "Reset step 2 failed");
      return;
    }
    // Update local state only — backend normalisation is picked up by the parent's
    // invalidate after the dialog closes.
    const reset: SetupDetailWithBlocked = {
      ...setup,
      store: { ...setup.store, racks: [] },
      blocked_faces: [],
    };
    setSetup(reset);
    editor.reset(reset);
    setLegacyDismissed(true);
  }, [pid, sid, setup, editor]);

  const onLegacyCancel = useCallback(() => {
    setLegacyResetError(null);
    setLegacyDismissed(true);
  }, []);

  const onWidthChange = useCallback(
    (raw: string) => {
      const w = clampDim(Number(raw));
      editor.setGridSize([w, editor.gridSize[1]]);
    },
    [editor],
  );
  const onHeightChange = useCallback(
    (raw: string) => {
      const h = clampDim(Number(raw));
      editor.setGridSize([editor.gridSize[0], h]);
    },
    [editor],
  );

  // Clear selection on close so the next open starts clean.
  useEffect(() => {
    if (!open) {
      setSelectedCell(null);
      setSelectedRackId(null);
      setSaveError(null);
    }
  }, [open]);

  const createNewSetup = onCreateNewSetup ?? (() => {});

  const showLegacyModal = legacyState === "clean" && !legacyDismissed;
  const isBlockingLegacy = legacyState === "with_run";

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent
        className="flex max-h-[90vh] w-[68vw] min-w-[640px] flex-col sm:max-w-[68vw]"
        data-testid="grid-editor-dialog"
      >
        <DialogHeader>
          <DialogTitle>Floor Configuration</DialogTitle>
        </DialogHeader>

        {isBlockingLegacy ? (
          <LegacyDetectModal
            state="with_run"
            onCreateNew={createNewSetup}
            onReset={onLegacyReset}
            onCancel={() => {
              /* with_run cannot be dismissed — the modal never calls onCancel. */
            }}
          />
        ) : (
          <div className="-mx-6 flex flex-1 flex-col gap-3 overflow-y-auto px-6 pb-1">
            {/* Dimension row — inline W/H inputs (5-20 clamp). */}
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Dimension:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground">W</span>
                <Input
                  type="number"
                  min={MIN_DIM}
                  max={MAX_DIM}
                  value={editor.gridSize[0]}
                  onChange={(e) => onWidthChange(e.target.value)}
                  className="h-8 w-16"
                  data-testid="grid-width-input"
                />
                <span className="text-muted-foreground">H</span>
                <Input
                  type="number"
                  min={MIN_DIM}
                  max={MAX_DIM}
                  value={editor.gridSize[1]}
                  onChange={(e) => onHeightChange(e.target.value)}
                  className="h-8 w-16"
                  data-testid="grid-height-input"
                />
              </div>
            </div>


            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="min-w-0 md:col-span-2">
                <GridEditor
                  racks={editor.racks}
                  gridSize={editor.gridSize}
                  blockedFaces={editor.blockedFaces}
                  onCellClick={onCellClick}
                  selectedCell={selectedCell}
                />
              </div>
              <div className="min-w-0">
                <RackEditPanel
                  ref={panelRef}
                  selectedCell={selectedCell}
                  selectedCellRacks={selectedCellRacks}
                  selectedRack={selectedRack}
                  onChange={onRackChange}
                  onGateConfigChange={onGateConfigChange}
                />
              </div>
            </div>

            {showLegacyModal && (
              <LegacyDetectModal
                state="clean"
                onCreateNew={createNewSetup}
                onReset={onLegacyReset}
                onCancel={onLegacyCancel}
                error={legacyResetError}
              />
            )}
          </div>
        )}

        <DialogFooter className="flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
          {saveError ? (
            <p
              data-testid="grid-save-error"
              className="flex-1 truncate text-sm text-destructive"
              title={saveError}
            >
              {saveError}
            </p>
          ) : (
            <span className="hidden flex-1 sm:block" aria-hidden />
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={onClose}
              data-testid="grid-cancel-button"
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                void onSave();
              }}
              disabled={saving || isBlockingLegacy}
              data-testid="grid-save-button"
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
