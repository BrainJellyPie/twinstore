// Delete a layout of the store, with the layouts made from it. A store keeps at least one layout, so the control is
// not offered when this layout's tree is every layout the store has.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";

import { deleteSetup } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { queryKeys } from "@/shared/queries/keys";

import { useLayouts } from "../hooks/useLayouts";
import { smoothScroll } from "@/shared/utils/motion";

export function DeleteLayout({ projectId, setupId }: { projectId: string; setupId: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data: layouts = [] } = useLayouts(projectId);
  const [confirming, setConfirming] = useState(false);
  const confirmBox = useRef<HTMLDivElement>(null);
  // The control sits at the end of a long panel: bring the question and its buttons into view.
  useEffect(() => { if (confirming) confirmBox.current?.scrollIntoView?.({ block: "nearest", behavior: smoothScroll() }); }, [confirming]);
  const remove = useMutation({
    mutationFn: () => deleteSetup(projectId, setupId),
    onSuccess: async () => {
      qc.removeQueries({ queryKey: queryKeys.setup(projectId, setupId) });  // gone: nothing should refetch it
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.setups(projectId) }),
        qc.invalidateQueries({ queryKey: queryKeys.project(projectId) }),
      ]);
    },
  });
  const layout = layouts.find((candidate) => candidate.id === setupId);
  // The layouts made from this one, at any depth: they go with it.
  const branches = new Set<string>();
  for (let grew = true; grew;) {
    grew = false;
    for (const candidate of layouts) {
      if (candidate.parentId && (candidate.parentId === setupId || branches.has(candidate.parentId)) && !branches.has(candidate.id)) {
        branches.add(candidate.id);
        grew = true;
      }
    }
  }
  if (!layout || layouts.length <= branches.size + 1) return null;

  return (
    <div className="mt-3 border-t pt-3 text-xs">
      {confirming ? (
        <div ref={confirmBox} role="group" aria-label={t("layoutDelete")} className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/[0.04] p-2.5">
          <p className="font-medium">{t("layoutDeleteConfirm", { name: layout.name })}</p>
          {branches.size > 0 && <p className="text-muted-foreground">{t("layoutDeleteBranches", { count: branches.size })}</p>}
          {remove.error && <p role="alert" className="text-destructive">{remove.error.message}</p>}
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="destructive" className="h-8" disabled={remove.isPending} onClick={() => remove.mutate()}>
              <Trash2 className="size-3.5" aria-hidden /> {t("layoutDeleteYes")}
            </Button>
            <Button type="button" size="sm" variant="outline" className="h-8" disabled={remove.isPending} onClick={() => { setConfirming(false); remove.reset(); }}>
              {t("cancel")}
            </Button>
          </div>
        </div>
      ) : (
        <button type="button" disabled={layout.status === "running"} onClick={() => setConfirming(true)}
          className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-destructive disabled:opacity-50">
          <Trash2 className="size-3.5" aria-hidden /> {t("layoutDelete")}
        </button>
      )}
    </div>
  );
}
