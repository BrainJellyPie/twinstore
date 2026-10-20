// Floating toolbar over the 3D view in playback: switch between runs of this layout,
// start another run, compare runs, export results, return to editing.

import { useState } from "react";
import { Download, GitCompareArrows, Pencil, Play } from "lucide-react";

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
  const editable = setupStatus === "draft";

  return (
    <div className="pointer-events-auto absolute bottom-4 left-3 z-10 flex max-w-[calc(100%-420px)] flex-col gap-2">
      {lastRunError && (
        <p className="rounded-md border border-destructive/40 bg-background/95 px-2 py-1 text-xs text-destructive shadow-sm">
          Last run failed: {lastRunError.split("\n")[0]}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border bg-background/95 p-1.5 shadow-md">
        <Select value={runId} onValueChange={setViewRunId}>
          <SelectTrigger className="h-8 w-[260px] text-xs" aria-label="Run shown">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {runs.map((r) => (
              <SelectItem key={r.run_id} value={r.run_id} className="text-xs">
                {runLabel(r)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" className="h-8 gap-1 text-xs" onClick={() => setLaunchOpen(true)}>
          <Play className="size-3" /> Run again
        </Button>
        <Button size="sm" variant="outline" className="h-8 gap-1 text-xs" onClick={() => setCompareOpen(true)}>
          <GitCompareArrows className="size-3" /> Compare
        </Button>
        <Button size="sm" variant="outline" className="h-8 gap-1 text-xs" asChild>
          <a href={runExportUrl(projectId, runId)} download>
            <Download className="size-3" /> CSV
          </a>
        </Button>
        {editable && (
          <Button size="sm" variant="ghost" className="h-8 gap-1 text-xs" onClick={() => setViewRunId(null)}>
            <Pencil className="size-3" /> Edit layout
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
