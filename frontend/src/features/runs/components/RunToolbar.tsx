// Floating toolbar over the 3D view in playback: switch between runs of this layout,
// start another run, compare runs, export results, return to editing.

import { useState } from "react";
import { Download, GitCompareArrows, Pencil, Play, Wand2 } from "lucide-react";

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
import { useSimulationStore } from "@/stores/simulationStore";

import { runLabel } from "../labels";
import { CompareDialog } from "./CompareDialog";
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
  const runs = useRuns(projectId, setupId).data
    .filter((r) => r.status === "completed")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const setViewRunId = useSimulationStore((s) => s.setViewRunId);
  const lastRunError = useSimulationStore((s) => s.lastRunError);
  const [launchOpen, setLaunchOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [optimizeOpen, setOptimizeOpen] = useState(false);
  const editable = setupStatus === "draft";

  return (
    <div className="pointer-events-auto absolute bottom-4 left-3 z-10 flex max-w-[calc(100%-1.5rem)] flex-col gap-2">
      {lastRunError && (
        <p className="glass rounded-xl border border-destructive/40 px-3 py-1.5 text-sm text-destructive shadow-float">
          Last run failed: {lastRunError.split("\n")[0]}
        </p>
      )}
      <div className="glass flex flex-wrap items-center gap-1 rounded-2xl border p-1.5 shadow-float">
        <Select value={runId} onValueChange={setViewRunId}>
          <SelectTrigger className="h-9 w-[270px] rounded-xl text-sm" aria-label="Run shown">
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
          <Play className="size-4" /> Run again
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
      <OptimizeDialog open={optimizeOpen} onOpenChange={setOptimizeOpen} projectId={projectId} setupId={setupId} />
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
