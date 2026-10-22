// This computer and the vision model it runs without any API key: what was detected, which model
// was chosen and why, and the state of its download and server.

import { Cpu, HardDrive, Loader2, MemoryStick, Play, Square } from "lucide-react";

import type { ModelSetup } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";

import { isPreparing, useLocalModelControl, useModelSetup } from "./useModelSetup";

const BACKEND_LABEL: Record<ModelSetup["plan"]["backend"], string> = {
  cuda: "NVIDIA GPU (CUDA)",
  metal: "Apple GPU (Metal)",
  vulkan: "GPU (Vulkan)",
  cpu: "CPU",
};

const STATE_LABEL: Record<ModelSetup["local"]["state"], string> = {
  off: "Not running",
  disabled: "Turned off (TWINSTORE_LOCAL_VLM)",
  preparing: "Checking this computer",
  downloading: "Downloading",
  starting: "Loading the model",
  ready: "Running",
  error: "Could not start",
};

export function LocalModelPanel() {
  const { data, isLoading } = useModelSetup();
  const { start, stop } = useLocalModelControl();
  if (isLoading || !data) return null;

  const { hardware: hw, plan, local } = data;
  const gpu = hw.gpus.length ? hw.gpus.map((g) => `${g.name}${g.vram_gb ? ` · ${g.vram_gb} GB` : ""}`).join(", ") : "none found";
  const busy = isPreparing(data);

  return (
    <section className="glass rounded-2xl p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Cpu className="size-4" aria-hidden /> Local vision model {data.cloud_providers.length ? "(fallback)" : "(in use: no API key)"}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Without a key, shoppers run on a small open model on this computer, chosen for its hardware. It is free and
            private but slower and less accurate than a cloud model; the published validation uses cloud models.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Stop also cancels a download or start in progress. */}
          {busy || (local.state === "ready" && local.managed) ? (
            <Button size="sm" variant="outline" onClick={() => stop.mutate()} disabled={stop.isPending}>
              <Square className="size-3.5" aria-hidden /> Stop
            </Button>
          ) : (
            <Button size="sm" onClick={() => start.mutate()} disabled={start.isPending || local.state === "disabled" || local.state === "ready"}>
              <Play className="size-3.5" aria-hidden /> Start {plan.model.label}
            </Button>
          )}
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <Fact icon={Cpu} label="Processor" value={`${hw.cpu || "CPU"} · ${hw.cores} cores`} />
        <Fact icon={MemoryStick} label="Memory" value={`${hw.ram_gb} GB (${hw.ram_free_gb} GB free)`} />
        <Fact icon={HardDrive} label="Graphics" value={gpu} />
      </dl>

      <div className="mt-4 rounded-xl bg-foreground/[0.04] p-3 text-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="font-medium">
            {plan.model.label} on {BACKEND_LABEL[plan.backend]}
          </span>
          <span className="num text-xs text-muted-foreground">
            {plan.model.download_gb} GB download · ~{plan.model.memory_gb} GB memory · {plan.parallel} shopper{plan.parallel > 1 ? "s" : ""} at a time
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
          {STATE_LABEL[local.state]}
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
        {local.state === "ready" && <span className="text-xs text-muted-foreground">Pick “{local.model_ref}” in a run.</span>}
      </div>
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
