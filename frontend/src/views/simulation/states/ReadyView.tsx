import { useCallback, useState } from "react";

import { useSimulationStore } from "@/stores/simulationStore";
import { RunLauncherDialog } from "@/features/runs/components/RunLauncherDialog";
import { useStoreAssets } from "@/features/store-viewer/hooks/useStoreAssets";
import { usePersonaData } from "@/features/playback/hooks/usePersonaData";
import type { SetupDetailWithBlocked } from "@/features/grid-editor/types";

import { ProjectShell } from "@/views/simulation/ProjectShell";
import { SimulationLayout } from "@/views/simulation/SimulationLayout";
import { SidePanel } from "@/views/simulation/SidePanel";
import { computeSimulationAvailability } from "@/views/simulation/availability";

import type { LayoutTabProps, ViewCommon } from "./types";

export function ReadyView({
  pid,
  setupId,
  setup,
  personas,
  location,
  layouts,
  selectedSetupId,
  onLayoutSelect,
  onAddLayout,
}: ViewCommon & { setupId: string } & LayoutTabProps) {
  const [launcherOpen, setLauncherOpen] = useState(false);
  const availability = computeSimulationAvailability(setup.readiness);
  const assets = useStoreAssets(setup.store);
  const { personaNames, personaGenders } = usePersonaData(personas);
  const activeTab = useSimulationStore((s) => s.activeTab);
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);

  // Route FloorConfigurationPanel's busy state into ProjectShell.navigationDisabled.
  const [busy, setBusy] = useState(false);
  const onBusyChange = useCallback((b: boolean) => setBusy(b), []);

  const mode = "ready";
  const onSimulate = availability.canSimulate ? () => setLauncherOpen(true) : undefined;

  // null-safe itemCount — setup.store.racks may be empty right after a Step 1 force-edit.
  const itemCount =
    setup.store?.racks?.reduce(
      (sum, rack) =>
        sum +
        (rack.slots ?? []).reduce(
          (slotSum, slot) => slotSum + (slot.items?.length ?? 0),
          0,
        ),
      0,
    ) ?? 0;

  // SetupDetail.blocked_faces is optional for legacy compatibility — coerce to []
  // so SidePanel sees the SetupDetailWithBlocked shape it expects.
  const setupForPanel: SetupDetailWithBlocked = {
    ...setup,
    blocked_faces: setup.blocked_faces ?? [],
  };

  return (
    <ProjectShell
      layouts={layouts}
      selectedLayoutId={selectedSetupId}
      onLayoutSelect={onLayoutSelect}
      onAddLayout={onAddLayout}
      navigationDisabled={busy}
      centerSlot={
        <SimulationLayout
          key={setup.id}
          storeId={setup.store.id}
          assets={assets}
          personaNames={personaNames}
          personaGenders={personaGenders}
          customers={null}
          heatmaps={null}
          mode={mode}
          overlay={
            <RunLauncherDialog
              open={launcherOpen}
              onOpenChange={setLauncherOpen}
              projectId={pid}
              setupId={setupId}
              personaCount={personas.length}
            />
          }
        />
      }
      sidePanelSlot={
        <SidePanel
          mode={mode}
          customers={null}
          minTime={assets.minTime}
          maxTime={assets.maxTime}
          store={setup.store}
          summary={null}
          personas={personas}
          location={location}
          onSimulate={onSimulate}
          simulating={false}
          availability={availability}
          projectId={pid}
          setupId={setupId}
          editableLayout={true}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          setup={setupForPanel}
          itemCount={itemCount}
          onBusyChange={onBusyChange}
        />
      }
    />
  );
}
