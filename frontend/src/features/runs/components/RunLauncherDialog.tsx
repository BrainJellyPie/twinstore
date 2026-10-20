// Run configuration dialog: engine, customer sample, seed, preview vs final.
//
// - Rule-based runs finish in seconds and cost nothing — ideal while iterating on a layout.
// - LLM runs are realistic but cost ~3 calls per customer; a sample keeps pilots cheap.
// - Vision runs ask a (local, CPU) vision-language model about 1–3 rendered shelves per
//   customer; seconds per call, so they default to a small sample.
// - The same seed on two layouts makes them see the same customers in the same moods,
//   which is what makes the A/B compare view statistically sharp.

import { useState, type FormEvent } from "react";
import { Bot, Eye, FlaskConical, Map as MapIcon, Zap } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/shared/components/ui/radio-group";
import { useSimulate } from "@/shared/mutations/useSimulate";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import type { EngineType, RunOptions, Scenario } from "@/shared/api/client";
import { cn } from "@/shared/utils/cn";

import { useEngines } from "../hooks";
import { ModelPicker, type ModelChoice } from "./ModelPicker";
import { ScenarioEditor } from "./ScenarioEditor";

export interface RunLauncherDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  setupId: string;
  personaCount: number;
  // Finalized layouts only accept preview runs.
  locked?: boolean;
  defaultEngine?: EngineType;
}

export function RunLauncherDialog(props: RunLauncherDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-[520px]">
        {/* Content unmounts when closed, so the form state resets on every open. */}
        <LauncherForm {...props} />
      </DialogContent>
    </Dialog>
  );
}

const SAMPLE_DEFAULT = 300;
const VISION_SAMPLE_DEFAULT = 30;

function LauncherForm({
  onOpenChange,
  projectId,
  setupId,
  personaCount,
  locked = false,
  defaultEngine,
}: RunLauncherDialogProps) {
  const simulate = useSimulate();
  const engines = useEngines().data;
  const serverDefault = engines?.find((e) => e.default)?.engine_type;
  const [engine, setEngine] = useState<EngineType>(defaultEngine ?? serverDefault ?? "rule_based");
  const [sampleMode, setSampleMode] = useState<"all" | "sample">(
    personaCount > SAMPLE_DEFAULT && (defaultEngine ?? serverDefault) !== "rule_based" ? "sample" : "all",
  );
  const [sampleSize, setSampleSize] = useState(Math.min(SAMPLE_DEFAULT, personaCount));
  const [seed, setSeed] = useState(0);
  const [replicate, setReplicate] = useState(0);
  const [preview, setPreview] = useState(true);
  const [modelChoice, setModelChoice] = useState<ModelChoice>({ kind: "default" });
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const town = useQuery({ queryKey: queryKeys.town(projectId), queryFn: ({ signal }) => api.getTown(projectId, signal) }).data;
  const [useTown, setUseTown] = useState(false);
  const [townScale, setTownScale] = useState(0.2);
  const [planPolicy, setPlanPolicy] = useState<"vlm" | "rule">("vlm");

  const isPreview = locked || preview;
  const customers = sampleMode === "all" ? personaCount : Math.max(1, Math.min(sampleSize, personaCount));
  const usesLlm = engines?.find((e) => e.engine_type === engine)?.uses_llm ?? engine !== "rule_based";
  const modelOf = (type: EngineType) => engines?.find((e) => e.engine_type === type)?.model;

  const chooseEngine = (next: EngineType) => {
    setEngine(next);
    if (next === "vlm_glance" && personaCount > VISION_SAMPLE_DEFAULT) {
      setSampleMode("sample");
      setSampleSize(VISION_SAMPLE_DEFAULT);
    }
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const options: RunOptions = {
      engine_type: engine,
      seed,
      replicate,
      preview: isPreview,
      max_customers: sampleMode === "sample" ? customers : undefined,
      model: modelChoice.kind === "single" ? modelChoice.model : undefined,
      ensemble:
        modelChoice.kind === "ensemble" && (modelChoice.ensemble?.members.length ?? 0) > 0 ? modelChoice.ensemble : undefined,
      scenario: scenario ?? undefined,
      use_town: town && useTown ? true : undefined,
      town_scale: town && useTown ? townScale : undefined,
      plan_policy: engine === "vlm_glance" ? planPolicy : undefined,
    };
    simulate.mutate({ projectId, setupId, options }, { onSuccess: () => onOpenChange(false) });
  };

  const engineCards: { value: EngineType; title: string; body: string; icon: typeof Bot; wide?: boolean }[] = [
    {
      value: "rule_based",
      title: "Rule-based preview",
      body: "Seconds per run, no API cost. Great for iterating on a layout.",
      icon: Zap,
    },
    {
      value: "pattern_intent_impulse",
      title: "LLM shoppers",
      body: modelOf("pattern_intent_impulse")
        ? `Realistic decisions via ${modelOf("pattern_intent_impulse")}.`
        : "Realistic decisions; consumes LLM API calls.",
      icon: Bot,
    },
    {
      value: "vlm_glance",
      title: "Vision shoppers",
      body: `A vision-language model looks at each shelf the shopper passes and picks what catches the eye${
        modelOf("vlm_glance") ? ` (${modelOf("vlm_glance")})` : ""
      }. Runs on a local model — keep the sample small.`,
      icon: Eye,
      wide: true,
    },
  ];

  return (
    <form onSubmit={submit} className="space-y-5">
      <DialogHeader>
        <DialogTitle>Run simulation</DialogTitle>
        <DialogDescription>
          {locked
            ? "This layout is finalized — new runs are saved as previews alongside the final run."
            : "Choose how shoppers are simulated. Previews keep the layout editable."}
        </DialogDescription>
      </DialogHeader>

      <RadioGroup
        value={engine}
        onValueChange={(v: string) => chooseEngine(v as EngineType)}
        className="grid grid-cols-2 gap-2"
        aria-label="Simulation engine"
      >
        {engineCards.map(({ value, title, body, icon: Icon, wide }) => (
          <label
            key={value}
            htmlFor={`engine-${value}`}
            className={cn(
              "flex cursor-pointer flex-col gap-1.5 rounded-lg border p-3 text-xs transition-colors",
              wide && "col-span-2",
              engine === value ? "border-primary bg-primary/5" : "hover:bg-muted/50",
            )}
          >
            <span className="flex items-center gap-2 text-sm font-medium">
              <RadioGroupItem id={`engine-${value}`} value={value} />
              <Icon className="size-4" aria-hidden />
              {title}
            </span>
            <span className="text-muted-foreground">{body}</span>
          </label>
        ))}
      </RadioGroup>

      <ScenarioEditor value={scenario} onChange={setScenario} />

      {town && (
        <div className="space-y-1.5 rounded-md border p-3 text-xs">
          <label className="flex items-center gap-2 text-sm font-medium" htmlFor="use-town">
            <input id="use-town" type="checkbox" className="size-4 accent-primary" checked={useTown} onChange={(e) => setUseTown(e.target.checked)} />
            <MapIcon className="size-4" aria-hidden /> Visitors from the neighborhood
          </label>
          <p className="text-muted-foreground">
            Who comes, when and from how far is predicted from {town.name}: homes, offices, schools, rival stores and
            linked trips from nearby venues. Shoppers know where they came from.
          </p>
          {useTown && (
            <label className="flex items-center gap-2">
              <span className="text-muted-foreground">Simulate</span>
              <input type="range" min={0.05} max={1} step={0.05} value={townScale} onChange={(e) => setTownScale(Number(e.target.value))} className="flex-1 accent-primary" />
              <span className="w-28 text-right tabular-nums">{Math.round(townScale * 100)} % of a full week</span>
            </label>
          )}
        </div>
      )}

      {engine === "vlm_glance" && (
        <div className="space-y-1.5 rounded-md border p-3 text-xs">
          <div className="text-sm font-medium">What the vision shoppers decide</div>
          <div className="grid grid-cols-2 gap-2">
            {([
              { id: "vlm", title: "Everything", hint: "At the door each shopper sees the store map, today's situation and where they came from, and decides whether to go in and what to buy; then picks impulse items off the shelves." },
              { id: "rule", title: "Shelf glances only", hint: "Shopping lists come from the rule model (faster); the VLM only judges impulse picks at the shelves." },
            ] as const).map((o) => (
              <button key={o.id} type="button" onClick={() => setPlanPolicy(o.id)}
                className={cn("rounded-lg border p-2 text-left", planPolicy === o.id ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
                <div className="font-medium">{o.title}</div>
                <div className="text-muted-foreground">{o.hint}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {usesLlm && (
        <ModelPicker
          engine={engine}
          defaultModel={modelOf(engine)}
          value={modelChoice}
          onChange={setModelChoice}
        />
      )}

      <div className="space-y-2">
        <div className="text-sm font-medium">Customers</div>
        <RadioGroup
          value={sampleMode}
          onValueChange={(v: string) => setSampleMode(v as "all" | "sample")}
          className="gap-2"
          aria-label="Customer sample"
        >
          <label className="flex items-center gap-2 text-sm" htmlFor="sample-all">
            <RadioGroupItem id="sample-all" value="all" />
            All {personaCount.toLocaleString()} personas
          </label>
          <label className="flex items-center gap-2 text-sm" htmlFor="sample-some">
            <RadioGroupItem id="sample-some" value="sample" />
            Sample of
            <Input
              type="number"
              min={1}
              max={personaCount}
              value={sampleSize}
              disabled={sampleMode !== "sample"}
              onChange={(e) => setSampleSize(Number(e.target.value) || 1)}
              className="h-7 w-24"
              aria-label="Sample size"
            />
            personas
          </label>
        </RadioGroup>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="run-seed">Seed</label>
          <Input id="run-seed" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)} />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="run-replicate">Replicate</label>
          <Input id="run-replicate" type="number" min={0} value={replicate} onChange={(e) => setReplicate(Math.max(0, Number(e.target.value) || 0))} />
        </div>
        <p className="col-span-2 flex gap-1.5 text-xs text-muted-foreground">
          <FlaskConical className="mt-0.5 size-3 shrink-0" aria-hidden />
          Use the same seed on two layouts for a paired A/B comparison; change the replicate to measure run-to-run noise.
        </p>
      </div>

      <label className="flex items-start gap-2 text-sm" htmlFor="run-preview">
        <input
          id="run-preview"
          type="checkbox"
          className="mt-0.5 size-4 accent-primary"
          checked={isPreview}
          disabled={locked}
          onChange={(e) => setPreview(e.target.checked)}
        />
        <span>
          Preview run
          <span className="block text-xs text-muted-foreground">
            Keeps the layout editable. Uncheck to finalize the layout with this run.
          </span>
        </span>
      </label>

      <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs">
        {engine === "vlm_glance" ? (
          <>
            ≈ <span className="font-medium tabular-nums">{customers.toLocaleString()}–{(customers * 3).toLocaleString()}</span>{" "}
            vision-model calls for {customers.toLocaleString()} customers (1–3 shelf glances each). On a CPU-only
            server each glance takes several seconds.
          </>
        ) : usesLlm ? (
          <>
            ≈ <span className="font-medium tabular-nums">{(customers * 3).toLocaleString()}</span> LLM calls
            for {customers.toLocaleString()} customers (3 per customer). Identical prompts are served from the
            response cache when it is enabled on the server.
          </>
        ) : (
          <>Instant — {customers.toLocaleString()} customers, no API cost.</>
        )}
      </div>

      {simulate.isError && (
        <p className="text-xs text-destructive">
          {simulate.error instanceof Error ? simulate.error.message : "Failed to start the run."}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={simulate.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={simulate.isPending || personaCount === 0}>
          {simulate.isPending ? "Starting…" : isPreview ? "Run preview" : "Run & finalize"}
        </Button>
      </DialogFooter>
    </form>
  );
}
