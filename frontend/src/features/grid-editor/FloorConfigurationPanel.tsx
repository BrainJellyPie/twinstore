import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/queries/keys";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { GridEditorDialog } from "./GridEditorDialog";
import { EditFloorConfirmDialog } from "./EditFloorConfirmDialog";
import type { SetupDetailWithBlocked } from "./types";

interface FloorConfigurationPanelProps {
  pid: string;
  sid: string;
  setup: SetupDetailWithBlocked;
  itemCount: number;
  /**
   * Called when the panel's busy state changes (grid dialog open or confirm dialog open).
   * The parent should wrap this in useCallback to avoid spurious effect fires on every parent render.
   */
  onBusyChange?: (busy: boolean) => void;
}

export function FloorConfigurationPanel({
  pid,
  sid,
  setup,
  itemCount,
  onBusyChange,
}: FloorConfigurationPanelProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const [gridDialogOpen, setGridDialogOpen] = useState(false);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  // dialogInitialSetup lifecycle:
  //   - set immediately before opening GridEditorDialog.
  //   - reset to null on dialog close (success or cancel) so a stale snapshot can't leak into a future open.
  const [dialogInitialSetup, setDialogInitialSetup] =
    useState<SetupDetailWithBlocked | null>(null);
  // The layout has products: the editor removes them only when a changed floor is saved.
  const [clearItemsOnSave, setClearItemsOnSave] = useState(false);

  const hasFloor = setup.store != null;

  const isBusy = gridDialogOpen || confirmDialogOpen;
  useEffect(() => {
    onBusyChange?.(isBusy);
  }, [isBusy, onBusyChange]);

  // Build from scratch, or edit a floor without products — no confirm needed.
  const openEditor = useCallback(() => {
    setDialogInitialSetup(setup);
    setClearItemsOnSave(false);
    setGridDialogOpen(true);
  }, [setup]);

  // hasFloor && itemCount > 0 — show confirm first.
  const onEditWithItems = useCallback(() => {
    setConfirmDialogOpen(true);
  }, []);

  // Nothing is saved here: Cancel/Esc in the editor leave the layout and its products untouched.
  const onConfirmEdit = useCallback(() => {
    setDialogInitialSetup(setup);
    setClearItemsOnSave(true);
    setConfirmDialogOpen(false);
    setGridDialogOpen(true);
  }, [setup]);

  const onGridSaved = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.setup(pid, sid) });
    queryClient.invalidateQueries({ queryKey: queryKeys.setups(pid) });
    queryClient.invalidateQueries({ queryKey: queryKeys.project(pid) });
    setGridDialogOpen(false);
    setDialogInitialSetup(null);
  }, [queryClient, pid, sid]);

  const onGridClose = useCallback(() => {
    setGridDialogOpen(false);
    setDialogInitialSetup(null);
  }, []);

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">{t("floorConfigurationStep")}</h3>
        {hasFloor && (
          <button
            type="button"
            data-testid="floor-config-edit-link"
            className="text-indigo-600 hover:underline"
            onClick={itemCount > 0 ? onEditWithItems : openEditor}
          >
            {t("editFloor")}
          </button>
        )}
      </div>

      {!hasFloor && (
        <Button
          data-testid="floor-config-build-button"
          onClick={openEditor}
        >
          {t("buildLayoutFromScratch")}
        </Button>
      )}

      <EditFloorConfirmDialog
        open={confirmDialogOpen}
        onCancel={() => setConfirmDialogOpen(false)}
        onConfirm={onConfirmEdit}
      />

      {gridDialogOpen && dialogInitialSetup && (
        <GridEditorDialog
          open={gridDialogOpen}
          pid={pid}
          sid={sid}
          initialSetup={dialogInitialSetup}
          clearItemsOnSave={clearItemsOnSave}
          onClose={onGridClose}
          onSaved={onGridSaved}
        />
      )}
    </div>
  );
}
