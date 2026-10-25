import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, ImagePlus } from "lucide-react";
import * as api from "@/shared/api/client";
import { captureUploadStatus } from "@/services/queries/captureUpload";
import { queryKeys } from "@/shared/queries/keys";
import {
  captureUpload,
  type CaptureUploadOptions,
} from "@/services/mutations/captureUpload";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { checkRecoveryRevision, forgetRecovery, queueIntent, readRecovery, recoveryErrorMessage, restoreRecovery, saveRecovery,
  type RecoveryCopy, type RecoveryOptions } from "./queueRecovery";
import {
  fileDigest,
  fileProblem,
  MAX_QUEUE_BYTES,
  MAX_QUEUE_FILES,
} from "./uploadFiles";
import { STAGES } from "./stages";

type Stage =
  | "queued"
  | "uploading"
  | "processing"
  | "ready"
  | "upload_error"
  | "poll_error"
  | "recognition_error";
/** A status line kept as a message key so it follows the selected language; server text stays as sent. */
type Detail = { key: MessageKey; values?: Record<string, string | number> } | { text: string };
interface Entry {
  id: string;
  file: File;
  digest: string;
  requestId: string;
  stage: Stage;
  captureId?: string;
  detail: Detail;
}
export function CaptureUploadQueue({
  projectId,
  onAccepted,
  onReview,
  onRecoveryAvailable,
  visible = true,
}: {
  visible?: boolean;
  projectId: string;
  onAccepted: () => void;
  onReview: (id: string) => void;
  onRecoveryAvailable?: (available: boolean) => void;
}) {
  const { t } = useI18n();
  const [entries, setEntries] = useState<Entry[]>([]);
  const entriesRef = useRef<Entry[]>([]);
  const [messages, setMessages] = useState<string[]>([]);
  const [picking, setPicking] = useState(false);
  const [working, setWorking] = useState(false);
  const [paused, setPaused] = useState(true);
  const [detector, setDetector] = useState<api.CaptureDetector>("auto");
  const [model, setModel] = useState("");
  const [chosenCurrency, setCurrency] = useState<string | null>(null);
  const [rackType, setRackType] = useState<"shelf" | "fridge">("shelf");
  const [saved, setSaved] = useState<RecoveryCopy | null>(null);
  const [recovering, setRecovering] = useState(false);
  const [recoveryMessage, setRecoveryMessage] = useState("");
  const [savedIntent, setSavedIntent] = useState<string | null>(null);
  const recoverySession = useRef<{ revision: string; intent: string } | null>(null);
  const recoveryBusy = useRef(false);
  const recoveryEpoch = useRef(0);
  useEffect(() => { onRecoveryAvailable?.(!!saved); }, [saved, onRecoveryAvailable]);
  const input = useRef<HTMLInputElement>(null);
  const alive = useRef(true);
  const busy = useRef(false);
  const pause = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const qc = useQueryClient();
  const upload = useMutation(captureUpload(projectId));
  const project = useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: ({ signal }) => api.getProject(projectId, signal),
    enabled: visible,
  });
  const { data: models = [] } = useQuery({
    queryKey: queryKeys.models(),
    queryFn: ({ signal }) => api.getModels(signal),
    staleTime: 60_000,
    enabled: visible,
  });
  const currency = chosenCurrency ?? project.data?.metadata.currency ?? "USD";
  const locked = entries.length > 0 || picking || working || recovering;
  const canPick = !picking && !working && !recovering && !!project.data && !project.isError;
  useEffect(() => {
    alive.current = true;
    let current = true;
    const epoch = recoveryEpoch.current;
    void readRecovery(projectId).then((copy) => {
      if (current && epoch === recoveryEpoch.current) setSaved(copy);
    }).catch((error: Error) => { if (current && epoch === recoveryEpoch.current) setRecoveryMessage(error.message); });
    return () => {
      current = false;
      alive.current = false;
      pause.current = true;
      controller.current?.abort();
    };
  }, [projectId]);
  const commit = (next: Entry[]) => {
    entriesRef.current = next;
    if (alive.current) setEntries(next);
  };
  const update = (id: string, change: Partial<Entry>) =>
    commit(
      entriesRef.current.map((e) => (e.id === id ? { ...e, ...change } : e)),
    );
  const refresh = () =>
    void qc.invalidateQueries({
      queryKey: ["projects", projectId, "captures"],
    });
  const recoveryOptions: RecoveryOptions = { detector, model, currency, rack_type: rackType };
  const checkpoint = async () => {
    const photos = entriesRef.current, intent = queueIntent(photos, recoveryOptions);
    const session = recoverySession.current;
    if (session?.intent === intent) {
      await checkRecoveryRevision(projectId, session.revision);
      return;
    }
    const copy = await saveRecovery(projectId, session?.revision ?? null, photos, recoveryOptions);
    recoverySession.current = { revision: copy.revision, intent };
    if (alive.current) { setSaved(copy); setSavedIntent(intent); }
  };
  const recoveryAction = async (action: "save" | "restore" | "forget" | "clear") => {
    if (recoveryBusy.current || busy.current || picking) return;
    recoveryEpoch.current += 1;
    recoveryBusy.current = true; setRecovering(true); setRecoveryMessage("");
    try {
      if (action === "save") {
        await checkpoint();
        if (alive.current) setRecoveryMessage(t("capRecoverySaved"));
      } else if (action === "restore") {
        const copy = await readRecovery(projectId);
        if (!copy) throw new Error(t("capRecoveryGone"));
        const photos = await restoreRecovery(copy);
        await checkRecoveryRevision(projectId, copy.revision);
        if (!alive.current) return;
        setDetector(copy.options.detector); setModel(copy.options.model); setCurrency(copy.options.currency); setRackType(copy.options.rack_type);
        const intent = queueIntent(photos, copy.options);
        recoverySession.current = { revision: copy.revision, intent };
        setSaved(copy); setSavedIntent(intent);
        commit(photos.map(p => ({ ...p, stage: "queued", detail: { key: "capRestoredDetail" } })));
        pause.current = true; setPaused(true); setMessages([]);
        setRecoveryMessage(t("capQueueRestored"));
      } else {
        const revision = recoverySession.current?.revision ?? saved?.revision;
        if (revision) await forgetRecovery(projectId, revision);
        recoverySession.current = null;
        if (alive.current) {
          setSaved(null); setSavedIntent(null);
          if (action === "clear") { commit([]); setMessages([]); }
          setRecoveryMessage(t("capRecoveryRemoved"));
        }
      }
    } catch (error) {
      if (alive.current) setRecoveryMessage(t("capRecoveryFailed", { error: recoveryErrorMessage(error) }));
    } finally {
      recoveryBusy.current = false;
      if (alive.current) setRecovering(false);
    }
  };
  const pick = async (files: File[]) => {
    if (!canPick || recoveryBusy.current) return;
    setPicking(true);
    const notices: string[] = [];
    const next = [...entriesRef.current];
    let bytes = next.reduce((sum, e) => sum + e.file.size, 0);
    for (const file of files) {
      const problem = fileProblem(file);
      if (problem) {
        notices.push(`${file.name}: ${problem}`);
        continue;
      }
      if (
        next.length >= MAX_QUEUE_FILES ||
        bytes + file.size > MAX_QUEUE_BYTES
      ) {
        notices.push(`${file.name}: ${t("capQueueLimit")}`);
        continue;
      }
      try {
        const digest = await fileDigest(file);
        if (!alive.current) return;
        if (next.some((e) => e.digest === digest)) {
          notices.push(`${file.name}: ${t("capDuplicatePhoto")}`);
          continue;
        }
        next.push({
          id: crypto.randomUUID(),
          requestId: crypto.randomUUID().replace(/-/g, ""),
          file,
          digest,
          stage: "queued",
          detail: { key: "capWaitingToStart" },
        });
        bytes += file.size;
      } catch (error) {
        notices.push(
          `${file.name}: ${error instanceof Error ? error.message : t("capCouldNotReadFile")}`,
        );
      }
    }
    if (alive.current) {
      if (!entriesRef.current.length && next.length) setCurrency(currency);
      commit(next);
      setMessages(notices);
      setPicking(false);
    }
  };
  const run = async () => {
    if (
      busy.current ||
      recoveryBusy.current ||
      picking ||
      entriesRef.current.some(
        (entry) => entry.stage === "upload_error" || entry.stage === "poll_error",
      )
    ) {
      return;
    }
    busy.current = true;
    pause.current = false;
    setPaused(false);
    setWorking(true);
    const options: CaptureUploadOptions = {
      detector,
      model,
      currency,
      rack_type: rackType,
    };
    const abort = new AbortController();
    controller.current = abort;
    try {
      while (alive.current && !pause.current) {
        const entry = entriesRef.current.find((e) => e.stage === "queued");
        if (!entry) break;
        let cid = entry.captureId;
        try {
          if (!cid) {
            update(entry.id, { stage: "uploading", detail: { key: "capUploading" } });
            // A newly generated retry ID must reach durable storage before the upload can be accepted.
            if (recoverySession.current) await checkpoint();
            if (!alive.current) break;
            const accepted = await upload.mutateAsync({
              file: entry.file,
              options: { ...options, request_id: entry.requestId },
              signal: abort.signal,
            });
            if (!alive.current) return;
            cid = accepted.capture_id;
            update(entry.id, { captureId: cid });
            onAccepted();
            refresh();
          }
          update(entry.id, {
            stage: "processing",
            detail: { key: "capRecognitionInProgress" },
          });
          while (alive.current) {
            const view = await captureUploadStatus(
              projectId,
              cid,
              abort.signal,
            );
            if (!alive.current) return;
            if (
              view.status.status === "completed" ||
              view.status.status === "failed"
            ) {
              update(entry.id, {
                stage:
                  view.status.status === "completed"
                    ? "ready"
                    : "recognition_error",
                detail:
                  view.status.status === "completed"
                    ? { key: "capRecognitionReady", values: { count: view.status.items } }
                    : view.status.error ? { text: view.status.error } : { key: "capRecognitionFailed" },
              });
              refresh();
              break;
            }
            update(entry.id, {
              detail: view.status.stage
                ? STAGES[view.status.stage] ? { key: STAGES[view.status.stage]! } : { key: "capRecognitionStage", values: { stage: view.status.stage } }
                : { key: "capWaitingRecognition" },
            });
            await new Promise((resolve) => setTimeout(resolve, 1500));
          }
        } catch (error) {
          if (!alive.current) return;
          update(entry.id, {
            stage: cid ? "poll_error" : "upload_error",
            captureId: cid,
            detail: { text: recoveryErrorMessage(error) },
          });
          pause.current = true;
          setPaused(true);
        }
      }
    } finally {
      busy.current = false;
      if (alive.current) {
        setWorking(false);
        setPaused(true);
      }
    }
  };
  const unresolved = entries.some(
    (e) => e.stage === "upload_error" || e.stage === "poll_error",
  );
  return (
    <section
      aria-label={t("capQueueAria")}
      className="min-w-0 max-h-[70dvh] space-y-3 overflow-y-auto rounded-2xl border bg-card p-4 text-sm md:max-h-full [&_button]:h-auto [&_button]:min-h-9 [&_button]:max-w-full [&_button]:whitespace-normal [&_button]:py-2"
    >
      <h2 className="flex items-center gap-2 font-display text-xl"><Camera className="size-5 text-primary" aria-hidden /> {t("capQueueTitle")}</h2>
      <p>{t("capQueueIntro")}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 [&>label]:min-w-0">
        <label>
          {t("capFindWith")}
          <select
            aria-label={t("capFindWith")}
            disabled={locked}
            className="mt-1 block h-10 w-full rounded-xl border bg-card/60 px-2.5 text-sm"
            value={detector}
            onChange={(e) => setDetector(e.target.value as api.CaptureDetector)}
          >
            <option value="auto">{t("capDetectorAuto")}</option>
            <option value="classic">{t("capDetectorClassic")}</option>
            <option value="gdino">Grounding DINO</option>
            <option value="vlm">{t("capDetectorVlm")}</option>
          </select>
        </label>
        <label>
          {t("capReadWith")}
          <select
            aria-label={t("capReadWith")}
            disabled={locked}
            className="mt-1 block h-10 w-full rounded-xl border bg-card/60 px-2.5 text-sm"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            <option value="">{t("studioAppVisionModel")}</option>
            {models
              .filter((m) => m.vision)
              .map((m) => (
                <option key={m.ref} value={m.ref}>
                  {m.label}
                </option>
              ))}
            <option value="none">{t("capDontRead")}</option>
            {model && model !== "none" && !models.some(m => m.vision && m.ref === model) && <option value={model}>{t("capSavedModel", { model })}</option>}
          </select>
        </label>
        <label>
          {t("capPricesInLabel")}
          <select
            aria-label={t("capPricesInLabel")}
            disabled={locked}
            className="mt-1 block h-10 w-full rounded-xl border bg-card/60 px-2.5 text-sm"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          >
            {[...new Set(["USD", "KRW", "JPY", "EUR", "GBP", currency])].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          {t("capFixture")}
          <select
            aria-label={t("capFixture")}
            disabled={locked}
            className="mt-1 block h-10 w-full rounded-xl border bg-card/60 px-2.5 text-sm"
            value={rackType}
            onChange={(e) => setRackType(e.target.value as "shelf" | "fridge")}
          >
            <option value="shelf">{t("capFixtureShelf")}</option>
            <option value="fridge">{t("capFixtureFridge")}</option>
          </select>
        </label>
      </div>
      <p>{t("capQueueSettingsHint")}</p>
      <button
        type="button"
        disabled={!canPick}
        className="group flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-primary/35 bg-primary/[0.03] p-8 py-8! text-center transition-colors hover:border-primary hover:bg-primary/[0.07] disabled:opacity-50"
        onClick={() => input.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void pick(Array.from(e.dataTransfer.files));
        }}
      >
        <span className="grid size-12 place-items-center rounded-2xl heat-gradient text-white shadow-[0_10px_28px_-12px_var(--heat-2)] transition-transform group-hover:scale-105" aria-hidden>
          <ImagePlus className="size-6" />
        </span>
        <span className="text-base font-semibold text-foreground">{t("capChooseOrDrop")}</span>
      </button>
      <input
        ref={input}
        aria-label={t("capPhotoFiles")}
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          void pick(files);
        }}
      />
      {project.isError && (
        <p role="alert">
          {t("capCurrencyError")}{" "}
          <Button onClick={() => void project.refetch()}>{t("capRetryStore")}</Button>
        </p>
      )}
      {picking && <p role="status">{t("capCheckingFiles")}</p>}
      <section aria-label={t("capRecoveryAria")} className="space-y-2 rounded-xl border border-dashed bg-muted/30 p-3 text-[0.8rem] text-muted-foreground [&_h3]:text-foreground">
        <h3 className="font-semibold">{t("capRecoveryTitle")}</h3>
        <p>{t("capRecoveryIntro")}</p>
        {saved && <p>{t("capRecoverySavedPhotos", { count: saved.photos.length })}</p>}
        {savedIntent && <p>{savedIntent === queueIntent(entries, recoveryOptions) ? t("capRecoveryCurrent") : t("capRecoveryUnsaved")}</p>}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={working || picking || recovering || !entries.length} onClick={() => void recoveryAction("save")}>{t("capSaveQueue")}</Button>
          <Button variant="outline" disabled={working || picking || recovering} onClick={() => void recoveryAction("restore")}>{entries.length ? t("capReplaceFromSaved") : t("capRestoreSaved")}</Button>
          <Button variant="outline" disabled={working || picking || recovering || !saved} onClick={() => void recoveryAction("forget")}>{t("capForgetSaved")}</Button>
        </div>
        <p>{t("capRestoreHint")}</p>
        {recovering && <p role="status">{t("capCheckingRecovery")}</p>}
        {recoveryMessage && <p role="status" className="break-words">{recoveryMessage}</p>}
      </section>
      {messages.length > 0 && (
        <ul role="alert" className="max-h-32 overflow-auto">
          {messages.map((m, i) => (
            <li className="break-words" key={i}>
              {m}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={
            working ||
            picking ||
            recovering ||
            unresolved ||
            !entries.some((e) => e.stage === "queued")
          }
          onClick={() => void run()}
        >
          {t("capStartResume")}
        </Button>
        <Button
          variant="outline"
          disabled={!working || paused}
          onClick={() => {
            pause.current = true;
            setPaused(true);
          }}
        >
          {t("capPauseAfter")}
        </Button>
        <Button
          variant="outline"
          disabled={working || picking || recovering || !entries.length}
          onClick={() => {
            if (recoverySession.current) void recoveryAction("clear");
            else { commit([]); setMessages([]); }
          }}
        >
          {savedIntent ? t("capClearQueueAndSaved") : t("capClearLocalQueue")}
        </Button>
      </div>
      <p>
        {t("capReadyCount", { ready: entries.filter((e) => e.stage === "ready").length, total: entries.length })}{" "}
        {working
          ? paused
            ? t("capWillPause")
            : t("capProcessingQueue")
          : t("capQueueStopped")}{" "}
        {t("capQueueServerHint")}
      </p>
      <ol className="space-y-2">
        {entries.map((e) => (
          <li key={e.id} className="rounded-lg border p-3">
            <p className="break-words font-medium">{e.file.name}</p>
            <p role="status" className="break-words">
              {"text" in e.detail ? e.detail.text : t(e.detail.key, e.detail.values)}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {e.captureId && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onReview(e.captureId!)}
                >
                  {t("capReviewPhoto")}
                </Button>
              )}
              {["upload_error", "poll_error", "recognition_error"].includes(
                e.stage,
              ) && (
                <Button
                  size="sm"
                  disabled={
                    working || picking || recovering || (e.stage === "recognition_error" && unresolved)
                  }
                  onClick={() => {
                    update(e.id, {
                      stage: "queued",
                      detail: { key: "capWaitingRetry" },
                      ...(e.stage === "recognition_error"
                        ? {
                            captureId: undefined,
                            requestId: crypto.randomUUID().replace(/-/g, ""),
                          }
                        : {}),
                    });
                    void run();
                  }}
                >
                  {e.stage === "recognition_error"
                    ? t("capRetryRecognition")
                    : t("capRetryPhoto")}
                </Button>
              )}
              {!["uploading", "processing"].includes(e.stage) && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={picking || recovering}
                  onClick={() =>
                    commit(
                      entriesRef.current.filter((item) => item.id !== e.id),
                    )
                  }
                >
                  {t("capRemoveFromQueue")}
                </Button>
              )}
            </div>
          </li>
        ))}
      </ol>
      {!!entries.length && (
        <p>{t("capQueueFooter")}</p>
      )}
    </section>
  );
}
