import { useI18n } from "@/shared/i18n/i18n";
import { useEffect, useState } from "react";
import type { CustomerResult, Store } from "@/shared/types/domain";
import type { RunStatus, RunSummary } from "@/shared/api/client";
import type { SetupDetailWithBlocked } from "@/features/grid-editor/types";
import { Lock } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { RunProgress } from "@/features/runs/components/RunProgress";
import { RunKpis } from "@/features/runs/components/RunKpis";
import { DiagnosticsSection } from "@/features/runs/components/DiagnosticsSection";
import { RunAnalystSection } from "@/features/runs/components/RunAnalystSection";
import { FidelitySection } from "@/features/runs/components/FidelitySection";
import { MovementSection } from "@/features/runs/components/MovementSection";
import { VisionGlancesSection } from "@/features/runs/components/VisionGlancesSection";
import { PreviewRunsList } from "@/features/runs/components/PreviewRunsList";
import { FloorConfigurationPanel } from "@/features/grid-editor/FloorConfigurationPanel";
import { LayoutExcelControls } from "@/features/layouts/components/LayoutExcelControls";
import { ProductBulkEditor } from "@/features/products/ProductBulkEditor";
import { LibraryPhotos } from "@/features/products/LibraryPhotos";
import { RackCopy } from "@/features/products/RackCopy";
import { StarterFill } from "@/features/products/StarterFill";
import { reasonIcon, reasonLabel, type Availability } from "@/views/simulation/availability";
import { PlaybackStatus } from "./sections/PlaybackStatus";
import { TimelineChart } from "./sections/TimelineChart";
import { Summary } from "./sections/Summary";
import { CustomerBehavior } from "./sections/CustomerBehavior";
import { RackRanking } from "./sections/RackRanking";
import { TopItems } from "./sections/TopItems";

export type DashboardMode = "ready" | "running" | "playback";

interface ReadyProps {
  mode: "ready";
  pid: string;
  sid: string;
  setup: SetupDetailWithBlocked;
  itemCount: number;
  onBusyChange?: (busy: boolean) => void;
  onSimulate?: () => void;
  simulating?: boolean;
  simulateError?: Error | null;
  availability?: Availability;
}

interface RunningProps {
  mode: "running";
  status?: RunStatus;
}

interface PlaybackProps {
  mode: "playback";
  customers: CustomerResult[] | null;
  minTime: number;
  maxTime: number;
  store: Store;
  summary?: RunSummary | null;
  projectId?: string;
  runId?: string;
}

export type DashboardPanelProps = ReadyProps | RunningProps | PlaybackProps;

export function DashboardPanel(props: DashboardPanelProps) {
  if (props.mode === "playback") {
    return <PlaybackContent {...props} />;
  }
  if (props.mode === "running") {
    return <RunningContent status={props.status} />;
  }
  return <ReadyContent {...props} />;
}

function PlaybackContent({ customers, minTime, maxTime, store, summary, projectId, runId }: PlaybackProps) {
  return (
    <div className="flex flex-col">
      <PlaybackStatus minTime={minTime} maxTime={maxTime} />
      <TimelineChart customers={customers} minTime={minTime} maxTime={maxTime} />
      <Summary />
      <CustomerBehavior />
      {summary && <RunKpis summary={summary} />}
      {projectId && runId && <RunAnalystSection key={`analyst:${projectId}:${runId}`} projectId={projectId} runId={runId} />}
      <RackRanking store={store} />
      <TopItems store={store} />
      {projectId && runId && <VisionGlancesSection projectId={projectId} runId={runId} />}
      {projectId && runId && <DiagnosticsSection projectId={projectId} runId={runId} />}
      {projectId && runId && <FidelitySection projectId={projectId} runId={runId} />}
      {projectId && runId && <MovementSection key={`${projectId}:${runId}`} projectId={projectId} runId={runId} />}
    </div>
  );
}

function RunningContent({ status }: { status?: RunStatus }) {
  // Ticks once a second so elapsed / remaining time stay live between status polls.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return <RunProgress status={status} now={now} />;
}

function ReadyContent({
  pid,
  sid,
  setup,
  itemCount,
  onBusyChange,
  onSimulate,
  simulating,
  simulateError,
  availability,
}: ReadyProps) {
  const { t } = useI18n();
  const hasFloor = setup.store != null;
  const blocked = availability !== undefined && !availability.canSimulate;

  return (
    <div className="flex flex-col gap-4 px-0 pt-3 pb-6">
      {/* Step 1: FloorConfigurationPanel renders its own "Step 1" header. */}
      <section className="flex flex-col gap-2">
        <FloorConfigurationPanel
          pid={pid}
          sid={sid}
          setup={setup}
          itemCount={itemCount}
          onBusyChange={onBusyChange}
        />
      </section>

      {/* Step 2 shows a locked placeholder until the floor exists. */}
      {!hasFloor && (
        <section className="flex items-center justify-between gap-2 rounded-lg border bg-muted/40 p-4 text-sm">
          <h3 className="text-sm font-medium text-muted-foreground">
            Step 2: Item placement
          </h3>
          <Lock aria-hidden className="size-4 text-muted-foreground" />
        </section>
      )}

      {hasFloor && setup.store && (
        <section className="flex flex-col gap-2 rounded-lg border bg-card p-4 text-sm">
          <h3 className="text-sm font-medium">Step 2: Item placement</h3>
          <StarterFill key={`starter:${pid}:${sid}`} pid={pid} sid={sid} />
          <RackCopy key={`copy:${pid}:${sid}`} pid={pid} sid={sid} />
          <LibraryPhotos key={`photos:${pid}:${sid}`} pid={pid} sid={sid} />
          <ProductBulkEditor key={`${pid}:${sid}`} pid={pid} sid={sid} />
          <LayoutExcelControls
            store={setup.store}
            projectId={pid}
            setupId={sid}
          />
          <div className="mt-2 flex flex-col gap-1.5">
            <Button
              size="lg"
              disabled={simulating || blocked || !onSimulate}
              onClick={onSimulate}
            >
              {simulating ? t("runningSimulation") : `${t("runSimulation")}…`}
            </Button>
            <p className="text-xs text-muted-foreground">
              Choose an instant rule-based preview or LLM shoppers, a customer sample and a seed.
            </p>
            {blocked && availability && availability.reasons.length > 0 && (
              <ul className="flex flex-col gap-1">
                {availability.reasons.map((r) => {
                  const Icon = reasonIcon(r);
                  return (
                    <li
                      key={r}
                      className="flex items-start gap-2 rounded-md border bg-muted/40 px-2 py-1.5 text-xs"
                    >
                      <Icon
                        aria-hidden
                        className="mt-0.5 size-3 shrink-0 text-muted-foreground"
                      />
                      <span>{reasonLabel(r)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
            {simulateError && (
              <p className="text-xs text-destructive">
                {simulateError instanceof Error
                  ? simulateError.message
                  : "Simulation run failed"}
              </p>
            )}
                    </div>
        </section>
      )}

      {hasFloor && <PreviewRunsList projectId={pid} setupId={sid} />}
    </div>
  );
}
