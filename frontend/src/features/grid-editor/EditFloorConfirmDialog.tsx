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

interface EditFloorConfirmDialogProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

// Confirming only opens the editor; products are removed when a changed floor is saved.
export function EditFloorConfirmDialog({
  open,
  onCancel,
  onConfirm,
}: EditFloorConfirmDialogProps) {
  const { t } = useI18n();
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
    >
      <DialogContent data-testid="edit-floor-confirm-dialog">
        <DialogHeader>
          <DialogTitle>{t("editFloorConfirmTitle")}</DialogTitle>
          <DialogDescription>{t("editFloorConfirmDescription")}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            {t("cancel")}
          </Button>
          <Button onClick={onConfirm}>
            {t("editFloorConfirmTitle")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
