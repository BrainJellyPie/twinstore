// Toolbar below the 3D view in playback: switch between runs of this layout,
// start another run, compare runs, export results, return to editing.

import { useEffect, useState } from "react";
import { Download, GitCompareArrows, Pencil, Play, Wand2 } from "lucide-react";

import { useI18n } from "@/shared/i18n/i18n";
import { Button } from "@/shared/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { runExportUrl } from "@/shared/api/client";
import { useRuns } from "@/shared/queries/useRuns";
import type { Layout } from "@/features/layouts/hooks/useLayouts";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";

import { runLabel } from "../labels";
import { CompareDialog } from "./CompareDialog";
import { LastRunFailure } from "./LastRunFailure";
import { OptimizeDialog } from "./OptimizeDialog";
import { RunLauncherDialog } from "./RunLauncherDialog";

export interface RunToolbarProps {
  projectId: string;
  setupId: string;
  runId: string;
  setupStatus: string;
  personaCount: number;
  layouts: Layout[];
}

export function RunToolbar({ projectId, setupId, runId, setupStatus, personaCount, layouts }: RunToolbarProps) {
  const { t } = useI18n();
  const runs = useRuns(projectId, setupId).data
    .filter((r) => r.status === "completed")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const setViewRunId = useSimulationStore((s) => s.setViewRunId);
  const [launchOpen, setLaunchOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [optimizeOpen, setOptimizeOpen] = useState(false);
  // A goal typed in the command palette opens the optimizer with it.
  const [goalPrefill, setGoalPrefill] = useState<{ id: number; text: string } | undefined>(undefined);
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  useEffect(() => {
    if (!pendingAsk) return;
    const routed = takeAsk(projectId, ["optimize"]);
    if (!routed) return;
    setGoalPrefill({ id: routed.id, text: routed.text });
    setOptimizeOpen(true);
  }, [pendingAsk, projectId, takeAsk]);
  const editable = setupStatus === "draft";

  return (
    <div className="relative z-10 flex min-w-0 shrink-0 flex-col gap-2" role="region" aria-label="Run actions">
      <LastRunFailure projectId={projectId} setupId={setupId}
        className="glass rounded-xl border border-destructive/40 px-3 py-1.5 text-sm text-destructive shadow-float" />
      <div className="glass flex flex-wrap items-center gap-1 rounded-2xl border p-1.5 shadow-float">
        <Select value={runId} onValueChange={setViewRunId}>
          {/* Sized to the label ("Rule-based · seed 0 · preview · 05:12 PM"), cut only when the bar is narrower. */}
          <SelectTrigger className="h-9 w-auto min-w-[min(270px,100%)] max-w-full rounded-xl text-sm" aria-label="Run shown">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {runs.map((r) => (
              <SelectItem key={r.run_id} value={r.run_id} className="text-sm">
                {runLabel(r)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" variant="ghost" className="h-9 gap-1.5 rounded-xl px-3 text-sm" onClick={() => setLaunchOpen(true)}>
          <Play className="size-4" /> {t("runAgain")}
        </Button>
        <Button size="sm" variant="ghost" className="h-9 gap-1.5 rounded-xl px-3 text-sm" onClick={() => setCompareOpen(true)}>
          <GitCompareArrows className="size-4" /> Compare
        </Button>
        <Button size="sm" variant="ghost" className="h-9 gap-1.5 rounded-xl px-3 text-sm" onClick={() => setOptimizeOpen(true)}>
          <Wand2 className="size-4" /> Optimize
        </Button>
        <Button size="sm" variant="ghost" className="h-9 gap-1.5 rounded-xl px-3 text-sm" asChild>
          <a href={runExportUrl(projectId, runId)} download>
            <Download className="size-4" /> CSV
          </a>
        </Button>
        {editable && (
          <Button size="sm" variant="ghost" className="h-9 gap-1.5 rounded-xl px-3 text-sm" onClick={() => setViewRunId(null)}>
            <Pencil className="size-4" /> Edit layout
          </Button>
        )}
      </div>
      <RunLauncherDialog
        open={launchOpen}
        onOpenChange={setLaunchOpen}
        projectId={projectId}
        setupId={setupId}
        personaCount={personaCount}
        locked={!editable}
      />
      <OptimizeDialog open={optimizeOpen} projectId={projectId} setupId={setupId} goalPrefill={goalPrefill}
        onOpenChange={(o) => { setOptimizeOpen(o); if (!o) setGoalPrefill(undefined); }} />
      <CompareDialog
        open={compareOpen}
        onOpenChange={setCompareOpen}
        projectId={projectId}
        layouts={layouts}
        defaultRunId={runId}
      />
    </div>
  );
}
