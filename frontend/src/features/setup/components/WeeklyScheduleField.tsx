import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/shared/components/ui/toggle-group";

import type { WorkingDayPreset } from "../validate";

const OPTIONS: readonly { value: WorkingDayPreset; label: string }[] = [
  { value: "7",       label: "7 Days" },
  { value: "weekday", label: "Weekday (Mon-Fri)" },
  { value: "weekend", label: "Weekend (Sat-Sun)" },
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
  return (
    <div className="space-y-1.5">
      <span className="text-sm font-medium">Working day</span>
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
        aria-label="Working day"
      >
        {OPTIONS.map((opt) => (
          <ToggleGroupItem
            key={opt.value}
            value={opt.value}
            aria-label={opt.label}
            className="text-xs data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:hover:bg-primary data-[state=on]:hover:text-primary-foreground"
          >
            {opt.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
