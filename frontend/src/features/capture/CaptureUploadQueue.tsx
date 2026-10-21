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
  visible = true,
}: {
  visible?: boolean;
  projectId: string;
  onAccepted: () => void;
  onReview: (id: string) => void;
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
  const locked = entries.length > 0 || picking || working;
  const canPick = !picking && !working && !!project.data && !project.isError;
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      pause.current = true;
      controller.current?.abort();
    };
  }, []);
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
  const pick = async (files: File[]) => {
    if (!canPick) return;
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
    if (busy.current || picking) return;
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
            update(entry.id, { stage: "uploading", detail: "Uploading…" });
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
            detail: error instanceof Error ? error.message : "Request failed",
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
      className="max-h-[70dvh] space-y-3 overflow-y-auto rounded-2xl border bg-card p-4 text-sm"
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
          disabled={working || picking || !entries.length}
          onClick={() => {
            commit([]);
            setMessages([]);
          }}
        >
          Clear local queue
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
        Keep this page open for unsent files; local files are not retained after
        reload.
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
                  disabled={working || picking}
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
                  disabled={picking}
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
