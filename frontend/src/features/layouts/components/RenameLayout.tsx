// Rename a layout, so layouts made the same way can be told apart. A finalized layout keeps its name, like the rest
// of it (the server refuses any change once a final run has used it).

import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { saveSetup } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import { queryKeys } from "@/shared/queries/keys";

import { useLayouts } from "../hooks/useLayouts";

export function RenameLayout({ projectId, setupId }: { projectId: string; setupId: string }) {
  const { t } = useI18n();
  const id = useId();
  const qc = useQueryClient();
  const { data: layouts = [] } = useLayouts(projectId);
  const [draft, setDraft] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (name: string) => saveSetup(projectId, setupId, { name }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.setups(projectId) }),
        qc.invalidateQueries({ queryKey: queryKeys.setup(projectId, setupId) }),
      ]);
      setDraft(null);  // after the refetch, so the field does not show the old name in between
    },
  });
  const layout = layouts.find((candidate) => candidate.id === setupId);
  if (!layout || layout.status === "locked") return null;
  const name = draft ?? layout.name;
  const changed = name.trim() !== "" && name.trim() !== layout.name;

  return (
    // Controls stay enabled while saving, so the button pressed or the field typed in keeps keyboard focus.
    <form className="mt-3 border-t pt-3 text-xs" onSubmit={(e) => { e.preventDefault(); if (changed && !save.isPending) save.mutate(name.trim()); }}>
      <label htmlFor={id} className="mb-1 block text-muted-foreground">{t("layoutNameLabel")}</label>
      <div className="flex gap-2">
        <Input id={id} value={name} maxLength={300} className="h-8 text-xs"
          onChange={(e) => { setDraft(e.target.value); save.reset(); }} />
        <Button type="submit" size="sm" variant="outline" className="h-8 shrink-0 aria-disabled:opacity-50" aria-disabled={!changed}>{t("layoutRename")}</Button>
      </div>
      {save.error && <p role="alert" className="mt-1 text-destructive">{save.error.message}</p>}
      <p role="status" className="mt-1 text-muted-foreground empty:hidden">{save.isSuccess ? t("studioSaved") : ""}</p>
    </form>
  );
}
