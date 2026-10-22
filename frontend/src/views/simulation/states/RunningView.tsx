import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useI18n } from "@/shared/i18n/i18n";
import { useRunStatus } from "@/shared/queries/useRunStatus";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { useStoreAssets } from "@/features/store-viewer/hooks/useStoreAssets";
import { usePersonaData } from "@/features/playback/hooks/usePersonaData";

import { ProjectShell } from "@/views/simulation/ProjectShell";
import { SimulationLayout } from "@/views/simulation/SimulationLayout";
import { SidePanel } from "@/views/simulation/SidePanel";

import type { LayoutTabProps, ViewCommon } from "./types";

export function RunningView({
  pid,
  setupId,
  runId,
  setup,
  personas,
  location,
  layouts,
  selectedSetupId,
  onLayoutSelect,
  onAddLayout,
}: ViewCommon & { setupId: string; runId: string } & LayoutTabProps) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const statusQuery = useRunStatus(pid, runId);
  const status = statusQuery.data;
  const assets = useStoreAssets(setup.store);
  const { personaNames, personaGenders } = usePersonaData(personas);
  const activeTab = useSimulationStore((s) => s.activeTab);
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);

  // Completion → show the new run. Failure → back to the previous view, which shows the
  // failure from this layout's run list (instead of crashing into the route error boundary).
  useEffect(() => {
    const s = status?.status;
    if (s !== "completed" && s !== "failed") return;
    if (s === "completed") useSimulationStore.getState().setViewRunId(runId);
    void qc.invalidateQueries({ queryKey: queryKeys.runs(pid, setupId) });
    void qc.invalidateQueries({ queryKey: queryKeys.projectRuns(pid) });
    void qc.invalidateQueries({ queryKey: queryKeys.setup(pid, setupId) });
    void qc.invalidateQueries({ queryKey: queryKeys.setups(pid), exact: true });
    void qc.invalidateQueries({ queryKey: queryKeys.projects(), exact: true });
  }, [status?.status, qc, pid, setupId, runId]);

  // A failed poll after the first answer keeps the last progress and keeps polling.
  if (statusQuery.error && !status) {
    throw statusQuery.error;
  }

  // While a final run is in progress the setup is locked (status="running") on the
  // backend, so PUT /slots is rejected with 409 — the editing entry point stays hidden.
  return (
    <ProjectShell
      layouts={layouts}
      selectedLayoutId={selectedSetupId}
      onLayoutSelect={onLayoutSelect}
      onAddLayout={onAddLayout}
      centerSlot={
        <SimulationLayout
          key={setup.id}
          storeId={setup.store.id}
          assets={assets}
          personaNames={personaNames}
          personaGenders={personaGenders}
          customers={null}
          heatmaps={null}
          mode="running"
          overlay={statusQuery.error ? (
            <p role="status" className="glass pointer-events-none absolute bottom-3 left-1/2 z-10 -translate-x-1/2 rounded-full border px-3 py-1 text-xs text-muted-foreground shadow-float">
              {t("reconnecting")}
            </p>
          ) : null}
        />
      }
      sidePanelSlot={
        <SidePanel
          mode="running"
          customers={null}
          minTime={assets.minTime}
          maxTime={assets.maxTime}
          store={setup.store}
          summary={null}
          personas={personas}
          location={location}
          editableLayout={false}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          runStatus={status}
        />
      }
    />
  );
}
