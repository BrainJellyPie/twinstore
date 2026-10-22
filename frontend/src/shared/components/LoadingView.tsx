import { Loader2 } from "lucide-react";
import { useI18n } from "@/shared/i18n/i18n";

interface Props {
  label?: string;
}

export function LoadingView({ label }: Props) {
  const { t } = useI18n();
  return (
    <div className="flex h-full w-full flex-1 items-center justify-center gap-2">
      <Loader2 className="size-4 animate-spin text-muted-foreground" />
      <div className="text-xs text-muted-foreground">{label ?? t("loadingView")}</div>
    </div>
  );
}
