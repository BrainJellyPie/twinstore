// A field for a whole number within limits. What is typed stays as typed, so an emptied field can be retyped, and
// counts as soon as it is a whole number in range; leaving the field brings it back within the limits.
import { useState, type ComponentProps } from "react";

import { Input } from "@/shared/components/ui/input";

type Props = Omit<ComponentProps<typeof Input>, "type" | "value" | "onChange" | "min" | "max"> & {
  value: number; min: number; max: number; onChange: (value: number) => void;
};

export function WholeNumberInput({ value, min, max, onChange, onBlur, ...props }: Props) {
  const [draft, setDraft] = useState<{ text: string; value: number } | null>(null);
  // A replacement setting must discard text belonging to the previous value.
  if (draft !== null && draft.value !== value) setDraft(null);
  return (
    <Input step={1} {...props} type="number" min={min} max={max} value={draft?.text ?? String(value)}
      onChange={(e) => {
        const next = Number(e.target.value);
        const accepted = e.target.value !== "" && Number.isInteger(next) && next >= min && next <= max;
        setDraft({ text: e.target.value, value: accepted ? next : value });
        if (accepted) onChange(next);
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
