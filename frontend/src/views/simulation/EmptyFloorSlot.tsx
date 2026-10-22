import { useI18n } from "@/shared/i18n/i18n";

export function EmptyFloorSlot() {
  const { t } = useI18n();
  return (
    <div className="flex h-full w-full items-center justify-center">
      <p className="text-sm text-muted-foreground">{t("emptyFloor")}</p>
    </div>
  );
}
