// Product racks use 1-cell slot editing. Multi-cell dining furniture has no
// product faces and can be edited without migrating legacy product slots.
//   "with_run": run history exists → cannot reset, only "create new setup" exposed.
//   "clean":    no history → reset is permitted (the caller saves an empty floor).

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import type { SetupDetailWithBlocked } from "./types";

export type LegacyState = "ok" | "with_run" | "clean";

export function checkLegacy(setup: SetupDetailWithBlocked): LegacyState {
  const hasMultiCell =
    setup.store?.racks.some(
      (r) => r.type !== "table" && r.shape.flat().filter((x) => x === 1).length > 1,
    ) ?? false;
  if (!hasMultiCell) return "ok";
  return setup.runId ? "with_run" : "clean";
}

interface LegacyDetectModalProps {
  state: "with_run" | "clean";
  onCreateNew: () => void;
  onReset: () => Promise<void>;
  onCancel: () => void;
  // Inline reset-failure message in the state="clean" case. null/undefined hides it.
  error?: string | null;
  resetting?: boolean;
}

export function LegacyDetectModal({
  state,
  onCreateNew,
  onReset,
  onCancel,
  error,
  resetting = false,
}: LegacyDetectModalProps) {
  const { t } = useI18n();
  // "with_run" is a blocking modal — no outside-click / ESC dismiss, no Cancel button.
  // The only exit is "create new setup"; otherwise the modal stays mounted.
  const isBlocking = state === "with_run";
  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (isBlocking) return;
        if (!next) onCancel();
      }}
    >
      <DialogContent
        data-testid="legacy-detect-modal"
        showCloseButton={!isBlocking}
        onEscapeKeyDown={(e) => {
          if (isBlocking) e.preventDefault();
        }}
        onPointerDownOutside={(e) => {
          if (isBlocking) e.preventDefault();
        }}
        onInteractOutside={(e) => {
          if (isBlocking) e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("legacyTitle")}</DialogTitle>
          <DialogDescription>
            {state === "with_run" ? t("legacyWithRun") : t("legacyClean")}
          </DialogDescription>
        </DialogHeader>
        {state === "clean" && error && (
          <p
            className="text-sm text-destructive"
            data-testid="legacy-detect-error"
          >
            {error}
          </p>
        )}
        <DialogFooter>
          {state === "with_run" ? (
            <Button onClick={onCreateNew} data-testid="legacy-create-new">
              {t("legacyCreateNew")}
            </Button>
          ) : (
            <>
              <Button variant="outline" disabled={resetting} onClick={onCancel}>
                {t("cancel")}
              </Button>
              <Button
                variant="destructive"
                disabled={resetting}
                onClick={() => {
                  void onReset();
                }}
                data-testid="legacy-reset"
              >
                {resetting ? t("legacyResetting") : t("legacyReset")}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
