import { Button } from "@/shared/components/ui/button";
import type { SetupDetailWithBlocked } from "./types";

interface EditLockBannerProps {
  setup: SetupDetailWithBlocked;
  onForceEditRequested: () => void;
  onCreateNewSetup: () => void;
}

function hasItems(setup: SetupDetailWithBlocked): boolean {
  return (
    setup.store?.racks.some((r) =>
      r.slots.some((s) => s.items.length > 0),
    ) ?? false
  );
}

export function EditLockBanner({
  setup,
  onForceEditRequested,
  onCreateNewSetup,
}: EditLockBannerProps) {
  if (setup.runId != null) {
    return (
      <div
        data-testid="edit-lock-banner-run"
        className="flex flex-col gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive sm:flex-row sm:items-center sm:justify-between"
      >
        <span>Editing locked — this setup has simulation history.</span>
        <Button variant="outline" size="sm" onClick={onCreateNewSetup}>
          Create new setup
        </Button>
      </div>
    );
  }
  if (hasItems(setup)) {
    return (
      <div
        data-testid="edit-lock-banner-items"
        className="flex flex-col gap-2 rounded-lg border tone-warn p-3 text-sm sm:flex-row sm:items-center sm:justify-between"
      >
        <span>
          Adding items locks store editing. Unlocking will clear all items.
        </span>
        <Button variant="outline" size="sm" onClick={onForceEditRequested}>
          Force edit
        </Button>
      </div>
    );
  }
  return null;
}
