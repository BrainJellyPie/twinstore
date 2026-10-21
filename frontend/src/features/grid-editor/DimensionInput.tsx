import { useState } from "react";
import { Input } from "@/shared/components/ui/input";
import { MIN_DIM, MAX_DIM, clampDim } from "./gridDimensions";

interface DimensionInputProps {
  axis: "width" | "height";
  value: number;
  onChange: (value: number) => void;
}

export function DimensionInput({ axis, value, onChange }: DimensionInputProps) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <label className="flex items-center gap-1.5 text-muted-foreground">
      {axis === "width" ? "Width" : "Depth"}
      <Input
        type="number"
        min={MIN_DIM}
        max={MAX_DIM}
        step={1}
        value={draft ?? String(value)}
        onChange={(event) => {
          const raw = event.target.value;
          setDraft(raw);
          const next = Number(raw);
          // Keep partial typing (such as the first digit of 40) without resizing.
          if (Number.isInteger(next) && next >= MIN_DIM && next <= MAX_DIM) onChange(next);
        }}
        onBlur={(event) => {
          onChange(clampDim(Number(event.target.value)));
          setDraft(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
        className="h-8 w-20 text-foreground"
        data-testid={`grid-${axis}-input`}
      />
    </label>
  );
}
