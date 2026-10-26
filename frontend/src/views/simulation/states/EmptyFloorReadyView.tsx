import { useCallback, useEffect, useState } from "react";

import { useSimulationStore } from "@/stores/simulationStore";
import type { SetupDetail } from "@/shared/api/client";
import type { Persona } from "@/shared/types/domain";
import type { SetupDetailWithBlocked } from "@/features/grid-editor/types";

import { ProjectShell } from "@/views/simulation/ProjectShell";
import { SidePanel } from "@/views/simulation/SidePanel";
import { EmptyFloorSlot } from "@/views/simulation/EmptyFloorSlot";

import type { LayoutTabProps } from "./types";

export function EmptyFloorReadyView({
  pid,
  setupId,
  setup,
  personas,
  location,
  layouts,
  selectedSetupId,
  onLayoutSelect,
  onAddLayout,
}: { pid: string; setupId: string; setup: SetupDetail; personas: Persona[]; location: string } & LayoutTabProps) {
  const activeTab = useSimulationStore((s) => s.activeTab);
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);

  // A layout without a floor has only its setup steps to show: open on them, not on an empty store tab.
  useEffect(() => { if (useSimulationStore.getState().activeTab === "settings") setActiveTab("dashboard"); }, [setup.id, setActiveTab]);

  const [busy, setBusy] = useState(false);
  const onBusyChange = useCallback((b: boolean) => setBusy(b), []);

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
      centerSlot={<EmptyFloorSlot key={setup.id} />}
      sidePanelSlot={
        <SidePanel
          mode="ready"
          customers={null}
          minTime={0}
          maxTime={0}
          store={null}
          summary={null}
          personas={personas}
          location={location}
          // Without a floor, simulation cannot be entered — onSimulate/availability omitted.
          editableLayout={true}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          projectId={pid}
          setupId={setupId}
          setup={setupForPanel}
          itemCount={0}
          onBusyChange={onBusyChange}
        />
      }
    />
  );
}
