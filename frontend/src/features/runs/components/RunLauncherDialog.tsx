// Run configuration dialog: engine, customer sample, seed, preview vs final.
//
// - Rule-based runs finish in seconds and cost nothing — ideal while iterating on a layout.
// - LLM runs are realistic but cost ~3 calls per customer; a sample keeps pilots cheap.
// - Vision runs ask a (local, CPU) vision-language model about 1–3 rendered shelves per
//   customer; seconds per call, so they default to a small sample.
// - The same seed on two layouts makes them see the same customers in the same moods,
//   which is what makes the A/B compare view statistically sharp.
// - The server estimates each choice (shoppers over how many days, time, cost); a long or costly run asks once more
//   before it starts.

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, Camera, ChevronDown, Eye, FlaskConical, Map as MapIcon, SlidersHorizontal, Zap } from "lucide-react";
import { keepPreviousData, queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";

import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { isPreparing, useModelSetup } from "@/features/settings/useModelSetup";
import { Button } from "@/shared/components/ui/button";
import { RequestError } from "@/shared/components/RequestError";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
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
import { SharedStoreControls } from "./SharedStoreControls";
import { choiceFromConfig, DEFAULT_SHARED_STORE, sharedStoreOptions, type SharedStoreChoice } from "../sharedStore";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { queryKeys } from "@/shared/queries/keys";
import type { EngineType, OperationsConfig, RunEstimate, RunOptions, Scenario, ShelfViewMode } from "@/shared/api/client";
import { cn } from "@/shared/utils/cn";
import { costText, durationText, runEstimateText, shoppersOverDaysText } from "@/shared/utils/estimate";

import { useAvailableModels, useEngines, useLayoutOperations } from "../hooks";
import { photographShelves } from "../shelfPhotos";
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

// LLM shoppers cost about 3 model calls each; this sample stays under the cost warning on typical models.
const SAMPLE_DEFAULT = 150;
const VISION_SAMPLE_DEFAULT = 30;
const ESTIMATE_DEBOUNCE_MS = 400;
const ESTIMATE_STALE_MS = 30_000;
// Starting waits this long for an estimate it does not have yet; without one the run starts unwarned.
const ESTIMATE_WAIT_MS = 10_000;

function LauncherForm({
  onOpenChange,
  projectId,
  setupId,
  personaCount,
  locked = false,
  defaultEngine,
}: RunLauncherDialogProps) {
  const { locale, t } = useI18n();
  const qc = useQueryClient();
  const simulate = useSimulate();
  const engines = useEngines().data;
  const modelSetup = useModelSetup().data;
  const serverDefault = engines?.find((e) => e.default)?.engine_type;
  // An engine whose model is not ready (no key, or the local model not answering) and has no keyed alternative cannot
  // run, so the dialog opens on the rule-based preview instead.
  const canRun = (type: EngineType) => {
    const info = engines?.find((e) => e.engine_type === type);
    return !info?.uses_llm || info.model_ready !== false || !!info.suggested_model;
  };
  const preferredEngine = defaultEngine ?? serverDefault;
  const [selectedEngine, setEngine] = useState<EngineType>();
  const engine = selectedEngine ?? (preferredEngine && canRun(preferredEngine) ? preferredEngine : "rule_based");
  const recommendedSample = Math.min(engine === "vlm_glance" ? VISION_SAMPLE_DEFAULT : SAMPLE_DEFAULT, personaCount);
  const [selectedSampleMode, setSampleMode] = useState<"all" | "sample" | null>(null);
  const sampleMode = selectedSampleMode ?? (engine !== "rule_based" && personaCount > recommendedSample ? "sample" : "all");
  const [selectedSampleSize, setSampleSize] = useState<string | null>(null);
  const sampleSize = selectedSampleSize ?? String(recommendedSample);
  const [seed, setSeed] = useState("0");
  const [replicate, setReplicate] = useState("0");
  const [preview, setPreview] = useState(true);
  const [pickedModel, setPickedModel] = useState<ModelChoice>({ kind: "default" });
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const town = useQuery({ queryKey: queryKeys.town(projectId), queryFn: ({ signal }) => api.getTown(projectId, signal) }).data;
  const [useTown, setUseTown] = useState(false);
  const [townScale, setTownScale] = useState(0.2);
  const [planPolicy, setPlanPolicy] = useState<"vlm" | "rule">("vlm");
  const [shelfView, setShelfView] = useState<ShelfViewMode>("chart");
  // The layout's saved operations are the starting point; settings without a field here (hourly tills, per-product
  // stock) come along unchanged.
  // A run waits for them: starting before they load would quietly run the default store instead.
  const layoutOperationsQuery = useLayoutOperations(projectId, setupId);
  const layoutOperations = layoutOperationsQuery.data;
  const [pickedStore, setSharedStore] = useState<SharedStoreChoice | null>(null);
  const sharedStore = pickedStore ?? (layoutOperations ? choiceFromConfig(layoutOperations) : DEFAULT_SHARED_STORE);
  const fields = sharedStoreOptions(sharedStore);
  // Clearing the crew here also drops the layout's crew hour by hour (it only applies with a crew).
  const operations: OperationsConfig | undefined | "invalid" = fields === "invalid" || fields === undefined
    ? fields : { ...(layoutOperations ?? {}), ...fields, ...(fields.crew == null ? { crew_schedule: {} } : {}) };
  const [photos, setPhotos] = useState<{ done: number; total: number } | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const photographing = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  // Closing the dialog stops photographing and estimating; nothing is started.
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; photographing.current?.abort(); };
  }, []);
  const [checking, setChecking] = useState(false);
  const [warning, setWarning] = useState<{ options: RunOptions; estimate: RunEstimate } | null>(null);
  const preparing = photos !== null;
  const withPhotos = engine === "vlm_glance" && shelfView === "photo_chart";

  const isPreview = locked || preview;
  const validSample = sampleMode === "all" || (sampleSize.trim() !== "" && Number.isSafeInteger(Number(sampleSize)) && Number(sampleSize) >= 1 && Number(sampleSize) <= personaCount);
  const validSeed = seed.trim() !== "" && Number.isSafeInteger(Number(seed));
  const validReplicate = replicate.trim() !== "" && Number.isSafeInteger(Number(replicate)) && Number(replicate) >= 0;
  const customers = sampleMode === "all" ? personaCount : validSample ? Number(sampleSize) : 0;
  const usesLlm = engines?.find((e) => e.engine_type === engine)?.uses_llm ?? engine !== "rule_based";
  const modelOf = (type: EngineType) => engines?.find((e) => e.engine_type === type)?.model;
  const models = useAvailableModels(usesLlm);
  const available = models.data?.filter((model) => engine !== "vlm_glance" || model.vision);
  // The server default has no API key: start from a model that has one (the user can still pick another).
  const engineInfo = engines?.find((e) => e.engine_type === engine);
  const noKey = usesLlm && engineInfo?.model_ready === false;
  const suggested = noKey && engineInfo?.suggested_model && available?.some((m) => m.ref === engineInfo.suggested_model)
    ? engineInfo.suggested_model : null;
  const modelChoice: ModelChoice = pickedModel.kind === "default" && suggested ? { kind: "single", model: suggested } : pickedModel;
  const setModelChoice = setPickedModel;
  const localState = modelSetup?.local.state;
  const notReadyMessage: MessageKey = localState === "disabled" ? "modelNotReadyLocalOff"
    : isPreparing(modelSetup) ? "modelNotReadyLocalPreparing"
    : localState === "off" || localState === "error" ? "modelNotReadyLocalStopped" : "modelNotReadyNoKey";
  let modelError: string | null = null;
  if (usesLlm && noKey && modelChoice.kind === "default" && available) modelError = t(notReadyMessage, { model: engineInfo?.model ?? "" });
  if (usesLlm && modelChoice.kind !== "default") {
    if (!available) modelError = models.isError ? t("modelListError") : t("loadingModels");
    else if (modelChoice.kind === "single") {
      modelError = !modelChoice.model ? t("needOneModel")
        : available.some((model) => model.ref === modelChoice.model) ? null : t("unavailableModel", { model: modelChoice.model });
    } else {
      const members = modelChoice.ensemble?.members ?? [];
      if (!members.length) modelError = t("needEnsemble");
      else if (members.some((member) => !available.some((model) => model.ref === member.model))) modelError = t("unavailableEnsemble");
      else if (members.some((member) => !Number.isFinite(member.weight) || member.weight <= 0)) modelError = t("invalidWeights");
    }
  }
  const valid = layoutOperationsQuery.isSuccess && personaCount > 0 && validSample && validSeed && validReplicate
    && modelError === null && operations !== "invalid";

  const chooseEngine = (next: EngineType) => {
    setEngine(next);
    if (next !== engine) {
      setSampleMode(null);
      setSampleSize(null);
      setModelChoice({ kind: "default" });
    }
  };

  const buildOptions = (): RunOptions => ({
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
    shelf_view: engine === "vlm_glance" ? shelfView : undefined,
    operations: operations === "invalid" ? undefined : operations,
    // Off means off, even on a layout with saved operations.
    shared_store: sharedStore.enabled ? undefined : false,
  });

  // The estimate follows the choices after a short pause; starting a run reuses it (or asks for it).
  const estimateQuery = (options: RunOptions) => queryOptions({
    queryKey: queryKeys.runEstimate(projectId, setupId, options),
    queryFn: ({ signal }) => api.estimateRun(projectId, setupId, options, signal),
    staleTime: ESTIMATE_STALE_MS,
    retry: false,
  });
  const optionsKey = JSON.stringify(valid ? buildOptions() : null);
  const [estimateKey, setEstimateKey] = useState(optionsKey);
  useEffect(() => {
    const timer = setTimeout(() => setEstimateKey(optionsKey), ESTIMATE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [optionsKey]);
  const estimateOptions = JSON.parse(estimateKey) as RunOptions | null;
  const estimate = useQuery({ ...estimateQuery(estimateOptions ?? {}), enabled: estimateOptions !== null, placeholderData: keepPreviousData });
  const shownEstimate = valid ? estimate.data : undefined;
  const estimateCurrent = estimateKey === optionsKey && !estimate.isPlaceholderData;
  // 400/404: nothing to estimate yet (e.g. no customers) — no line rather than a guess.
  const noEstimate = estimate.error instanceof ApiError && (estimate.error.status === 400 || estimate.error.status === 404);

  const fetchEstimate = async (options: RunOptions): Promise<RunEstimate | null> => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([
        qc.fetchQuery(estimateQuery(options)),
        new Promise<null>((done) => { timer = setTimeout(() => done(null), ESTIMATE_WAIT_MS); }),
      ]);
    } catch {
      return null; // An estimate that cannot be read never blocks the run.
    } finally {
      clearTimeout(timer);
    }
  };

  const start = async (options: RunOptions) => {
    if (withPhotos) {
      const controller = new AbortController();
      photographing.current = controller;
      setPhotoError(null);
      setPhotos({ done: 0, total: 0 });
      try {
        await photographShelves(projectId, setupId, (done, total) => setPhotos({ done, total }), controller.signal);
      } catch (error) {
        if (!controller.signal.aborted) {
          setPhotoError(error instanceof Error ? error.message : String(error));
          setPhotos(null);
        }
        return;
      }
      if (controller.signal.aborted) return;
      setPhotos(null);
    }
    simulate.mutate({ projectId, setupId, options }, { onSuccess: () => onOpenChange(false) });
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!valid || simulate.isPending || preparing || checking || warning) return;
    const options = buildOptions();
    let latest = qc.getQueryData(estimateQuery(options).queryKey) ?? null;
    if (!latest) {
      setChecking(true);
      latest = await fetchEstimate(options);
      setChecking(false);
      if (!mounted.current) return;
    }
    if (latest?.warn) {
      setWarning({ options, estimate: latest });
      return;
    }
    await start(options);
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
    <>
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

      <fieldset disabled={simulate.isPending || preparing || checking} className="min-w-0 space-y-5">
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

        <fieldset disabled={!layoutOperationsQuery.isSuccess}>
          <SharedStoreControls value={sharedStore} onChange={setSharedStore} />
        </fieldset>
        {layoutOperationsQuery.isPending && <p role="status" className="text-xs text-muted-foreground">{t("opsLayoutLoading")}</p>}
        <RequestError error={layoutOperationsQuery.error}>
          <Button type="button" size="sm" variant="outline" disabled={layoutOperationsQuery.isFetching}
            onClick={() => void layoutOperationsQuery.refetch()}>{t("tryAgain")}</Button>
        </RequestError>
        {layoutOperations && <p className="-mt-1 text-xs text-muted-foreground">{t("opsLayoutSaved")}</p>}

        <details className="group rounded-xl border">
          <summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl p-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">
            <SlidersHorizontal className="size-4 shrink-0" aria-hidden />
            {t("advancedSettings")}
            <ChevronDown className="ml-auto size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <div className="space-y-5 border-t p-3">
            <ScenarioEditor value={scenario} onChange={setScenario} projectId={projectId} setupId={setupId} />

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
                <div className="pt-2 text-sm font-medium">{t("shelfViewTitle")}</div>
                <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
                  {([
                    { id: "chart", title: t("shelfViewChart"), hint: t("shelfViewChartHint") },
                    { id: "photo_chart", title: t("shelfViewPhoto"), hint: t("shelfViewPhotoHint") },
                  ] as const).map((o) => (
                    <button key={o.id} type="button" onClick={() => { setShelfView(o.id); setPhotoError(null); }}
                      aria-pressed={shelfView === o.id}
                      className={cn("rounded-lg border p-2 text-left", shelfView === o.id ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
                      <div className="flex items-center gap-1.5 font-medium">{o.id === "photo_chart" && <Camera className="size-3.5" aria-hidden />}{o.title}</div>
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
            {suggested && pickedModel.kind === "default" && (
              <p className="text-xs text-muted-foreground">{t("defaultModelNoKey", { model: engineInfo?.model ?? "", suggested })}</p>
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
          {locked ? t("previewLockedSummary") : isPreview ? t("previewSummary") : t("finalSummary")}
          {" · "}{scenario?.name ?? t("baselineSituation")}
          {usesLlm && ` · ${modelChoice.kind === "single" ? modelChoice.model ?? t("chooseModel") : modelChoice.kind === "ensemble" ? t("modelEnsemble") : modelOf(engine) || t("serverDefaultModel")}`}
          {town && useTown && ` · ${t("neighborSummary", { percent: Math.round(townScale * 100) })}`}
          {withPhotos && ` · ${t("shelfViewPhoto")}`}
        </p>

        {/* The server's estimate, or a short wait for it; nothing while the form is invalid or the estimate failed. */}
        {!noEstimate && (shownEstimate || (valid && !estimate.isError)) && <div className={cn("rounded-md border px-3 py-2 text-xs", shownEstimate?.warn && estimateCurrent ? "tone-warn" : "bg-muted/40")}
          aria-live="polite" aria-busy={!estimateCurrent || estimate.isFetching}>
          {shownEstimate
            ? <span className={cn(!estimateCurrent && "opacity-60")}>{runEstimateText(locale, shownEstimate)}</span>
            : <span className="text-muted-foreground">{t("checkingEstimate")}</span>}
        </div>}

      </fieldset>

      {(!validSample || !validSeed || !validReplicate) && (
        <p id="run-input-error" role="alert" className="text-xs text-destructive">
          {!validSample ? t("sampleError", { max: personaCount }) : !validSeed ? t("seedError") : t("replicateError")}
        </p>
      )}

      {modelError && <p id="run-model-error" role={!available && !models.isError ? "status" : "alert"} className={cn("break-words text-xs", !available && !models.isError ? "text-muted-foreground" : "text-destructive")}>{modelError}</p>}

      {photos && photos.total > 0 && (
        <p role="status" className="text-xs text-muted-foreground">{t("photographingShelves", { done: photos.done, total: photos.total })}</p>
      )}
      {photoError && <p role="alert" className="break-words text-xs text-destructive">{t("shelfPhotosFailed", { error: photoError })}</p>}

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
        <Button type="submit" disabled={simulate.isPending || preparing || checking || !valid}>
          {preparing ? t("photographingShelves", { done: photos.done, total: photos.total || "…" })
            : checking ? t("checkingEstimate")
            : simulate.isPending ? t("starting") : isPreview ? t("runPreview") : t("runFinalize")}
        </Button>
      </DialogFooter>
    </form>
    {warning && <RunWarning estimate={warning.estimate} onBack={() => setWarning(null)}
      onRun={() => { const { options } = warning; setWarning(null); void start(options); }} />}
    </>
  );
}

/** Asked before a long or costly run starts (shelf photos, if any, are taken only after "Run anyway"). */
function RunWarning({ estimate, onBack, onRun }: { estimate: RunEstimate; onBack: () => void; onRun: () => void }) {
  const { locale, t } = useI18n();
  const calls = estimate.model_calls > 0;
  return (
    <AlertDialog open onOpenChange={(next) => { if (!next) onBack(); }}>
      <AlertDialogContent className="max-h-[92dvh] grid-cols-1 overflow-y-auto [overflow-wrap:anywhere] data-[size=default]:max-w-[calc(100%-2rem)] data-[size=default]:sm:max-w-md">
        <AlertDialogHeader className="min-w-0">
          <AlertDialogTitle>{t("runWarnTitle")}</AlertDialogTitle>
          <AlertDialogDescription>{t("runWarnDescription")}</AlertDialogDescription>
        </AlertDialogHeader>
        <dl className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
          <dt className="text-muted-foreground">{t("estimateShoppers")}</dt>
          <dd>{shoppersOverDaysText(locale, estimate.customers, estimate.days, estimate.per_day)}</dd>
          {estimate.model && <><dt className="text-muted-foreground">{t("model")}</dt><dd className="break-all">{estimate.model}</dd></>}
          <dt className="text-muted-foreground">{t("estimateModelCalls")}</dt>
          <dd>{calls ? new Intl.NumberFormat(locale).format(estimate.model_calls) : t("noModelCalls")}</dd>
          <dt className="text-muted-foreground">{t("estimateTime")}</dt>
          <dd>{durationText(locale, estimate.minutes)}</dd>
          {calls && <><dt className="text-muted-foreground">{t("estimateCost")}</dt><dd>{costText(locale, estimate.cost_usd, estimate.local)}</dd></>}
        </dl>
        <p className="text-xs text-muted-foreground">{t("runWarnHint")}</p>
        <AlertDialogFooter className="min-w-0">
          <AlertDialogCancel>{t("goBack")}</AlertDialogCancel>
          <AlertDialogAction onClick={onRun}>{t("runAnyway")}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
