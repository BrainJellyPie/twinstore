import { BarChart3, Settings2, UsersRound } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { DashboardPanel } from "@/features/dashboard/components/DashboardPanel";
import { SettingsPanel } from "@/features/dashboard/components/SettingsPanel";
import { ShopperPanel } from "@/features/shoppers/ShopperPanel";
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
    <aside className="panel m-3 flex w-auto min-w-0 shrink-0 flex-col overflow-y-auto rounded-[1.6rem] md:w-[24rem]">
      <Tabs value={activeTab === "shoppers" && mode !== "playback" ? "dashboard" : activeTab} onValueChange={(v) => setActiveTab(v as DashboardTab)} className="gap-0">
        <div className="sticky top-0 z-10 border-b border-glass-border bg-[var(--glass-strong)] px-3 pt-3 pb-2.5 backdrop-blur-xl">
          <TabsList className="h-11 w-full rounded-xl">
            <TabsTrigger value="dashboard" className="gap-1.5 rounded-[0.65rem] text-sm"><BarChart3 className="size-4" />Results</TabsTrigger>
            {mode === "playback" && <TabsTrigger value="shoppers" className="gap-1.5 rounded-[0.65rem] text-sm"><UsersRound className="size-4" />Shoppers</TabsTrigger>}
            <TabsTrigger value="settings" className="gap-1.5 rounded-[0.65rem] text-sm"><Settings2 className="size-4" />{mode === "playback" ? "Store" : <>Store &amp; layout</>}</TabsTrigger>
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
                availability={availability}
              />
            ) : null
          )}
        </TabsContent>
        {mode === "playback" && store != null && projectId && runId && customers && (
          <TabsContent value="shoppers" className="px-3">
            <ShopperPanel projectId={projectId} runId={runId} customers={customers} personas={personas} store={store} />
          </TabsContent>
        )}
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
