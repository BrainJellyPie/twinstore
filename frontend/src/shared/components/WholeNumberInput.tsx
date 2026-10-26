// A field for a whole number within limits. What is typed stays as typed, so an emptied field can be retyped, and
// counts as soon as it is a whole number in range; leaving the field brings it back within the limits.
import { useState, type ComponentProps } from "react";

import { Input } from "@/shared/components/ui/input";

type Props = Omit<ComponentProps<typeof Input>, "type" | "value" | "onChange" | "min" | "max"> & {
  value: number; min: number; max: number; onChange: (value: number) => void;
};

export function WholeNumberInput({ value, min, max, onChange, onBlur, ...props }: Props) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <Input step={1} {...props} type="number" min={min} max={max} value={draft ?? String(value)}
      onChange={(e) => {
        setDraft(e.target.value);
        const next = Number(e.target.value);
        if (e.target.value !== "" && Number.isInteger(next) && next >= min && next <= max) onChange(next);
      }}
      onBlur={(e) => {
        const next = Number(e.target.value);
        // An emptied or unreadable field goes back to the last number it held.
        onChange(e.target.value === "" || !Number.isFinite(next) ? value : Math.min(max, Math.max(min, Math.round(next))));
        setDraft(null);
        onBlur?.(e);
      }} />
  );
}
