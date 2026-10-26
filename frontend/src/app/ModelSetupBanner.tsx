// Optional model setup stays compact so the store remains usable on small screens.

import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronDown, Cpu, KeyRound, Loader2, Sparkles, Square, TriangleAlert, X } from "lucide-react";

import { useI18n } from "@/shared/i18n/i18n";
import { BACKEND_LABEL, isPreparing, useLocalModelControl, useModelSetup } from "@/features/settings/useModelSetup";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { formatDecimal } from "@/shared/utils/money";

const DISMISS_KEY = "twinstore.modelBanner.dismissed";

function readDismissed(): string | null {
  try {
    return sessionStorage.getItem(DISMISS_KEY);
  } catch {
    return null;
  }
}

export function ModelSetupBanner() {
  const { t } = useI18n();
  const { data } = useModelSetup();
  const { start, stop } = useLocalModelControl();
  const [dismissed, setDismissed] = useState<string | null>(readDismissed);

  if (!data?.warning) return null;
  const state = data.local.state;
  // Surface changed states even if a previous notice was dismissed.
  if (dismissed === state) return null;
  const busy = isPreparing(data);
  const ready = state === "ready";
  const failed = state === "error";
  const progress = data.local.progress !== null && Number.isFinite(data.local.progress)
    ? Math.round(Math.max(0, Math.min(1, data.local.progress)) * 100) : null;

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
      <div className={cn("glass relative mx-auto flex max-w-6xl items-start gap-3 rounded-2xl px-3 py-2.5 text-sm", failed && "border-l-2 border-l-warn")}>
        <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-foreground/[0.06]" aria-hidden>
          {busy ? <Loader2 className="size-4 animate-spin" /> : ready ? <Cpu className="size-4" /> : failed ? <TriangleAlert className="size-4" /> : <Sparkles className="size-4" />}
        </span>
        {/* One line on a wide screen (title, hint, setup link), so the notice costs little of every page. */}
        <div className="min-w-0 flex-1 md:flex md:flex-wrap md:items-baseline md:gap-x-3 md:pt-1">
          <p className="font-medium leading-snug">
            {busy ? t("preparingVision") : ready ? t("localReady") : failed ? t("modelAttention") : t("exploreFree")}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground md:mt-0 md:min-w-0 md:flex-1">
            {ready ? t("localReadyHint") : busy ? t("preparingHint") : t("freePreviewHint")}
          </p>
          {busy && (
            <div className="mt-1.5 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground md:order-last md:basis-full">
              <div role="progressbar" aria-label={t("modelDownload")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress ?? undefined}
                className="h-1.5 w-32 max-w-full overflow-hidden rounded-full bg-foreground/10">
                <div className={cn("h-full rounded-full bg-primary transition-[width] duration-500", progress === null && "w-1/3 animate-pulse")}
                  style={progress !== null ? { width: `${progress}%` } : undefined} />
              </div>
              <span className="num min-w-0 break-words">
                {progress !== null && data.local.total_mb > 0
                  ? `${formatDecimal(data.local.downloaded_mb, 0)} / ${formatDecimal(data.local.total_mb, 0)} MB`
                  : data.local.message}
              </span>
            </div>
          )}
          <details className="group mt-1.5 md:mt-0 md:open:basis-full">
            <summary className="flex w-fit cursor-pointer list-none items-center gap-1 rounded-sm text-xs font-medium text-primary focus-visible:outline-2 focus-visible:outline-ring">
              {busy || ready ? t("modelDetails") : t("setupVision")}
              <ChevronDown className="size-3 transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <div className="mt-2 space-y-2 border-t border-glass-border pt-2">
              {/* Said here in the reader's language from the setup's state; the server's own warning is English. */}
              <p className="break-words text-xs leading-relaxed text-muted-foreground">{(() => {
                if (state === "disabled") return t("setupWarnDisabled");
                const model = t("localModelOn", { model: data.plan.model.label, backend: BACKEND_LABEL[data.plan.backend] });
                return ready ? t("setupWarnReady", { model }) : busy ? t("setupWarnBusy", { model })
                  : data.local.downloaded === false ? t("setupWarnOffDownload", { model, size: data.plan.model.download_gb })
                    : t("setupWarnOff", { model });
              })()}</p>
              <div className="flex flex-wrap items-center gap-2">
                {(state === "off" || failed) && (
                  <Button size="sm" variant="outline" className="h-auto min-h-8 max-w-full py-1.5 whitespace-normal" onClick={() => start.mutate()} disabled={start.isPending}>
                    <Cpu className="size-3.5" aria-hidden /> {start.isPending ? t("starting") : failed ? t("retryLocal")
                      : data.local.downloaded === false ? t("downloadLocal", { size: data.plan.model.download_gb }) : t("startLocal")}
                  </Button>
                )}
                {busy && (
                  <Button size="sm" variant="outline" onClick={() => stop.mutate()} disabled={stop.isPending}>
                    <Square className="size-3.5" aria-hidden /> {stop.isPending ? t("stoppingLocal") : t("stopLocal")}
                  </Button>
                )}
                <Button size="sm" variant="outline" asChild>
                  <Link to="/settings"><KeyRound className="size-3.5" aria-hidden /> {t("modelSettings")}</Link>
                </Button>
              </div>
              {start.isError && <p role="alert" className="break-words text-xs text-destructive">{start.error instanceof Error ? start.error.message : t("startLocalError")}</p>}
              {stop.isError && <p role="alert" className="break-words text-xs text-destructive">{stop.error instanceof Error && stop.error.message ? stop.error.message : t("stopLocalError")}</p>}
            </div>
          </details>
        </div>
        <button type="button" onClick={dismiss} className="grid size-8 shrink-0 place-items-center rounded-lg text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring" aria-label={t("hideNotice")}>
          <X className="size-4" aria-hidden />
        </button>
      </div>
    </div>
  );
}
