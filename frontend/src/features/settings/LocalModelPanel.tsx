// This computer and the vision model it runs without any API key: what was detected, which model
// was chosen and why, and the state of its download and server.

import { Cpu, HardDrive, Loader2, MemoryStick, Play, Square } from "lucide-react";

import type { ModelSetup } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { richText } from "@/shared/i18n/richText";

import { isPreparing, useLocalModelControl, useModelSetup } from "./useModelSetup";

const BACKEND_LABEL: Record<ModelSetup["plan"]["backend"], string> = {
  cuda: "NVIDIA GPU (CUDA)",
  metal: "Apple GPU (Metal)",
  vulkan: "GPU (Vulkan)",
  cpu: "CPU",
};

const STATE_LABEL: Record<ModelSetup["local"]["state"], MessageKey> = {
  off: "localStateOff",
  disabled: "localStateDisabled",
  preparing: "localStatePreparing",
  downloading: "localStateDownloading",
  starting: "localStateStarting",
  ready: "localStateReady",
  error: "localStateError",
};

export function LocalModelPanel() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch, isFetching } = useModelSetup();
  const { start, stop } = useLocalModelControl();
  if (!data && error) {
    return (
      <section role="alert" className="glass flex flex-wrap items-center justify-between gap-3 rounded-2xl p-5 text-sm">
        <span className="min-w-0 break-words">
          <span className="font-medium">{t("localCheckFailed")}</span>{" "}
          <span className="text-muted-foreground">{error.message}</span>
        </span>
        <Button size="sm" variant="outline" disabled={isFetching} onClick={() => void refetch()}>
          {isFetching && <Loader2 className="size-3.5 animate-spin" aria-hidden />} {t("localRetry")}
        </Button>
      </section>
    );
  }
  if (isLoading || !data) return null;

  const { hardware: hw, plan, local } = data;
  const gpu = hw.gpus.length ? hw.gpus.map((g) => `${g.name}${g.vram_gb ? ` · ${g.vram_gb} GB` : ""}`).join(", ") : t("localNoGpu");
  const busy = isPreparing(data);
  const turnedOff = local.state === "disabled";
  const role = t(turnedOff ? "localRoleOff" : data.cloud_providers.length ? "localRoleFallback" : "localRoleInUse");

  return (
    <section className="glass rounded-2xl p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Cpu className="size-4" aria-hidden /> {t("localTitle")} {role}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("localDescription")}
          </p>
          {turnedOff && (
            <p className="mt-2 text-sm" data-testid="local-model-turned-off">
              {richText(t("localTurnedOffHint"), {
                setting: <code className="font-mono text-xs">TWINSTORE_LOCAL_VLM</code>,
                file: <code className="font-mono text-xs">.env</code>,
                value: <code className="font-mono text-xs">on</code>,
              })}
            </p>
          )}
        </div>
        {!turnedOff && (
          <div className="flex items-center gap-2">
            {/* Stop also cancels a download or start in progress. */}
            {busy || (local.state === "ready" && local.managed) ? (
              <Button size="sm" variant="outline" onClick={() => stop.mutate()} disabled={stop.isPending}>
                <Square className="size-3.5" aria-hidden /> {t("localStop")}
              </Button>
            ) : (
              <Button size="sm" className="h-auto min-h-8 max-w-full py-1.5 whitespace-normal" onClick={() => start.mutate()} disabled={start.isPending || local.state === "ready"}>
                <Play className="size-3.5" aria-hidden /> {local.downloaded === false
                  ? t("localDownloadStart", { model: plan.model.label, size: plan.model.download_gb })
                  : t("localStart", { model: plan.model.label })}
              </Button>
            )}
          </div>
        )}
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <Fact icon={Cpu} label={t("localProcessor")} value={t("localCores", { cpu: hw.cpu || "CPU", cores: hw.cores })} />
        <Fact icon={MemoryStick} label={t("localMemory")} value={t("localRam", { total: hw.ram_gb, free: hw.ram_free_gb })} />
        <Fact icon={HardDrive} label={t("localGraphics")} value={gpu} />
      </dl>

      <div className="mt-4 rounded-xl bg-foreground/[0.04] p-3 text-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="font-medium">
            {t("localModelOn", { model: plan.model.label, backend: BACKEND_LABEL[plan.backend] })}
          </span>
          <span className="num text-xs text-muted-foreground">
            {t(plan.parallel > 1 ? "localPlanMany" : "localPlanOne", { download: plan.model.download_gb, memory: plan.model.memory_gb, parallel: plan.parallel })}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{plan.reason}.</p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        <span
          className={cn(
            "inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium",
            local.state === "ready" ? "bg-positive/15 text-positive" : local.state === "error" ? "bg-negative/15 text-negative" : "bg-foreground/[0.06] text-muted-foreground",
          )}
        >
          {busy && <Loader2 className="size-3 animate-spin" aria-hidden />}
          {t(STATE_LABEL[local.state])}
        </span>
        {local.message && <span className="text-xs text-muted-foreground">{local.message}</span>}
        {busy && local.progress !== null && (
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-40 overflow-hidden rounded-full bg-foreground/10" aria-hidden>
              <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${Math.round(local.progress * 100)}%` }} />
            </div>
            <span className="num text-xs text-muted-foreground">{Math.round(local.progress * 100)}%</span>
          </div>
        )}
        {local.state === "ready" && <span className="text-xs text-muted-foreground">{t("localPickInRun", { model: local.model_ref })}</span>}
      </div>
      {start.error && <p role="alert" className="mt-2 break-words text-xs text-destructive">{t("localStartFailed", { message: start.error.message })}</p>}
      {stop.error && <p role="alert" className="mt-2 break-words text-xs text-destructive">{t("localStopFailed", { message: stop.error.message })}</p>}
    </section>
  );
}

function Fact({ icon: Icon, label, value }: { icon: typeof Cpu; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0">
        <dt className="text-xs text-muted-foreground">{label}</dt>
        <dd className="truncate" title={value}>
          {value}
        </dd>
      </div>
    </div>
  );
}
