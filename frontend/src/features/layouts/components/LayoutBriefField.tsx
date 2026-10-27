// The design brief, read into the generator's options by the text model: "Apply to the options" sets what the brief
// asks for (style, size, door, tills, theme, colors, seating, left-out categories) and lists what the options cannot
// express. The brief itself is still saved with the layout.

import { useId, useLayoutEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import { NeedsModel } from "@/features/settings/NeedsModel";
import type { TemplateChoice } from "../templateOptions";

const controlClass = "w-full rounded-md border bg-background px-2 py-1.5 text-xs";

export function LayoutBriefField({ value, onApply, onBriefChange }: {
  value: TemplateChoice;
  onApply: (patch: Partial<TemplateChoice>) => void;
  onBriefChange: (brief: string) => void;
}) {
  const id = useId();
  const { t } = useI18n();
  const brief = value.requirements ?? "";
  const length = Array.from(brief.trim()).length;
  const context = JSON.stringify(value);
  const [read, setRead] = useState<{ context: string; reading: api.BriefReading } | null>(null);
  const reader = useMutation({
    mutationFn: (request: { templateId: string; brief: string; options: Record<string, unknown> }) =>
      api.readLayoutBrief(request.templateId, { brief: request.brief, options: request.options }),
  });
  const reset = reader.reset;
  useLayoutEffect(() => reset(), [context, reset]);
  const request = () => {
    if (length < 5 || reader.isPending) return;
    const { templateId, sourceSetupId: _source, seed: _seed, currency: _currency, requirements: _brief, ...options } = value;
    reader.mutate({ templateId, brief: brief.trim(), options }, { onSuccess: (reading) => {
      const patch = reading.options as Partial<TemplateChoice>;
      setRead({ context: JSON.stringify({ ...value, ...patch }), reading });
      if (Object.keys(patch).length > 0) onApply(patch);
    } });
  };
  // A reply can update only the options and brief from which it was requested.
  const shown = read?.context === context ? read.reading : null;

  return (
    <div className="space-y-1.5 text-xs">
      <label htmlFor={id}>{t("layoutBriefLabel")}</label>
      <textarea id={id} className={controlClass} rows={2} value={brief} onChange={(e) => onBriefChange(Array.from(e.target.value).slice(0, 2000).join(""))}
        placeholder={t("layoutBriefPlaceholder")} />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="inline-flex items-center gap-1 rounded border px-2 py-1 hover:bg-muted disabled:opacity-50"
          disabled={length < 5 || reader.isPending} onClick={request}>
          {reader.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} {t("layoutBriefApply")}
        </button>
        <span className="text-muted-foreground">{t("layoutBriefHint")}</span>
      </div>
      {reader.error && <p role="alert" className="text-destructive">{reader.error.message}</p>}
      {reader.error && <NeedsModel purpose="assist" />}
      {shown && (
        <div className="space-y-1 rounded-md bg-muted/50 p-2" aria-label={t("layoutBriefApplied")}>
          {shown.rationale && <p className="text-muted-foreground">{shown.rationale}</p>}
          {shown.applied.length > 0
            ? <ul className="list-disc space-y-0.5 pl-4">{shown.applied.map((a) => <li key={a}>{a}</li>)}</ul>
            : <p>{t("layoutBriefNoOptions")}</p>}
          {shown.not_expressible.length > 0 && <p className="text-muted-foreground">{t("layoutBriefNotExpressible", { items: shown.not_expressible.join("; ") })}</p>}
          {shown.warnings.map((w) => <p key={w} className="text-muted-foreground">· {w}</p>)}
        </div>
      )}
    </div>
  );
}
