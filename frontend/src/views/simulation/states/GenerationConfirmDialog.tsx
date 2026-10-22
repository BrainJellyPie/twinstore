// Asked while a customer generation waits: writing every estimated visitor is slow (or costly), so the user chooses
// between all of them, a sample a day (the rest of each day are copies of it), or cancelling. The dialog stays open
// until one of these is chosen — closing it any other way would leave the job waiting silently.

import { useI18n } from "@/shared/i18n/i18n";
import { Button } from "@/shared/components/ui/button";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import type { GenerationChoice, GenerationConfirm, WriteChoice } from "@/shared/types/domain";
import { costText, durationText } from "@/shared/utils/estimate";

interface Props {
  confirm: GenerationConfirm;
  answering: boolean;
  error: string | null;
  onAnswer: (choice: GenerationChoice) => void;
}

const optionClass = "h-auto w-full flex-col items-start gap-0.5 whitespace-normal px-3 py-2.5 text-left";

export function GenerationConfirmDialog({ confirm, answering, error, onAnswer }: Props) {
  const { locale, t } = useI18n();
  const counts = Object.values(confirm.visitors_per_day).filter((n) => Number.isFinite(n));
  const fewest = counts.length ? Math.min(...counts) : confirm.all.per_day;
  const most = counts.length ? Math.max(...counts) : confirm.all.per_day;
  const visitors = fewest === most ? t("visitorsADay", { count: fewest }) : t("visitorsADayRange", { min: fewest, max: most });
  const details = (choice: WriteChoice) => [
    t("modelCalls", { calls: choice.requests }),
    durationText(locale, choice.minutes),
    costText(locale, choice.cost_usd, confirm.local),
  ].join(" · ");

  return (
    <AlertDialog open onOpenChange={() => { /* Stays open until the user chooses; Cancel is explicit. */ }}>
      <AlertDialogContent className="max-h-[92dvh] grid-cols-1 overflow-y-auto [overflow-wrap:anywhere] data-[size=default]:max-w-[calc(100%-2rem)] data-[size=default]:sm:max-w-lg">
        <AlertDialogHeader className="min-w-0">
          <AlertDialogTitle>{t("genConfirmTitle")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("genConfirmEstimate", { visitors, days: confirm.days })} {t("genConfirmSlow", { model: confirm.model })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="grid min-w-0 gap-2">
          <Button variant="outline" className={optionClass} disabled={answering} onClick={() => onAnswer("all")}>
            <span className="font-medium">{t("genWriteAll", { count: confirm.all.customers })}</span>
            <span className="text-xs font-normal text-muted-foreground">{details(confirm.all)}</span>
          </Button>
          <Button variant="outline" className={optionClass} disabled={answering} onClick={() => onAnswer("sample")}>
            <span className="font-medium">{t("genWriteSample", { count: confirm.sample.per_day })}</span>
            <span className="text-xs font-normal text-muted-foreground">
              {t("genSampleHint", { count: confirm.sample.customers })} {details(confirm.sample)}
            </span>
          </Button>
        </div>
        {error !== null && (
          <p role="alert" className="space-y-1 rounded-lg border border-destructive/30 p-3 text-sm text-destructive">
            <span className="block">{t("genConfirmFailed")}</span>
            {error && <span className="block text-xs">{error}</span>}
          </p>
        )}
        <AlertDialogFooter className="min-w-0">
          <AlertDialogCancel disabled={answering} onClick={() => onAnswer("cancel")}>{t("cancel")}</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
