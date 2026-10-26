import { BarChart3, ChevronRight, Crosshair, Settings2, UsersRound } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { DashboardPanel } from "@/features/dashboard/components/DashboardPanel";
import { SettingsPanel } from "@/features/dashboard/components/SettingsPanel";
import { ShopperPanel } from "@/features/shoppers/ShopperPanel";
import type { Store, Persona, CustomerResult } from "@/shared/types/domain";
import type { RunStatus, RunSummary } from "@/shared/api/client";
import type { DashboardTab } from "@/stores/simulationStore";
import type { SetupDetailWithBlocked } from "@/features/grid-editor/types";
import { useI18n } from "@/shared/i18n/i18n";
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
  const { t } = useI18n();
  return (
    <aside className="panel m-3 flex w-auto min-w-0 shrink-0 flex-col overflow-y-auto rounded-[1.6rem] md:w-[24rem]">
      <Tabs value={activeTab === "shoppers" && mode !== "playback" ? "dashboard" : activeTab} onValueChange={(v) => setActiveTab(v as DashboardTab)} className="gap-0">
        <div className="sticky top-0 z-10 border-b border-glass-border bg-[var(--glass-strong)] px-3 pt-3 pb-2.5 backdrop-blur-xl">
          <TabsList className="h-11 w-full rounded-xl">
            <TabsTrigger value="dashboard" className="min-w-0 gap-1.5 rounded-[0.65rem] px-1.5 text-sm sm:px-2.5"><BarChart3 className="hidden size-4 sm:block" /><span className="truncate">{t("spResults")}</span></TabsTrigger>
            {mode === "playback" && <TabsTrigger value="shoppers" className="min-w-0 gap-1.5 rounded-[0.65rem] px-1.5 text-sm sm:px-2.5"><UsersRound className="hidden size-4 sm:block" /><span className="truncate">{t("spShoppers")}</span></TabsTrigger>}
            <TabsTrigger value="settings" className="min-w-0 gap-1.5 rounded-[0.65rem] px-1.5 text-sm sm:px-2.5"><Settings2 className="hidden size-4 sm:block" /><span className="truncate">{mode === "playback" ? t("store") : t("spStoreLayout")}</span></TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="dashboard" className="px-3">
          {mode === "playback" && store != null && projectId && runId && customers && (
            <button type="button" onClick={() => setActiveTab("shoppers")}
              className="group relative mt-3 mb-1 flex w-full items-center gap-3 overflow-hidden rounded-2xl p-3 text-left text-white dark:text-neutral-950 shadow-[0_12px_32px_-12px_var(--heat-2)] heat-gradient transition-transform hover:scale-[1.01] active:scale-[0.99]">
              <span className="pointer-events-none absolute inset-0 bg-[linear-gradient(110deg,transparent_35%,rgb(255_255_255/0.25)_50%,transparent_65%)] bg-[length:250%_100%] animate-shimmer" aria-hidden />
              <span className="relative grid size-10 shrink-0 place-items-center rounded-xl bg-white/20 backdrop-blur"><Crosshair className="size-5" aria-hidden /></span>
              <span className="relative min-w-0 flex-1">
                <span className="block text-sm font-semibold">{t("spTrackCta")}</span>
                <span className="block text-[0.72rem] leading-snug">{t("spTrackHint")}</span>
              </span>
              <ChevronRight className="relative size-5 shrink-0 transition-transform group-hover:translate-x-0.5" aria-hidden />
            </button>
          )}
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
              setupId={setupId}
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
