import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { captureUploadStatus } from "@/services/queries/captureUpload";
import { queryKeys } from "@/shared/queries/keys";
import {
  captureUpload,
  type CaptureUploadOptions,
} from "@/services/mutations/captureUpload";
import { Button } from "@/shared/components/ui/button";
import { checkRecoveryRevision, forgetRecovery, queueIntent, readRecovery, recoveryErrorMessage, restoreRecovery, saveRecovery,
  type RecoveryCopy, type RecoveryOptions } from "./queueRecovery";
import {
  fileDigest,
  fileProblem,
  MAX_QUEUE_BYTES,
  MAX_QUEUE_FILES,
} from "./uploadFiles";

type Stage =
  | "queued"
  | "uploading"
  | "processing"
  | "ready"
  | "upload_error"
  | "poll_error"
  | "recognition_error";
interface Entry {
  id: string;
  file: File;
  digest: string;
  requestId: string;
  stage: Stage;
  captureId?: string;
  detail: string;
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
        if (alive.current) setRecoveryMessage("Recovery copy saved in this browser. Upload starts only when you resume.");
      } else if (action === "restore") {
        const copy = await readRecovery(projectId);
        if (!copy) throw new Error("The browser copy is no longer available. It may have been cleared or evicted.");
        const photos = await restoreRecovery(copy);
        await checkRecoveryRevision(projectId, copy.revision);
        if (!alive.current) return;
        setDetector(copy.options.detector); setModel(copy.options.model); setCurrency(copy.options.currency); setRackType(copy.options.rack_type);
        const intent = queueIntent(photos, copy.options);
        recoverySession.current = { revision: copy.revision, intent };
        setSaved(copy); setSavedIntent(intent);
        commit(photos.map(p => ({ ...p, stage: "queued", detail: "Restored — resume to recover accepted photos or upload unsent files" })));
        pause.current = true; setPaused(true); setMessages([]);
        setRecoveryMessage("Queue restored and paused. Resume checks existing request IDs before starting new recognition.");
      } else {
        const revision = recoverySession.current?.revision ?? saved?.revision;
        if (revision) await forgetRecovery(projectId, revision);
        recoverySession.current = null;
        if (alive.current) {
          setSaved(null); setSavedIntent(null);
          if (action === "clear") { commit([]); setMessages([]); }
          setRecoveryMessage("Browser recovery copy removed. Uploaded photos were not deleted.");
        }
      }
    } catch (error) {
      if (alive.current) setRecoveryMessage(`${recoveryErrorMessage(error)} Keep this page open; your live queue was not replaced.`);
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
        notices.push(`${file.name}: Queue limit is 20 photos and 100 MB.`);
        continue;
      }
      try {
        const digest = await fileDigest(file);
        if (!alive.current) return;
        if (next.some((e) => e.digest === digest)) {
          notices.push(`${file.name}: Identical photo already in this queue.`);
          continue;
        }
        next.push({
          id: crypto.randomUUID(),
          requestId: crypto.randomUUID().replace(/-/g, ""),
          file,
          digest,
          stage: "queued",
          detail: "Waiting to start",
        });
        bytes += file.size;
      } catch (error) {
        notices.push(
          `${file.name}: ${error instanceof Error ? error.message : "Could not read file"}`,
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
            update(entry.id, { stage: "uploading", detail: "Checking recovery and uploading…" });
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
            detail: "Recognition in progress…",
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
                    ? `${view.status.items} products — review names, prices and facings`
                    : view.status.error || "Recognition failed",
              });
              refresh();
              break;
            }
            update(entry.id, {
              detail: view.status.stage
                ? `Recognition: ${view.status.stage}`
                : "Waiting for recognition…",
            });
            await new Promise((resolve) => setTimeout(resolve, 1500));
          }
        } catch (error) {
          if (!alive.current) return;
          update(entry.id, {
            stage: cid ? "poll_error" : "upload_error",
            captureId: cid,
            detail: recoveryErrorMessage(error),
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
      aria-label="Photo upload queue"
      className="max-h-[70dvh] space-y-3 overflow-y-auto rounded-2xl border bg-card p-4 text-sm md:max-h-full"
    >
      <h2 className="text-lg font-semibold">Add shelf photos together</h2>
      <p>
        Choose or drop up to 20 JPEG, PNG or WebP photos (25 MB each, 100 MB
        total). Review each result, then use Combine reviewed shelf photos to
        build one layout.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label>
          Find products with
          <select
            aria-label="Find products with"
            disabled={locked}
            className="block h-10 w-full rounded border"
            value={detector}
            onChange={(e) => setDetector(e.target.value as api.CaptureDetector)}
          >
            <option value="auto">Best available</option>
            <option value="classic">Shelf geometry (fast)</option>
            <option value="gdino">Grounding DINO</option>
            <option value="vlm">Vision model boxes</option>
          </select>
        </label>
        <label>
          Read products with
          <select
            aria-label="Read products with"
            disabled={locked}
            className="block h-10 w-full rounded border"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            <option value="">App's vision model</option>
            {models
              .filter((m) => m.vision)
              .map((m) => (
                <option key={m.ref} value={m.ref}>
                  {m.label}
                </option>
              ))}
            <option value="none">Don't read (typical prices)</option>
            {model && model !== "none" && !models.some(m => m.vision && m.ref === model) && <option value={model}>Saved model: {model}</option>}
          </select>
        </label>
        <label>
          Prices in
          <select
            aria-label="Prices in"
            disabled={locked}
            className="block h-10 w-full rounded border"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          >
            {["USD", "KRW", "JPY", "EUR", "GBP"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Fixture
          <select
            aria-label="Fixture"
            disabled={locked}
            className="block h-10 w-full rounded border"
            value={rackType}
            onChange={(e) => setRackType(e.target.value as "shelf" | "fridge")}
          >
            <option value="shelf">Shelf / gondola</option>
            <option value="fridge">Fridge</option>
          </select>
        </label>
      </div>
      <p>
        Settings stay fixed for this queue. Recognition may call the selected
        model for each photo. This queue waits for one photo to finish before
        sending the next.
      </p>
      <section aria-label="Queue recovery" className="space-y-2 rounded border p-3">
        <h3 className="font-semibold">Continue after leaving this page</h3>
        <p>Save a recovery copy to keep these photos, settings and request IDs in this browser. Photos stay on this device until you start uploads. This is not a cloud backup; clearing browser data or storage eviction removes the copy.</p>
        {saved && <p>{saved.photos.length} photos saved for this store. Restore pauses the queue; it does not call a model.</p>}
        {savedIntent && <p>{savedIntent === queueIntent(entries, recoveryOptions) ? "Current upload choices are saved." : "Queue changes are not saved yet. Save them now, or resume to save before the next upload."}</p>}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={working || picking || recovering || !entries.length} onClick={() => void recoveryAction("save")}>Save queue on this browser</Button>
          <Button variant="outline" disabled={working || picking || recovering} onClick={() => void recoveryAction("restore")}>{entries.length ? "Replace local queue from saved copy" : "Restore saved queue"}</Button>
          <Button variant="outline" disabled={working || picking || recovering || !saved} onClick={() => void recoveryAction("forget")}>Forget saved copy</Button>
        </div>
        <p>Restoring replaces local choices only after the saved photos pass validation. Uploaded photos stay unchanged.</p>
        {recovering && <p role="status">Checking browser recovery…</p>}
        {recoveryMessage && <p role="status" className="break-words">{recoveryMessage}</p>}
      </section>
      <button
        type="button"
        disabled={!canPick}
        className="w-full rounded-xl border-2 border-dashed p-6 disabled:opacity-50"
        onClick={() => input.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void pick(Array.from(e.dataTransfer.files));
        }}
      >
        Choose photos or drop them here
      </button>
      <input
        ref={input}
        aria-label="Shelf photo files"
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
          Could not load the store currency.{" "}
          <Button onClick={() => void project.refetch()}>Retry store</Button>
        </p>
      )}
      {picking && <p role="status">Checking selected files…</p>}
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
          Start / resume queue
        </Button>
        <Button
          variant="outline"
          disabled={!working || paused}
          onClick={() => {
            pause.current = true;
            setPaused(true);
          }}
        >
          Pause after current photo
        </Button>
        <Button
          variant="outline"
          disabled={working || picking || recovering || !entries.length}
          onClick={() => {
            if (recoverySession.current) void recoveryAction("clear");
            else { commit([]); setMessages([]); }
          }}
        >
          {savedIntent ? "Clear queue and saved copy" : "Clear local queue"}
        </Button>
      </div>
      <p>
        {entries.filter((e) => e.stage === "ready").length} of {entries.length}{" "}
        ready.{" "}
        {working
          ? paused
            ? "Will pause after the current photo."
            : "Processing queue…"
          : "Queue stopped."}{" "}
        Accepted recognition continues on the server when you pause or leave.
        Save a browser recovery copy before leaving if you want to retain unsent files. Restored copies recover progress when resumed.
      </p>
      <ol className="space-y-2">
        {entries.map((e) => (
          <li key={e.id} className="rounded-lg border p-3">
            <p className="break-words font-medium">{e.file.name}</p>
            <p role="status" className="break-words">
              {e.detail}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {e.captureId && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onReview(e.captureId!)}
                >
                  Review photo
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
                      detail: "Waiting to retry",
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
                    ? "Retry recognition (new attempt)"
                    : "Retry this photo"}
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
                  Remove from queue
                </Button>
              )}
            </div>
          </li>
        ))}
      </ol>
      {!!entries.length && (
        <p>
          Removing or clearing this list does not delete uploaded photos.
          Missing names and typical prices need review; these are not verified
          inventory or prices.
        </p>
      )}
    </section>
  );
}
