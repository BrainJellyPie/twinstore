// Keep a tested variant in the physical twin: its edits, reviewed on the tested layout as it is now, saved as a new
// layout (the original stays). A tested price becomes the everyday price; a test-only package is not kept.

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Store } from "lucide-react";

import { applyLayoutEdit, checkLayoutEdit, type Variant } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { useI18n } from "@/shared/i18n/i18n";
import { focusOnMount } from "@/shared/utils/focusOnMount";

export function KeepAsLayout({ projectId, setupId, variant, currency, hint, label }: {
  projectId: string; setupId: string; variant: Variant;
  /** The currency of the variant's prices, checked against the layout's (changes made in another store). */
  currency?: string; hint?: string;
  /** The variant's name, for screen readers where several variants each offer this. */
  label?: string;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [requestId] = useState(() => crypto.randomUUID().replace(/-/g, ""));
  const check = useMutation({ mutationFn: () => checkLayoutEdit(projectId, setupId, { name: variant.name, changes: variant.changes, currency }) });
  const save = useMutation({
    mutationFn: () => applyLayoutEdit(projectId, setupId, {
      name: variant.name, changes: check.data!.changes, source_sha256: check.data!.source_sha256, request_id: requestId,
    }),
    onSuccess: () => Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.setups(projectId) }),
      qc.invalidateQueries({ queryKey: queryKeys.project(projectId) }),
    ]),
  });
  const review = check.data;

  return (
    <div className="mt-2 space-y-2 rounded-xl border border-dashed p-3 text-xs">
      <div className="flex items-center gap-1.5 font-semibold text-foreground"><Store className="size-3.5 text-primary" aria-hidden />{t("mkKeepTitle")}</div>
      {/* The button pressed is replaced, so focus moves to what replaced it rather than dropping to the page. */}
      {save.data ? (
        <p ref={focusOnMount} tabIndex={-1} role="status" className="flex items-center gap-1.5 rounded-md font-medium text-positive outline-offset-4">
          <Check className="size-3.5" aria-hidden />{t("mkKeepSaved", { name: save.data.name })}
        </p>
      ) : review ? (
        <div ref={focusOnMount} tabIndex={-1} className="space-y-1.5 rounded-md outline-offset-4">
          {review.applied.length > 0
            ? <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">{review.applied.map((a) => <li key={a}>{a}</li>)}</ul>
            : <p className="text-muted-foreground">{t("editWordsNone")}</p>}
          {review.warnings.map((w) => <p key={w} className="text-muted-foreground">· {w}</p>)}
          {review.applied.length > 0 && (
            <Button size="sm" className="gap-1.5" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" aria-hidden />} {t("editWordsSave")}
            </Button>
          )}
        </div>
      ) : (
        <>
          <p className="text-muted-foreground">{hint ?? t("mkKeepHint")}</p>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={() => check.mutate()} disabled={check.isPending}
            aria-label={label ? t("mkKeepReviewOf", { name: label }) : undefined}>
            {check.isPending && <Loader2 className="animate-spin" aria-hidden />} {t("mkKeepReview")}
          </Button>
        </>
      )}
      {(check.error ?? save.error) && <p role="alert" className="text-destructive">{(check.error ?? save.error)!.message}</p>}
    </div>
  );
}
