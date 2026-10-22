import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/queries/keys";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { GridEditorDialog } from "./GridEditorDialog";
import { EditFloorConfirmDialog } from "./EditFloorConfirmDialog";
import { useForceEdit } from "./useForceEdit";
import { loadSetup } from "./gridEditorApi";
import type { SetupDetailWithBlocked } from "./types";

interface FloorConfigurationPanelProps {
  pid: string;
  sid: string;
  setup: SetupDetailWithBlocked;
  itemCount: number;
  /**
   * Called when the panel's busy state changes (grid dialog open, confirm dialog open, or
   * force-edit running). The parent should wrap this in useCallback to avoid spurious effect
   * fires on every parent render.
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
  const forceEdit = useForceEdit(pid, sid);

  const [gridDialogOpen, setGridDialogOpen] = useState(false);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  // dialogInitialSetup lifecycle:
  //   - set on Build/Edit-no-items/force-edit-success (immediately before opening GridEditorDialog).
  //   - reset to null on dialog close (success or cancel) so a stale snapshot can't leak into a future open.
  const [dialogInitialSetup, setDialogInitialSetup] =
    useState<SetupDetailWithBlocked | null>(null);

  const hasFloor = setup.store != null;

  const isBusy = gridDialogOpen || confirmDialogOpen || forceEdit.running;
  useEffect(() => {
    onBusyChange?.(isBusy);
  }, [isBusy, onBusyChange]);

  const onBuildFromScratch = useCallback(() => {
    setDialogInitialSetup(setup);
    setGridDialogOpen(true);
  }, [setup]);

  // hasFloor && itemCount === 0 — skip confirm, reuse current setup.
  const onEditNoItems = useCallback(() => {
    setDialogInitialSetup(setup);
    setGridDialogOpen(true);
  }, [setup]);

  // hasFloor && itemCount > 0 — show confirm first.
  const onEditWithItems = useCallback(() => {
    setConfirmError(null);
    setConfirmDialogOpen(true);
  }, []);

  // Policy: a successful force-edit persists items=[] on the backend. If the user then
  // cancels GridEditorDialog, items are NOT restored — the confirm dialog already
  // collected destructive consent.
  const onConfirmForceEdit = useCallback(async () => {
    if (forceEdit.running) return;
    setConfirmError(null);
    try {
      const result = await forceEdit.forceEdit(setup);
      if (!result.ok) {
        setConfirmError(result.message);
        return;
      }
      // Single canonical path for fresh setup: invalidate + fetchQuery.
      // useForceEdit's return is NOT used — that would re-introduce stale-setup risk.
      await queryClient.invalidateQueries({
        queryKey: queryKeys.setup(pid, sid),
      });
      const refetched = await queryClient.fetchQuery({
        queryKey: queryKeys.setup(pid, sid),
        queryFn: async () => {
          const r = await loadSetup(pid, sid);
          if (!r.ok) throw new Error(r.message ?? "Refresh failed");
          return r.detail;
        },
      });
      setDialogInitialSetup(refetched);
      queryClient.invalidateQueries({ queryKey: queryKeys.setups(pid) });
      queryClient.invalidateQueries({ queryKey: queryKeys.project(pid) });
      setConfirmDialogOpen(false);
      setGridDialogOpen(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Refresh failed";
      setConfirmError(msg);
    }
  }, [forceEdit, queryClient, pid, sid, setup]);

  const onConfirmCancel = useCallback(() => {
    setConfirmError(null);
    setConfirmDialogOpen(false);
  }, []);

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
            onClick={itemCount > 0 ? onEditWithItems : onEditNoItems}
          >
            {t("editFloor")}
          </button>
        )}
      </div>

      {!hasFloor && (
        <Button
          data-testid="floor-config-build-button"
          onClick={onBuildFromScratch}
        >
          {t("buildLayoutFromScratch")}
        </Button>
      )}

      <EditFloorConfirmDialog
        open={confirmDialogOpen}
        onCancel={onConfirmCancel}
        onConfirm={() => {
          void onConfirmForceEdit();
        }}
        error={confirmError}
        confirmDisabled={forceEdit.running}
      />

      {gridDialogOpen && dialogInitialSetup && (
        <GridEditorDialog
          open={gridDialogOpen}
          pid={pid}
          sid={sid}
          initialSetup={dialogInitialSetup}
          onClose={onGridClose}
          onSaved={onGridSaved}
        />
      )}
    </div>
  );
}
