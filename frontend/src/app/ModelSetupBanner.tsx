// Shown under the command bar while no API key is set: which local model stands in for the cloud
// models, how far its download is, and the way to add a key.

import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Cpu, KeyRound, Loader2, TriangleAlert, X } from "lucide-react";

import { isPreparing, useLocalModelControl, useModelSetup } from "@/features/settings/useModelSetup";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";

const DISMISS_KEY = "twinstore.modelBanner.dismissed";

function readDismissed(): string | null {
  try {
    return sessionStorage.getItem(DISMISS_KEY);
  } catch {
    return null;
  }
}

export function ModelSetupBanner() {
  const { data } = useModelSetup();
  const { start } = useLocalModelControl();
  const [dismissed, setDismissed] = useState<string | null>(readDismissed);

  if (!data?.warning) return null;
  const state = data.local.state;
  // A dismissed banner comes back when the situation changes (e.g. the download finished or failed).
  if (dismissed === state) return null;
  const busy = isPreparing(data);
  const ready = state === "ready";
  const progress = data.local.progress;

  const dismiss = () => {
    setDismissed(state);
    try {
      sessionStorage.setItem(DISMISS_KEY, state);
    } catch {
      /* private mode: dismiss for this page only */
    }
  };

  return (
    <div role="status" className="relative z-20 px-4 pt-2">
      <div
        className={cn(
          "glass relative mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl px-4 py-2.5 text-sm",
          ready ? "border-l-2 border-l-primary" : "border-l-2 border-l-warn",
        )}
      >
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-foreground/[0.06]" aria-hidden>
          {busy ? <Loader2 className="size-4 animate-spin" /> : ready ? <Cpu className="size-4" /> : <TriangleAlert className="size-4" />}
        </span>
        <div className="min-w-0 flex-1 pr-5 sm:pr-0">
          <p className="leading-snug">{data.warning}</p>
          {busy && (
            <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
              <div className="h-1.5 w-48 overflow-hidden rounded-full bg-foreground/10" aria-hidden>
                <div
                  className={cn("h-full rounded-full bg-primary transition-[width] duration-500", progress === null && "w-1/3 animate-pulse")}
                  style={progress !== null ? { width: `${Math.round(progress * 100)}%` } : undefined}
                />
              </div>
              <span className="num">
                {progress !== null && data.local.total_mb > 0
                  ? `${data.local.downloaded_mb.toFixed(0)} / ${data.local.total_mb.toFixed(0)} MB`
                  : data.local.message}
              </span>
            </div>
          )}
        </div>
        <div className="flex w-full min-w-0 shrink-0 flex-wrap items-center gap-2 sm:w-auto sm:flex-nowrap">
          {(state === "off" || state === "error") && (
            <Button size="sm" variant="outline" onClick={() => start.mutate()} disabled={start.isPending}>
              <Cpu className="size-3.5" aria-hidden /> Start local model
            </Button>
          )}
          <Button size="sm" asChild>
            <Link to="/settings">
              <KeyRound className="size-3.5" aria-hidden /> Add an API key
            </Link>
          </Button>
          <button
            type="button"
            onClick={dismiss}
            className="absolute top-2 right-2 grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground sm:static"
            aria-label="Hide this notice"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
