// Shown where a step needs a model and none is set up: the user picks one here (a key, or the local model's download)
// instead of the app downloading gigabytes nobody asked for.

import { Link } from "@tanstack/react-router";
import { Cpu, KeyRound, Loader2 } from "lucide-react";

import type { ModelSetup } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { isPreparing, useLocalModelControl, useModelSetup } from "./useModelSetup";

const COMING: Partial<Record<ModelSetup["local"]["state"], MessageKey>> = {
  preparing: "localStatePreparing", downloading: "localStateDownloading", starting: "localStateStarting",
};

/** `settings`: also link to the model settings (off where the screen already has that button). */
export function NeedsModel({ settings = true }: { settings?: boolean }) {
  const { t } = useI18n();
  const { data } = useModelSetup();
  const { start } = useLocalModelControl();
  if (!data || data.cloud_providers.length > 0 || data.local.state === "ready") return null;
  const busy = isPreparing(data);
  const progress = busy && data.local.progress !== null ? ` ${Math.round(data.local.progress * 100)}%` : "";
  return (
    <div role="status" className="space-y-2 rounded-lg border p-3 text-sm" data-testid="needs-model">
      <p>{t("needsModelHint")}</p>
      {busy ? (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden /> {t(COMING[data.local.state] ?? "localStatePreparing")}{progress}
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {data.local.state !== "disabled" && (
            <Button size="sm" variant="outline" onClick={() => start.mutate()} disabled={start.isPending}>
              <Cpu className="size-3.5" aria-hidden /> {data.local.downloaded === false
                ? t("downloadLocal", { size: data.plan.model.download_gb }) : t("startLocal")}
            </Button>
          )}
          {settings && <Button size="sm" variant="outline" asChild>
            <Link to="/settings"><KeyRound className="size-3.5" aria-hidden /> {t("modelSettings")}</Link>
          </Button>}
        </div>
      )}
      {start.isError && <p role="alert" className="break-words text-xs text-destructive">
        {start.error instanceof Error ? start.error.message : t("startLocalError")}</p>}
    </div>
  );
}
