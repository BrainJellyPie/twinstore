// Cross-field validation (close > open) lives in the parent's validate.ts; this
// component only renders error messages it receives. closeHour=24 means "24:00".

import { useI18n } from "@/shared/i18n/i18n";
import { cn } from "@/shared/utils/cn";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

const labelClass = "text-sm font-medium";
const errorTextClass = "text-xs text-destructive";
const errorBorderClass = "border-destructive focus-visible:border-destructive";

// Open range: 0–23; close range: 0–24. Label format: "H:00".
const OPEN_HOURS = Array.from({ length: 24 }, (_, i) => i); // 0..23
const CLOSE_HOURS = Array.from({ length: 25 }, (_, i) => i); // 0..24

export interface OpeningHoursFieldProps {
  openHour: number;
  closeHour: number;
  onOpenChange: (value: number) => void;
  onCloseChange: (value: number) => void;
  // Separate open / close errors. The cross-field message typically attaches to close.
  openError?: string;
  closeError?: string;
  disabled?: boolean;
}

export function OpeningHoursField({
  openHour,
  closeHour,
  onOpenChange,
  onCloseChange,
  openError,
  closeError,
  disabled,
}: OpeningHoursFieldProps) {
  const { t } = useI18n();
  return (
    <div className="space-y-1.5">
      <span className={labelClass}>{t("openingHours")}</span>
      <div className="flex items-center gap-3">
        <Select
          value={String(openHour)}
          onValueChange={(v) => onOpenChange(Number(v))}
          disabled={disabled}
        >
          <SelectTrigger
            id="setup-open-hour"
            className={cn("flex-1", openError && errorBorderClass)}
            aria-invalid={openError ? true : undefined}
            aria-label={t("openingTime")}
            aria-describedby={openError ? "setup-open-hour-error" : undefined}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPEN_HOURS.map((h) => (
              <SelectItem key={h} value={String(h)}>
                {h}:00
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">~</span>
        <Select
          value={String(closeHour)}
          onValueChange={(v) => onCloseChange(Number(v))}
          disabled={disabled}
        >
          <SelectTrigger
            id="setup-close-hour"
            className={cn("flex-1", closeError && errorBorderClass)}
            aria-invalid={closeError ? true : undefined}
            aria-label={t("closingTime")}
            aria-describedby={closeError ? "setup-close-hour-error" : undefined}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CLOSE_HOURS.map((h) => (
              <SelectItem key={h} value={String(h)}>
                {h}:00
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {(openError || closeError) && (
        <div className="space-y-0.5">
          {openError && <p id="setup-open-hour-error" role="alert" className={errorTextClass}>{openError}</p>}
          {closeError && <p id="setup-close-hour-error" role="alert" className={errorTextClass}>{closeError}</p>}
        </div>
      )}
    </div>
  );
}
