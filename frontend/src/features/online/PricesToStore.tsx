// Bring a tested online variant's prices to the physical twin: the run's copy of the variant against its control,
// matched to a layout's products by SKU, reviewed on the chosen layout and kept as a new layout. Design, pictures and
// ads stay online and are listed as such.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import * as api from "@/shared/api/client";
import { getRunStoreChanges, onlineKeys } from "@/shared/api/online";
import { queryKeys } from "@/shared/queries/keys";
import { useI18n } from "@/shared/i18n/i18n";
import { KeepAsLayout } from "@/features/marketing/KeepAsLayout";

export function PricesToStore({ projectId, runId, variant }: { projectId: string; runId: string; variant: number }) {
  const { t } = useI18n();
  const found = useQuery({
    queryKey: onlineKeys.storeChanges(projectId, runId, variant),
    queryFn: ({ signal }) => getRunStoreChanges(projectId, runId, variant, signal),
    staleTime: Infinity,  // a run's copy of its stores never changes
  });
  const { data: setups = [] } = useQuery({ queryKey: queryKeys.setups(projectId), queryFn: ({ signal }) => api.getSetups(projectId, signal) });
  const { data: project } = useQuery({ queryKey: queryKeys.project(projectId), queryFn: ({ signal }) => api.getProject(projectId, signal) });
  const [picked, setPicked] = useState("");
  const active = project?.state.activeSetupId ?? "";
  const setupId = setups.some((s) => s.id === picked) ? picked
    : setups.some((s) => s.id === active) ? active : setups[setups.length - 1]?.id ?? "";
  const changes = found.data;
  if (!changes || changes.changes.length === 0 || !setupId) return null;

  return (
    <div className="px-1.5">
      <label className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {t("onKeepLayout")}
        <select value={setupId} onChange={(e) => setPicked(e.target.value)}
          className="h-8 min-w-0 max-w-full flex-1 rounded-lg border bg-card px-2 text-xs text-foreground sm:flex-none">
          {setups.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </label>
      <KeepAsLayout key={setupId} projectId={projectId} setupId={setupId} currency={changes.currency} hint={t("onKeepHint")}
        variant={{ name: changes.name, changes: changes.changes }} />
      {changes.skipped.length > 0 && (
        <div className="mt-1.5 text-[0.7rem] text-muted-foreground">
          <span className="font-medium">{t("onKeepStaysOnline")}</span>{" "}
          {changes.skipped.join(" · ")}
        </div>
      )}
    </div>
  );
}
