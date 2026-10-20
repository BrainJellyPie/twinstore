import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

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
  const qc = useQueryClient();
  const statusQuery = useRunStatus(pid, runId);
  const status = statusQuery.data;
  const assets = useStoreAssets(setup.store);
  const { personaNames, personaGenders } = usePersonaData(personas);
  const activeTab = useSimulationStore((s) => s.activeTab);
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);

  // Completion → show the new run. Failure → back to the previous view with the error
  // surfaced inline (instead of crashing into the route error boundary).
  useEffect(() => {
    const s = status?.status;
    if (s !== "completed" && s !== "failed") return;
    const store = useSimulationStore.getState();
    if (s === "completed") {
      store.setViewRunId(runId);
    } else {
      store.setLastRunError(status?.error || "Simulation failed");
    }
    void qc.invalidateQueries({ queryKey: queryKeys.runs(pid, setupId) });
    void qc.invalidateQueries({ queryKey: queryKeys.projectRuns(pid) });
    void qc.invalidateQueries({ queryKey: queryKeys.setup(pid, setupId) });
  }, [status?.status, status?.error, qc, pid, setupId, runId]);

  if (statusQuery.error) {
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
