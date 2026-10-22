import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";
import { Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { useProject } from "@/shared/queries/useProject";
import { useSetup } from "@/shared/queries/useSetup";
import { useRuns } from "@/shared/queries/useRuns";
import { useSetupGeneration } from "@/shared/queries/useSetupGeneration";
import { deleteProject } from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { PreparingView } from "@/views/simulation/states/PreparingView";
import { ReadyView } from "@/views/simulation/states/ReadyView";
import { RunningView } from "@/views/simulation/states/RunningView";
import { PlaybackView } from "@/views/simulation/states/PlaybackView";
import { EmptyFloorReadyView } from "@/views/simulation/states/EmptyFloorReadyView";
import { useLayouts, type Layout } from "@/features/layouts/hooks/useLayouts";
import { useSwitchLayout } from "@/features/layouts/hooks/useSwitchLayout";
import { AddLayoutDialog } from "@/features/layouts/components/AddLayoutDialog";
import type { ProjectDetail, SetupDetail } from "@/shared/api/client";
import type { Store } from "@/shared/types/domain";

export const Route = createFileRoute("/projects/$pid")({
  component: SimulationPage,
});

function SimulationPage() {
  const { pid } = Route.useParams();
  return <SimulationPageInner key={pid} pid={pid} />;
}

function SimulationPageInner({ pid }: { pid: string }) {
  const router = useRouter();
  const { t } = useI18n();
  const content = useRef<HTMLDivElement>(null);
  const navigationFocus = useRef<{ element: HTMLElement; source: "tab" | "finder" } | null>(null);
  const project = useProject(pid).data;
  const layoutsQuery = useLayouts(pid);
  const layouts = layoutsQuery.data;
  const selectedSetupId = useSimulationStore((s) => s.selectedSetupId);
  const switchLayout = useSwitchLayout();
  const layoutMounted = useCallback((id: string) => {
    const previous = navigationFocus.current;
    if (!previous || previous.element.isConnected) return;
    navigationFocus.current = null;
    if (document.activeElement !== document.body || router.state.location.pathname.replace(/\/$/, "") !== `/projects/${pid}`) return;
    const target = previous.source === "tab"
      ? Array.from(content.current?.querySelectorAll<HTMLButtonElement>("[data-layout-id]") ?? []).find(tab => tab.dataset.layoutId === id)
      : content.current?.querySelector<HTMLButtonElement>("[data-layout-finder-trigger]");
    target?.focus();
  }, [pid, router]);
  const isCurrentProject = useCallback(() => router.state.location.pathname.replace(/\/$/, "") === `/projects/${pid}`, [pid, router]);
  const effectiveSetupId = layouts?.some((layout) => layout.id === selectedSetupId)
    ? selectedSetupId
    : layouts?.[0]?.id;

  useEffect(() => {
    if (effectiveSetupId && selectedSetupId !== effectiveSetupId) {
      switchLayout(effectiveSetupId);
    }
  }, [selectedSetupId, effectiveSetupId, switchLayout]);

  useEffect(() => {
    return () => {
      usePlaybackControlStore.getState().reset();
      useSimulationMetricsStore.getState().reset();
      useSimulationStore.getState().reset();
    };
  }, []);

  const [addLayoutOpen, setAddLayoutOpen] = useState(false);
  const reloadLayouts = <Button type="button" variant="outline" size="sm" disabled={layoutsQuery.isFetching}
    onClick={() => { void layoutsQuery.refetch(); }}>{t("reloadLayouts")}</Button>;
  const layoutError = layoutsQuery.isError ? <div role="alert"
    className="max-h-48 w-full min-w-0 shrink-0 space-y-2 overflow-y-auto rounded-xl border border-destructive/30 p-4 text-sm [overflow-wrap:anywhere]">
    <p className="font-medium">{t("layoutsLoadFailed")}</p>
    {layoutsQuery.error instanceof Error && <p className="whitespace-pre-wrap text-muted-foreground">{layoutsQuery.error.message}</p>}
    {reloadLayouts}
  </div> : null;

  if (!layouts) {
    return (
      <div role={layoutsQuery.isError ? undefined : "status"} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto p-4 text-sm">
        <div className="my-auto w-full min-w-0 shrink-0">{layoutError ?? <p className="text-center">{t("loadingLayouts")}</p>}</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto">
      {layoutError}
      {/*
        Local Suspense — on layout switch, if useSetup(useSuspenseQuery)'s cache miss
        bubbles up to the root Suspense, SimulationPageInner itself unmounts and the
        cleanup useEffect (below) calls simulationStore.reset(), which nulls
        selectedSetupId. On remount, the initial useEffect restores it to layouts[0],
        producing a regression where "selection snaps back to layout 1". A local
        Suspense boundary scopes the remount to SimulationPageContent and preserves
        inner state. fallback=null works with startTransition so the previous content
        stays visible until the transition completes.
      */}
      {effectiveSetupId ? <div ref={content} className="contents"
        onFocusCapture={(event) => {
          const target = event.target;
          const source = target.hasAttribute("data-layout-id") ? "tab"
            : target.hasAttribute("data-layout-finder-result") || target.hasAttribute("data-layout-finder-trigger") ? "finder" : null;
          navigationFocus.current = source ? { element: target, source } : null;
        }}
        onBlurCapture={(event) => {
          const next = event.relatedTarget;
          // Suspense hides the old view before replacement, which also blurs its focused tab.
          if (!next && typeof event.target.checkVisibility === "function" && !event.target.checkVisibility()) return;
          if (!(next instanceof HTMLElement) || !next.matches("[data-layout-id],[data-layout-finder-result],[data-layout-finder-trigger]")) navigationFocus.current = null;
        }}><Suspense fallback={null}>
        <SimulationPageContent
          key={effectiveSetupId}
          pid={pid}
          project={project}
          effectiveSetupId={effectiveSetupId}
          layouts={layouts}
          onLayoutSelect={switchLayout}
          onLayoutMounted={layoutMounted}
          onAddLayout={() => setAddLayoutOpen(true)}
        />
      </Suspense></div> : <div className="flex min-h-40 min-w-0 flex-1 items-center justify-center p-4">
        <div className="max-w-lg space-y-3 text-center [overflow-wrap:anywhere]">
          <h2 className="font-medium">{t("noLayoutsFound")}</h2>
          <p className="text-sm text-muted-foreground">{t("noLayoutsHint")}</p>
          <div className="flex flex-wrap justify-center gap-2">
            {!layoutsQuery.isError && reloadLayouts}
            <Button type="button" size="sm" onClick={() => setAddLayoutOpen(true)}>{t("newLayout")}</Button>
          </div>
        </div>
      </div>}
      <AddLayoutDialog
        open={addLayoutOpen}
        onOpenChange={setAddLayoutOpen}
        projectId={pid}
        parentSetupId={effectiveSetupId ?? ""}
        layouts={layouts}
        defaultCurrency={project.metadata.currency ?? "USD"}
        isCurrentProject={isCurrentProject}
      />
    </div>
  );
}

interface SimulationPageContentProps {
  pid: string;
  project: ProjectDetail;
  effectiveSetupId: string;
  layouts: Layout[];
  onLayoutSelect: (id: string) => void;
  onLayoutMounted: (id: string) => void;
  onAddLayout: () => void;
}

function SimulationPageContent({
  pid,
  project,
  effectiveSetupId,
  layouts,
  onLayoutSelect,
  onLayoutMounted,
  onAddLayout,
}: SimulationPageContentProps) {
  const setup = useSetup(pid, effectiveSetupId).data;
  const runs = useRuns(pid, effectiveSetupId).data;
  const navigate = useNavigate();
  const router = useRouter();
  const qc = useQueryClient();
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const generation = useSetupGeneration(pid, effectiveSetupId);
  useLayoutEffect(() => { onLayoutMounted(effectiveSetupId); }, [effectiveSetupId, onLayoutMounted]);

  const location = project.metadata.address;

  // Run shown in playback: the user's pick, else the latest finalized (non-preview) run.
  // Preview runs never take over the view on their own, so a draft layout stays editable.
  const viewRunId = useSimulationStore((s) => s.viewRunId);
  const completedRuns = [...runs]
    .filter((r) => r.status === "completed")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const viewedRun =
    (viewRunId ? completedRuns.find((r) => r.run_id === viewRunId) : undefined) ??
    completedRuns.find((r) => !r.preview);
  const runningRun = runs.find((r) => r.status === "running" || r.status === "pending");

  const tabProps = {
    layouts,
    selectedSetupId: effectiveSetupId,
    onLayoutSelect,
    onAddLayout,
  };

  const reasons = setup.readiness?.reasons ?? [];

  const layoutPending =
    generation.phase === "layout" || reasons.includes("layout_pending");
  const personaPending =
    generation.phase === "persona" || reasons.includes("personas_pending");
  const personaMissing = reasons.includes("no_personas");
  const isFailedLayoutCtx =
    generation.phase === "failed" && generation.kind === "layout";
  const isFailedPersonaCtx =
    generation.phase === "failed" && generation.kind === "persona";
  const isPreparing =
    layoutPending ||
    personaPending ||
    isFailedPersonaCtx ||
    isFailedLayoutCtx ||
    personaMissing;

  const contextKind: "layout" | "persona" =
    layoutPending || isFailedLayoutCtx ? "layout" : "persona";

  // Mode resolver — priority order (spec §7):
  //   1) any layout/persona signal → PreparingView
  //   2) (all above false) store==null → EmptyFloorReadyView (post-wizard + persona ready)
  //   3) store!=null → existing RunningView/PlaybackView/ReadyView flow
  // PreparingView renders outside SimulationLayout — SimulationLayout's store asset
  // hook blows up on a null store, so it can't be reused.
  if (isPreparing) {
    return (
      <PreparingView
        generation={generation}
        contextKind={contextKind}
        projectName={project.metadata.name}
        layouts={layouts}
        selectedSetupId={effectiveSetupId}
        onLayoutSelect={onLayoutSelect}
        onBackToStores={() => { void navigate({ to: "/" }); }}
        onAbandonProject={async () => {
          await deleteProject(pid);
          // Leave before touching the cache: refetching the deleted store's queries 404s and would
          // unmount this page before the new-store form opens.
          if (mounted.current && router.state.location.pathname.replace(/\/$/, "") === `/projects/${pid}`) {
            await navigate({ to: "/projects/new" });
          }
          qc.removeQueries({ queryKey: queryKeys.project(pid) });
          await qc.invalidateQueries({ queryKey: queryKeys.projects(), exact: true });
        }}
      />
    );
  }

  const hasFloor = setup.store != null;

  if (!hasFloor) {
    return (
      <EmptyFloorReadyView
        pid={pid}
        setupId={effectiveSetupId}
        setup={setup}
        personas={project.personas}
        location={location}
        {...tabProps}
      />
    );
  }
  const setupWithStore: SetupDetail & { store: Store } = {
    ...setup,
    store: { ...setup.store!, currency: setup.store!.currency ?? project.metadata.currency },
  };

  if (runningRun) {
    return (
      <RunningView
        pid={pid}
        setupId={effectiveSetupId}
        runId={runningRun.run_id}
        setup={setupWithStore}
        personas={project.personas}
        location={location}
        {...tabProps}
      />
    );
  }
  if (viewedRun) {
    return (
      <PlaybackView
        pid={pid}
        runId={viewedRun.run_id}
        location={location}
        setupStatus={setup.status}
        personaCount={project.personas.length}
        {...tabProps}
      />
    );
  }
  return (
    <ReadyView
      pid={pid}
      setupId={effectiveSetupId}
      setup={setupWithStore}
      personas={project.personas}
      location={location}
      {...tabProps}
    />
  );
}
