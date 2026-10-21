import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/shared/components/ui/toggle-group";

import type { WorkingDayPreset } from "../validate";

const OPTIONS: readonly { value: WorkingDayPreset; label: MessageKey }[] = [
  { value: "7",       label: "sevenDays" },
  { value: "weekday", label: "weekdays" },
  { value: "weekend", label: "weekends" },
];

export interface WeeklyScheduleFieldProps {
  value: WorkingDayPreset;
  onChange: (value: WorkingDayPreset) => void;
  disabled?: boolean;
}

export function WeeklyScheduleField({
  value,
  onChange,
  disabled,
}: WeeklyScheduleFieldProps) {
  const { t } = useI18n();
  return (
    <div className="space-y-1.5">
      <span className="text-sm font-medium">{t("workingDay")}</span>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        spacing={1}
        className="w-full flex-wrap"
        value={value}
        onValueChange={(v) => {
          if (v) onChange(v as WorkingDayPreset);
        }}
        disabled={disabled}
        aria-label={t("workingDay")}
      >
        {OPTIONS.map((opt) => (
          <ToggleGroupItem
            key={opt.value}
            value={opt.value}
            aria-label={t(opt.label)}
            className="text-xs data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:hover:bg-primary data-[state=on]:hover:text-primary-foreground"
          >
            {t(opt.label)}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
