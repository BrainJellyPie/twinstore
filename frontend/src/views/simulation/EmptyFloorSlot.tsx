import { EmptyFloorStart } from "@/features/dashboard/components/EmptyFloorStart";
import { useI18n } from "@/shared/i18n/i18n";

export function EmptyFloorSlot() {
  const { t } = useI18n();
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3">
      <p className="text-sm text-muted-foreground">{t("emptyFloor")}</p>
      <EmptyFloorStart />
    </div>
  );
}
