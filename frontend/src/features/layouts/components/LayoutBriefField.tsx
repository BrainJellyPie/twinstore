// The design brief, read into the generator's options by the text model: "Apply to the options" sets what the brief
// asks for (style, size, door, tills, theme, colors, seating, left-out categories) and lists what the options cannot
// express. The brief itself is still saved with the layout.

import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import type { TemplateChoice } from "../templateOptions";

const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";

export function LayoutBriefField({ value, onApply, onBriefChange }: {
  value: TemplateChoice;
  onApply: (patch: Partial<TemplateChoice>) => void;
  onBriefChange: (brief: string) => void;
}) {
  const id = useId();
  const brief = value.requirements ?? "";
  const length = Array.from(brief.trim()).length;
  const [read, setRead] = useState<{ brief: string; templateId: string; reading: api.BriefReading } | null>(null);
  const reader = useMutation({
    mutationFn: ({ text }: { text: string; templateId: string }) => {
      const { templateId: _id, sourceSetupId: _source, seed: _seed, currency: _currency, requirements: _brief, ...options } = value;
      return api.readLayoutBrief(value.templateId, { brief: text.trim(), options });
    },
    onSuccess: (reading, { text, templateId }) => {
      setRead({ brief: text, templateId, reading });
      if (Object.keys(reading.options).length > 0) onApply(reading.options as Partial<TemplateChoice>);
    },
  });
  // A reading belongs to the brief and the format it was made for.
  const shown = read && read.brief === brief && read.templateId === value.templateId ? read.reading : null;

  return (
    <div className="space-y-1.5 text-xs">
      <label htmlFor={id}>Additional design brief</label>
      <textarea id={id} className={controlClass} rows={2} maxLength={2000} value={brief} onChange={(e) => onBriefChange(e.target.value)}
        placeholder="For example: a calm loop with two tills by the door, botanical look with sage walls, no alcohol." />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="inline-flex items-center gap-1 rounded border px-2 py-1 hover:bg-muted disabled:opacity-50"
          disabled={length < 5 || reader.isPending} onClick={() => reader.mutate({ text: brief, templateId: value.templateId })}>
          {reader.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} Apply to the options
        </button>
        <span className="text-muted-foreground">Sets what the brief asks for; you can still change every option.</span>
      </div>
      {reader.error && <p role="alert" className="text-destructive">{reader.error.message}</p>}
      {shown && (
        <div className="space-y-1 rounded-md bg-muted/50 p-2" aria-label="Brief applied">
          {shown.rationale && <p className="text-muted-foreground">{shown.rationale}</p>}
          {shown.applied.length > 0
            ? <ul className="list-disc space-y-0.5 pl-4">{shown.applied.map((a) => <li key={a}>{a}</li>)}</ul>
            : <p>The brief did not ask for anything the options can set.</p>}
          {shown.not_expressible.length > 0 && <p className="text-muted-foreground">Not set by the options (kept in the brief): {shown.not_expressible.join("; ")}.</p>}
          {shown.warnings.map((w) => <p key={w} className="text-muted-foreground">· {w}</p>)}
        </div>
      )}
    </div>
  );
}
