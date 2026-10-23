import { useEffect, useMemo } from "react";

import { useRun } from "@/shared/queries/useRun";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { useStoreAssets } from "@/features/store-viewer/hooks/useStoreAssets";
import { usePersonaData } from "@/features/playback/hooks/usePersonaData";
import { RunToolbar } from "@/features/runs/components/RunToolbar";
import { useRunOperations } from "@/features/runs/hooks";
import { currencyCode } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";

import { ProjectShell } from "@/views/simulation/ProjectShell";
import { SimulationLayout } from "@/views/simulation/SimulationLayout";
import { SidePanel } from "@/views/simulation/SidePanel";

import type { LayoutTabProps } from "./types";

export function PlaybackView({
  pid,
  runId,
  location,
  setupStatus,
  personaCount,
  layouts,
  selectedSetupId,
  onLayoutSelect,
  onAddLayout,
}: { pid: string; runId: string; location: string; setupStatus: string; personaCount: number } & LayoutTabProps) {
  const { t } = useI18n();
  const run = useRun(pid, runId).data;
  const operations = useRunOperations(pid, runId).data;
  const crew = useMemo(() => operations?.config.crew != null
    ? { tasks: operations.crew_tasks ?? [], crew: operations.config.crew, schedule: operations.config.crew_schedule ?? {},
        shifts: operations.config.crew_shifts ?? [],
        closing: Object.fromEntries(run.store.weekly_schedule.filter((d) => d.is_open).map((d) => [d.day, d.close_hour])) }
    : null, [operations, run.store.weekly_schedule]);
  const assets = useStoreAssets(run.store, run.customers);
  const { personaNames, personaGenders } = usePersonaData(run.personas);
  const activeTab = useSimulationStore((s) => s.activeTab);
  const sendAsk = useAssistStore((s) => s.send);
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);
  const setCurrency = useSimulationStore((s) => s.setCurrency);

  useEffect(() => {
    setCurrency(currencyCode(run.summary.currency));
  }, [run.summary.currency, setCurrency]);

  return (
    <ProjectShell
      layouts={layouts}
      selectedLayoutId={selectedSetupId}
      onLayoutSelect={onLayoutSelect}
      onAddLayout={onAddLayout}
      centerSlot={
        <SimulationLayout
          key={`${run.store.id}:${runId}`}
          storeId={run.store.id}
          assets={assets}
          personaNames={personaNames}
          personaGenders={personaGenders}
          customers={run.customers}
          heatmaps={run.heatmaps}
          rackStats={run.summary.racks ?? null}
          emptySpells={operations?.empty_spells ?? null}
          crew={crew}
          mode="playback"
          onAskAboutRack={(rack) => {
            sendAsk({ projectId: pid, destination: "run_question",
              text: rack.rack_name ? t("askAboutRack", { rack: rack.rack_name }) : t("askAboutThisShelf") });
            setActiveTab("dashboard");
          }}
        />
      }
      footerSlot={
        <RunToolbar
          projectId={pid}
          setupId={selectedSetupId}
          runId={runId}
          setupStatus={setupStatus}
          personaCount={personaCount}
          layouts={layouts}
        />
      }
      sidePanelSlot={
        <SidePanel
          mode="playback"
          customers={run.customers}
          minTime={assets.minTime}
          maxTime={assets.maxTime}
          store={run.store}
          summary={run.summary}
          personas={run.personas}
          location={location}
          editableLayout={false}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          projectId={pid}
          setupId={selectedSetupId}
          runId={runId}
        />
      }
    />
  );
}
