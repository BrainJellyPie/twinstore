// Run configuration dialog: engine, customer sample, seed, preview vs final.
//
// - Rule-based runs finish in seconds and cost nothing — ideal while iterating on a layout.
// - LLM runs are realistic but cost ~3 calls per customer; a sample keeps pilots cheap.
// - Vision runs ask a (local, CPU) vision-language model about 1–3 rendered shelves per
//   customer; seconds per call, so they default to a small sample.
// - The same seed on two layouts makes them see the same customers in the same moods,
//   which is what makes the A/B compare view statistically sharp.

import { useState, type FormEvent } from "react";
import { Bot, ChevronDown, Eye, FlaskConical, Map as MapIcon, SlidersHorizontal, Zap } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { useI18n } from "@/shared/i18n/i18n";
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
  const { t } = useI18n();
  const simulate = useSimulate();
  const engines = useEngines().data;
  const serverDefault = engines?.find((e) => e.default)?.engine_type;
  const [selectedEngine, setEngine] = useState<EngineType>();
  const engine = selectedEngine ?? defaultEngine ?? serverDefault ?? "rule_based";
  const recommendedSample = Math.min(engine === "vlm_glance" ? VISION_SAMPLE_DEFAULT : SAMPLE_DEFAULT, personaCount);
  const [selectedSampleMode, setSampleMode] = useState<"all" | "sample" | null>(null);
  const sampleMode = selectedSampleMode ?? (engine !== "rule_based" && personaCount > recommendedSample ? "sample" : "all");
  const [selectedSampleSize, setSampleSize] = useState<string | null>(null);
  const sampleSize = selectedSampleSize ?? String(recommendedSample);
  const [seed, setSeed] = useState("0");
  const [replicate, setReplicate] = useState("0");
  const [preview, setPreview] = useState(true);
  const [modelChoice, setModelChoice] = useState<ModelChoice>({ kind: "default" });
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const town = useQuery({ queryKey: queryKeys.town(projectId), queryFn: ({ signal }) => api.getTown(projectId, signal) }).data;
  const [useTown, setUseTown] = useState(false);
  const [townScale, setTownScale] = useState(0.2);
  const [planPolicy, setPlanPolicy] = useState<"vlm" | "rule">("vlm");

  const isPreview = locked || preview;
  const validSample = sampleMode === "all" || (sampleSize.trim() !== "" && Number.isSafeInteger(Number(sampleSize)) && Number(sampleSize) >= 1 && Number(sampleSize) <= personaCount);
  const validSeed = seed.trim() !== "" && Number.isSafeInteger(Number(seed));
  const validReplicate = replicate.trim() !== "" && Number.isSafeInteger(Number(replicate)) && Number(replicate) >= 0;
  const valid = personaCount > 0 && validSample && validSeed && validReplicate;
  const customers = sampleMode === "all" ? personaCount : validSample ? Number(sampleSize) : 0;
  const usesLlm = engines?.find((e) => e.engine_type === engine)?.uses_llm ?? engine !== "rule_based";
  const modelOf = (type: EngineType) => engines?.find((e) => e.engine_type === type)?.model;

  const chooseEngine = (next: EngineType) => {
    setEngine(next);
    if (next !== engine) {
      setSampleMode(null);
      setSampleSize(null);
      setModelChoice({ kind: "default" });
    }
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!valid || simulate.isPending) return;
    const options: RunOptions = {
      engine_type: engine,
      seed: Number(seed),
      replicate: Number(replicate),
      preview: isPreview,
      max_customers: sampleMode === "sample" ? customers : undefined,
      model: usesLlm && modelChoice.kind === "single" ? modelChoice.model : undefined,
      ensemble:
        usesLlm && modelChoice.kind === "ensemble" && (modelChoice.ensemble?.members.length ?? 0) > 0 ? modelChoice.ensemble : undefined,
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
      title: t("rulePreview"),
      body: t("ruleEngineHint"),
      icon: Zap,
    },
    {
      value: "pattern_intent_impulse",
      title: t("llmShoppers"),
      body: modelOf("pattern_intent_impulse")
        ? t("llmEngineModel", { model: modelOf("pattern_intent_impulse")! })
        : t("llmEngineHint"),
      icon: Bot,
    },
    {
      value: "vlm_glance",
      title: t("visionShoppers"),
      body: `${t("visionEngineHint")}${modelOf("vlm_glance") ? ` (${modelOf("vlm_glance")})` : ""}`,
      icon: Eye,
      wide: true,
    },
  ];

  return (
    <form onSubmit={submit}
      onInvalidCapture={(event) => {
        const details = (event.target as HTMLElement).closest("details");
        if (details) details.open = true;
      }} className="min-w-0 space-y-5">
      <DialogHeader>
        <DialogTitle>{t("runSimulation")}</DialogTitle>
        <DialogDescription>
          {locked
            ? t("lockedRunHint")
            : t("runHint")}
        </DialogDescription>
      </DialogHeader>

      <fieldset disabled={simulate.isPending} className="min-w-0 space-y-5">
        <RadioGroup
          value={engine}
          onValueChange={(v: string) => chooseEngine(v as EngineType)}
          className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2"
          aria-label={t("simulationEngine")}
        >
          {engineCards.map(({ value, title, body, icon: Icon, wide }) => (
            <label
              key={value}
              htmlFor={`engine-${value}`}
              className={cn(
                "flex cursor-pointer flex-col gap-1.5 rounded-lg border p-3 text-xs transition-colors",
                wide && "min-[400px]:col-span-2",
                engine === value ? "border-primary bg-primary/5" : "hover:bg-muted/50",
              )}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <RadioGroupItem id={`engine-${value}`} value={value} />
                <Icon className="size-4" aria-hidden />
                {title}
              </span>
              <span className="min-w-0 break-words text-muted-foreground">{body}</span>
            </label>
          ))}
        </RadioGroup>

        <div className="space-y-2">
          <div className="text-sm font-medium">{t("customers")}</div>
          <RadioGroup
            value={sampleMode}
            onValueChange={(v: string) => setSampleMode(v as "all" | "sample")}
            className="gap-2"
            aria-label={t("customerSample")}
          >
            <label className="flex items-center gap-2 text-sm" htmlFor="sample-all">
              <RadioGroupItem id="sample-all" value="all" />
              {t("allPersonas", { count: personaCount })}
            </label>
            <label className="grid grid-cols-[auto_auto_minmax(0,6rem)_auto] items-center justify-start gap-2 text-sm" htmlFor="sample-some">
              <RadioGroupItem id="sample-some" value="sample" />
              <span className="whitespace-nowrap">{t("sampleOf")}</span>
              <Input
                type="number"
                min={1}
                max={personaCount}
                value={sampleSize}
                disabled={sampleMode !== "sample"}
                onChange={(e) => setSampleSize(e.target.value)}
                aria-invalid={!validSample}
                aria-describedby={!validSample ? "run-input-error" : undefined}
                className="h-7 min-w-0 w-full"
                aria-label={t("sampleSize")}
              />
              <span className="hidden min-[400px]:inline">{t("personasUnit")}</span>
            </label>
          </RadioGroup>
        </div>

        <details className="group rounded-xl border">
          <summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl p-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">
            <SlidersHorizontal className="size-4 shrink-0" aria-hidden />
            {t("advancedSettings")}
            <ChevronDown className="ml-auto size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <div className="space-y-5 border-t p-3">
            <ScenarioEditor value={scenario} onChange={setScenario} />

            {town && (
              <div className="space-y-1.5 rounded-md border p-3 text-xs">
                <label className="flex items-center gap-2 text-sm font-medium" htmlFor="use-town">
                  <input id="use-town" type="checkbox" className="size-4 accent-primary" checked={useTown} onChange={(e) => setUseTown(e.target.checked)} />
                  <MapIcon className="size-4" aria-hidden /> {t("townVisitors")}
                </label>
                <p className="text-muted-foreground">
                  {t("townVisitorsHint", { name: town.name })}
                </p>
                {useTown && (
                  <label className="flex items-center gap-2">
                    <span className="text-muted-foreground">{t("simulate")}</span>
                    <input type="range" min={0.05} max={1} step={0.05} value={townScale} onChange={(e) => setTownScale(Number(e.target.value))} className="flex-1 accent-primary" />
                    <span className="w-28 text-right tabular-nums">{t("predictedShare", { percent: Math.round(townScale * 100) })}</span>
                  </label>
                )}
              </div>
            )}

            {engine === "vlm_glance" && (
              <div className="space-y-1.5 rounded-md border p-3 text-xs">
                <div className="text-sm font-medium">{t("visionDecisions")}</div>
                <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
                  {([
                    { id: "vlm", title: t("decideEverything"), hint: t("decideEverythingHint") },
                    { id: "rule", title: t("shelfGlancesOnly"), hint: t("shelfGlancesHint") },
                  ] as const).map((o) => (
                    <button key={o.id} type="button" onClick={() => setPlanPolicy(o.id)}
                      aria-pressed={planPolicy === o.id}
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

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium" htmlFor="run-seed">{t("seed")}</label>
                <Input id="run-seed" type="number" value={seed} onChange={(e) => setSeed(e.target.value)} aria-invalid={!validSeed} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium" htmlFor="run-replicate">{t("replicate")}</label>
                <Input id="run-replicate" type="number" min={0} value={replicate} onChange={(e) => setReplicate(e.target.value)} aria-invalid={!validReplicate} />
              </div>
              <p className="col-span-2 flex gap-1.5 text-xs text-muted-foreground">
                <FlaskConical className="mt-0.5 size-3 shrink-0" aria-hidden />
                {t("pairedRunHint")}
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
                {t("previewRun")}
                <span className="block text-xs text-muted-foreground">
                  {t("previewRunHint")}
                </span>
              </span>
            </label>

          </div>
        </details>

        <p className="text-xs text-muted-foreground" aria-live="polite">
          {isPreview ? t("previewSummary") : t("finalSummary")}
          {" · "}{scenario?.name ?? t("baselineSituation")}
          {usesLlm && ` · ${modelChoice.kind === "single" ? modelChoice.model ?? t("serverDefaultModel") : modelChoice.kind === "ensemble" ? t("modelEnsemble") : modelOf(engine) || t("serverDefaultModel")}`}
          {town && useTown && ` · ${t("neighborSummary", { percent: Math.round(townScale * 100) })}`}
        </p>

        <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs">
          {engine === "vlm_glance"
            ? t("visionCallEstimate", { min: customers, max: customers * 3, count: customers })
            : usesLlm ? t("llmCallEstimate", { calls: customers * 3, count: customers }) : t("ruleCallEstimate", { count: customers })}
        </div>

      </fieldset>

      {(!validSample || !validSeed || !validReplicate) && (
        <p id="run-input-error" role="alert" className="text-xs text-destructive">
          {!validSample ? t("sampleError", { max: personaCount }) : !validSeed ? t("seedError") : t("replicateError")}
        </p>
      )}

      {simulate.isError && (
        <p role="alert" className="text-xs text-destructive">
          {simulate.error instanceof Error ? simulate.error.message : t("runStartError")}
        </p>
      )}

      {personaCount === 0 && <p role="status" className="text-xs text-muted-foreground">{t("addPersonasHint")}</p>}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={simulate.isPending}>
          {t("cancel")}
        </Button>
        <Button type="submit" disabled={simulate.isPending || !valid}>
          {simulate.isPending ? t("starting") : isPreview ? t("runPreview") : t("runFinalize")}
        </Button>
      </DialogFooter>
    </form>
  );
}
