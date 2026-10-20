import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { DashboardPanel } from "@/features/dashboard/components/DashboardPanel";
import { SettingsPanel } from "@/features/dashboard/components/SettingsPanel";
import type { Store, Persona, CustomerResult } from "@/shared/types/domain";
import type { RunStatus, RunSummary } from "@/shared/api/client";
import type { DashboardTab } from "@/stores/simulationStore";
import type { SetupDetailWithBlocked } from "@/features/grid-editor/types";
import { type Availability } from "./availability";

export interface SidePanelProps {
  mode: "ready" | "running" | "playback";
  customers: CustomerResult[] | null;
  minTime: number;
  maxTime: number;
  // null is allowed because ready mode accepts setups with no floor yet.
  // DashboardPanel(mode='ready') and SettingsPanel both guard the store==null case.
  store: Store | null;
  summary: RunSummary | null;
  personas: Persona[];
  location: string;
  onSimulate?: () => void;
  simulating?: boolean;
  simulateError?: Error | null;
  availability?: Availability;
  projectId?: string;
  setupId?: string;
  editableLayout?: boolean;
  activeTab: DashboardTab;
  setActiveTab: (tab: DashboardTab) => void;
  // ready-mode only — passed from $pid.tsx ReadyView.
  setup?: SetupDetailWithBlocked;
  itemCount?: number;
  onBusyChange?: (busy: boolean) => void;
  // playback-mode only — enables the run KPI / diagnostics / validation sections.
  runId?: string;
  // running-mode only — live progress.
  runStatus?: RunStatus;
}

export function SidePanel({
  mode,
  customers,
  minTime,
  maxTime,
  store,
  summary,
  personas,
  location,
  onSimulate,
  simulating,
  simulateError,
  availability,
  projectId,
  setupId,
  editableLayout,
  activeTab,
  setActiveTab,
  setup,
  itemCount,
  onBusyChange,
  runId,
  runStatus,
}: SidePanelProps) {
  return (
    <aside className="flex h-full w-[23rem] shrink-0 flex-col overflow-y-auto border-l bg-surface">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as DashboardTab)} className="gap-0">
        <div className="sticky top-0 z-10 bg-surface/90 px-3 pt-3 pb-2 backdrop-blur">
          <TabsList className="h-10 w-full rounded-xl">
            <TabsTrigger value="dashboard" className="rounded-lg text-sm">Results</TabsTrigger>
            <TabsTrigger value="settings" className="rounded-lg text-sm">Store &amp; layout</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="dashboard" className="px-3">
          {mode === "playback" && store != null ? (
            <DashboardPanel
              mode="playback"
              customers={customers}
              minTime={minTime}
              maxTime={maxTime}
              store={store}
              summary={summary}
              projectId={projectId}
              runId={runId}
            />
          ) : mode === "running" ? (
            <DashboardPanel mode="running" status={runStatus} />
          ) : (
            // ready mode — these props are passed by ReadyView; undefined indicates a
            // miswired caller. Explicit guard acts as a runtime safety net.
            setup != null && projectId != null && setupId != null && itemCount != null ? (
              <DashboardPanel
                mode="ready"
                pid={projectId}
                sid={setupId}
                setup={setup}
                itemCount={itemCount}
                onBusyChange={onBusyChange}
                onSimulate={onSimulate}
                simulating={simulating}
                simulateError={simulateError}
                availability={availability}
              />
            ) : null
          )}
        </TabsContent>
        <TabsContent value="settings" className="px-3">
          <SettingsPanel
            store={store}
            summary={summary}
            personas={personas}
            location={location}
            projectId={projectId}
            setupId={setupId}
            editableLayout={editableLayout ?? false}
          />
        </TabsContent>
      </Tabs>
    </aside>
  );
}
