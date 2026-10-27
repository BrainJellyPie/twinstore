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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import { Button } from "@/shared/components/ui/button";
import { translate, useI18n } from "@/shared/i18n/i18n";
import type { Position, Rack } from "@/shared/types/domain";
import { GridEditor } from "./GridEditor";
import { rackCells } from "@/shared/utils/grid";
import { RackEditPanel, type RackEditPanelHandle } from "./RackEditPanel";
import { LegacyDetectModal, checkLegacy } from "./LegacyDetectModal";
import { useGridEditor } from "./useGridEditor";
import { saveSetup } from "./gridEditorApi";
import { MIN_DIM, MAX_DIM } from "./gridDimensions";
import { DimensionInput } from "./DimensionInput";
import { rackTypeLabel } from "@/shared/i18n/rackTypeLabels";
import { useProject } from "@/shared/queries/useProject";
import type { Store } from "@/shared/types/domain";
import type { EditorRack, SetupDetailWithBlocked } from "./types";
import type { Locale, MessageKey } from "@/shared/i18n/messages";

// Layout issues the server reports that have their own words; others show as the server wrote them.
const ISSUE_TEXT: Record<string, MessageKey> = {
  no_entrance: "readinessNoEntrance", no_exit: "readinessNoExit", no_counter: "readinessNoCounter",
};

// onSaved: parent only invalidates queries — do NOT mutate setup state or selectedSetupId.
// No `next` argument by design: removes the temptation to sync via local state.
// invalidate → refetch handles propagation automatically.
// onCreateNewSetup is only used by LegacyDetectModal's "create new setup" button — optional.
// clearItemsOnSave: the layout has products, which the backend does not allow on a changed floor.
// The editor works on the floor without them and removes them only when a changed floor is saved,
// so closing without saving leaves the layout as it was.
interface GridEditorDialogProps {
  open: boolean;
  pid: string;
  sid: string;
  initialSetup: SetupDetailWithBlocked;
  onClose: () => void;
  onSaved: () => void;
  onCreateNewSetup?: () => void;
  clearItemsOnSave?: boolean;
}

/** Fixtures that a smaller floor leaves partly or wholly off the grid. */
function outsideGrid(racks: Rack[], [width, depth]: [number, number]): Rack[] {
  return racks.filter((rack) => rackCells(rack).some(([x, y]) => x < 0 || y < 0 || x >= width || y >= depth));
}

function outsideMessage(outside: Rack[], locale: Locale): string {
  const names = outside.slice(0, 3).map((rack) => rack.rack_name || rackTypeLabel(rack.type, (key) => translate(locale, key))).join(", ");
  // "+2" rather than ", …": the message goes on with a full stop, which an ellipsis would double.
  return translate(locale, "gridOutside", { count: outside.length, names: `${names}${outside.length > 3 ? ` +${outside.length - 3}` : ""}` });
}

function withoutItems(store: Store): Store {
  return {
    ...store,
    racks: store.racks.map((r) => ({ ...r, slots: r.slots.map((s) => ({ ...s, items: [] })) })),
  };
}

export function GridEditorDialog({
  open,
  pid,
  sid,
  initialSetup,
  onClose,
  onSaved,
  onCreateNewSetup,
  clearItemsOnSave = false,
}: GridEditorDialogProps) {
  const { locale, t } = useI18n();
  const project = useProject(pid).data;

  // Local snapshot of the setup the dialog operates on. Updated after legacy reset.
  // Not updated after a successful Save — the dialog closes and the parent invalidates.
  const [setup, setSetup] = useState<SetupDetailWithBlocked>(() =>
    clearItemsOnSave && initialSetup.store
      ? { ...initialSetup, store: withoutItems(initialSetup.store) }
      : initialSetup,
  );
  // The saved store with its products, while they are still on the backend.
  const [productsStore, setProductsStore] = useState<Store | null>(
    clearItemsOnSave ? initialSetup.store : null,
  );
  const editor = useGridEditor(setup);

  const [selectedCell, setSelectedCell] = useState<Position | null>(null);
  const [selectedRackId, setSelectedRackId] = useState<string | null>(null);
  const [placing, setPlacing] = useState(false);
  const [legacyDismissed, setLegacyDismissed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [legacyResetError, setLegacyResetError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const resettingRef = useRef(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

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
      if (placing && selectedRack) {
        const offset: Position = [pos[0] - selectedRack.position[0], pos[1] - selectedRack.position[1]];
        const error = editor.moveRacks(selectedCellRacks.map((rack) => rack.id), offset);
        setSaveError(error);
        if (!error) { setSelectedCell(pos); setPlacing(false); }
        return;
      }
      const existing = editor.racks.find(
        (r) => rackCells(r).some(([x, y]) => x === pos[0] && y === pos[1]),
      );
      // Empty cell: do NOT create a draft yet — wait for type selection.
      // The draft is created in onRackChange when RackEditPanel's Type radio first emits.
      setSelectedCell(pos);
      setSelectedRackId(existing?.id ?? null);
      setSaveError(null);
    },
    [editor, placing, selectedRack, selectedCellRacks],
  );

  const onMove = (offset: Position) => {
    if (!selectedCell || selectedCellRacks.length === 0) return;
    const error = editor.moveRacks(selectedCellRacks.map((rack) => rack.id), offset);
    setSaveError(error);
    if (!error) setSelectedCell([selectedCell[0] + offset[0], selectedCell[1] + offset[1]]);
  };

  const onRackChange = useCallback(
    (patch: Partial<EditorRack> | null) => {
      setPlacing(false);
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
      setPlacing(false);
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
  // Shrinking the floor hides fixtures at once; say so now rather than only when Save refuses them.
  const hidden = outsideGrid(editor.racks, editor.gridSize);

  const onSave = useCallback(async () => {
    flushSync(() => {
      panelRef.current?.flushPendingText();
    });
    const racksForSave = racksRef.current;
    setSaveError(null);
    // An unchanged floor keeps its products.
    if (productsStore && setup.store
      && editor.gridSize[0] === setup.store.grid_size[0] && editor.gridSize[1] === setup.store.grid_size[1]
      && JSON.stringify(racksForSave) === JSON.stringify(setup.store.racks)) {
      onClose();
      return;
    }
    const outside = outsideGrid(racksForSave, editor.gridSize);
    if (outside.length > 0) {
      setSaveError(outsideMessage(outside, locale));
      return;
    }
    // shelf/fridge/counter require a name for identification; entrance/exit do not.
    const NAMED_TYPES = new Set(["shelf", "fridge", "counter"]);
    const unnamed = racksForSave.filter(
      (r) => NAMED_TYPES.has(r.type) && !r.rack_name.trim(),
    );
    if (unnamed.length > 0) {
      const coords = unnamed  // counted from 1, as under the grid
        .map((r) => translate(locale, "gridCellAt", { column: r.position[0] + 1, row: r.position[1] + 1 }))
        .join("; ");
      setSaveError(translate(locale, "gridUnnamed", { cells: coords }));
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
        ...(productsStore ? { discard_products: true } : {}),
        store: {
          ...baseStore,
          grid_size: editor.gridSize,
          racks: racksForSave,
        },
      });
      if (!result.ok) {
        // Say what the layout is missing ("no exit"), not only that it has errors.
        const listed = Array.isArray(result.details.issues) ? result.details.issues as unknown[] : [];
        const issues = listed.flatMap((issue) => {
          if (!issue || typeof issue !== "object") return [];
          const { code, message } = issue as { code?: unknown; message?: unknown };
          const key = typeof code === "string" ? ISSUE_TEXT[code] : undefined;
          return key ? [translate(locale, key)] : typeof message === "string" && message ? [message] : [];
        });
        setSaveError(issues.length ? issues.join(" · ") : result.message || translate(locale, "gridSaveFailed"));
        return;
      }
      onSaved();
      onClose();
    } catch (error) {
      setSaveError(error instanceof Error && error.message ? error.message : translate(locale, "gridSaveFailed"));
    } finally {
      setSaving(false);
    }
  }, [pid, sid, setup, productsStore, editor.gridSize, project, onSaved, onClose, locale]);

  // Product removal and legacy-floor reset commit in one validated save.
  const onLegacyReset = useCallback(async () => {
    if (!setup.store || resettingRef.current) return;
    resettingRef.current = true;
    setResetting(true);
    setLegacyResetError(null);
    try {
      const empty = {
        ...setup.store,
        grid_size: setup.store.grid_size,
        racks: [],
      };
      const result = await saveSetup(pid, sid, { store: empty, discard_products: true });
      if (!result.ok) {
        setLegacyResetError(result.message || translate(locale, "gridResetFailed"));
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
      setProductsStore(null);
      setLegacyDismissed(true);
    } catch (error) {
      setLegacyResetError(error instanceof Error && error.message ? error.message : translate(locale, "gridResetFailed"));
    } finally {
      resettingRef.current = false;
      setResetting(false);
    }
  }, [pid, sid, setup, editor, locale]);

  const onLegacyCancel = useCallback(() => {
    setLegacyResetError(null);
    setLegacyDismissed(true);
  }, []);

  // Clear selection on close so the next open starts clean.
  useEffect(() => {
    if (!open) {
      setSelectedCell(null);
      setSelectedRackId(null);
      setPlacing(false);
      setSaveError(null);
    }
  }, [open]);

  const createNewSetup = onCreateNewSetup ?? (() => {});

  const showLegacyModal = legacyState === "clean" && !legacyDismissed;
  const isBlockingLegacy = legacyState === "with_run";

  // Cancel, the X button and Escape ask before dropping unsaved edits; outside clicks are ignored.
  const requestClose = () => {
    if (editor.dirty) setConfirmDiscard(true);
    else onClose();
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) requestClose();
      }}
    >
      <DialogContent
        className="flex max-h-[92dvh] w-[calc(100vw-2rem)] min-w-0 flex-col sm:max-w-[min(92vw,1440px)]"
        data-testid="grid-editor-dialog"
        onEscapeKeyDown={(event) => {
          if (placing) { event.preventDefault(); setPlacing(false); setSaveError(null); }
          else if (editor.dirty) { event.preventDefault(); setConfirmDiscard(true); }
        }}
        onInteractOutside={(event) => {
          if (editor.dirty) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("gridTitle")}</DialogTitle>
          <DialogDescription className={productsStore ? "text-warn" : "sr-only"} data-testid="grid-editor-description">
            {productsStore ? t("floorEditRemovesProducts") : t("floorEditorDescription")}
          </DialogDescription>
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
          <div className="-mx-6 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-6 pb-1">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <DimensionInput axis="width" value={editor.gridSize[0]}
                onChange={(width) => { editor.setGridSize([width, editor.gridSize[1]]); setSaveError(null); }} />
              <DimensionInput axis="height" value={editor.gridSize[1]}
                onChange={(height) => { editor.setGridSize([editor.gridSize[0], height]); setSaveError(null); }} />
              <span className="text-xs text-muted-foreground">{t("gridCellsPerSide", { min: MIN_DIM, max: MAX_DIM })}</span>
            </div>
            {hidden.length > 0 && !saveError && <p role="status" className="text-sm text-warn">{outsideMessage(hidden, locale)}</p>}


            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="min-w-0 md:col-span-2">
                <GridEditor
                  racks={editor.racks}
                  gridSize={editor.gridSize}
                  blockedFaces={editor.blockedFaces}
                  onCellClick={onCellClick}
                  selectedCell={selectedCell}
                  placing={placing}
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
                  onMove={onMove}
                  placing={placing}
                  onPlacementChange={(next) => { setPlacing(next); setSaveError(null); }}
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
                resetting={resetting}
              />
            )}
          </div>
        )}

        <DialogFooter className="flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
          {saveError ? (
            <p
              data-testid="grid-save-error"
              role="alert"
              className="flex-1 text-sm text-destructive"
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
              onClick={requestClose}
              data-testid="grid-cancel-button"
            >
              {t("cancel")}
            </Button>
            <Button
              onClick={() => {
                void onSave();
              }}
              disabled={saving || isBlockingLegacy || placing}
              data-testid="grid-save-button"
            >
              {saving ? t("gridSaving") : t("providerSave")}
            </Button>
          </div>
        </DialogFooter>
        <AlertDialog open={confirmDiscard} onOpenChange={setConfirmDiscard}>
          <AlertDialogContent data-testid="grid-discard-confirm">
            <AlertDialogHeader>
              <AlertDialogTitle>{t("discardFloorChangesTitle")}</AlertDialogTitle>
              <AlertDialogDescription>{t("discardFloorChangesDescription")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t("keepEditing")}</AlertDialogCancel>
              <AlertDialogAction variant="destructive" onClick={onClose}>{t("discardChanges")}</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </DialogContent>
    </Dialog>
  );
}
