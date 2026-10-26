// Bring a tested online variant's prices to the physical twin: the run's copy of the variant against its control,
// matched to a layout's products by SKU, reviewed on the chosen layout and kept as a new layout. Design, pictures and
// ads stay online and are listed as such.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";

import * as api from "@/shared/api/client";
import { getRunStoreChanges, onlineKeys } from "@/shared/api/online";
import { queryKeys } from "@/shared/queries/keys";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { KeepAsLayout } from "@/features/marketing/KeepAsLayout";
import { useExperimentDraft } from "@/stores/experimentDraftStore";

// What one A/B variant may hold (the marketing API's limits).
const AB_MAX_CHANGES = 20;
const AB_NAME_LENGTH = 40;

export function PricesToStore({ projectId, runId, variant }: { projectId: string; runId: string; variant: number }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const sendDraft = useExperimentDraft((s) => s.send);
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
  if (found.error) return (
    <p role="alert" className="px-1.5 text-xs text-destructive">
      {found.error.message}{" "}
      <button type="button" onClick={() => void found.refetch()} disabled={found.isFetching} className="underline disabled:opacity-50">
        {t("analystRetry")}
      </button>
    </p>
  );
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
      {changes.changes.length <= AB_MAX_CHANGES ? (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.7rem] text-muted-foreground">
          <Button type="button" variant="outline" size="sm" className="h-8 gap-1.5 text-xs" onClick={() => {
            sendDraft(projectId, {
              setup_id: setupId, engine: "rule", panel: 300, focus_skus: [],
              variants: [{ name: Array.from(changes.name).slice(0, AB_NAME_LENGTH).join("").trimEnd(), changes: changes.changes }],
            });
            void navigate({ to: "/marketing/$pid", params: { pid: projectId } });
          }}>
            <FlaskConical className="size-3.5" aria-hidden /> {t("onTestInStore")}
          </Button>
          <span>{t("onTestInStoreHint")}</span>
        </div>
      ) : (
        <p className="mt-1.5 text-[0.7rem] text-muted-foreground">{t("onTestInStoreTooMany", { count: changes.changes.length })}</p>
      )}
      {changes.skipped.length > 0 && (
        <div className="mt-1.5 text-[0.7rem] text-muted-foreground">
          <span className="font-medium">{t("onKeepStaysOnline")}</span>{" "}
          {changes.skipped.join(" · ")}
        </div>
      )}
    </div>
  );
}
