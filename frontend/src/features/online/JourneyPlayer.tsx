/**
 * A shopper's visit played back as it happened: each page loads in a browser window, the view scrolls to what the
 * shopper picked, the cursor moves there and clicks, and their thought appears, from arrival to the end of the visit.
 */
import { useEffect, useEffectEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MessageCircle, MousePointer2, Pause, Play, RotateCcw, Search } from "lucide-react";
import { getPlayback, onlineKeys, stepScreenshotUrl, type SessionView } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import { ACTION_LABELS, OUTCOME_LABELS, PAGE_LABELS } from "./labels";

type Phase = "arrive" | "aim" | "click" | "read";

// Milliseconds at normal speed; reading time grows with what there is to read.
const PHASE_MS: Record<Exclude<Phase, "read">, number> = { arrive: 800, aim: 1100, click: 600 };
const SPEEDS = [0.5, 1, 2] as const;
// Width over height of the browser window: a laptop screen, or a phone held upright.
const DESKTOP_RATIO = 1.6;
const PHONE_RATIO = 0.5;
const WINDOW_VH = 58;

export function JourneyPlayer({ projectId, runId, view, index, onIndex, money, rival, onRival }: {
  projectId: string; runId: string; view: SessionView; index: number; onIndex: (index: number) => void;
  money: (amount: number) => string; rival: string; onRival: () => void;
}) {
  const { t } = useI18n();
  const { session, shopper } = view;
  const frames = useQuery({
    queryKey: onlineKeys.playback(projectId, runId, view.variant, shopper.id),
    queryFn: ({ signal }) => getPlayback(projectId, runId, view.variant, shopper.id, signal),
  });
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [at, setAt] = useState<{ index: number; phase: Phase }>({ index, phase: "arrive" });
  const [loaded, setLoaded] = useState("");
  const [failed, setFailed] = useState("");
  const [retry, setRetry] = useState({ page: "", attempt: 0 });
  const phase: Phase = at.index === index ? at.phase : "arrive";
  const step = session.steps[Math.min(index, session.steps.length - 1)];
  const frame = frames.data?.[index];
  const last = index >= session.steps.length - 1;
  const pageSrc = step ? stepScreenshotUrl(projectId, runId, view.variant, shopper.id, step.index, false) : "";
  const src = pageSrc && retry.page === pageSrc ? `${pageSrc}&retry=${retry.attempt}` : pageSrc;
  const imageFailed = failed === src && src !== "";
  const ready = loaded === src && frame !== undefined && !imageFailed && !frames.isError;
  const box = step?.choice ? frame?.box ?? null : null;
  const reading = (step?.thought.length ?? 0) + (step?.search_text.length ?? 0) + (step?.choice?.label.length ?? 0);
  const duration = (phase === "read" ? Math.min(4500, 1300 + 25 * reading) : PHASE_MS[phase]) / speed;
  const ended = last && phase === "read" && !playing;

  // An effect event: a parent re-rendering (another player beside this one) must not restart the phase timer.
  const advance = useEffectEvent(() => {
    if (phase === "arrive") setAt({ index, phase: box ? "aim" : "read" });
    else if (phase === "aim") setAt({ index, phase: "click" });
    else if (phase === "click") setAt({ index, phase: "read" });
    else if (last) setPlaying(false);
    else onIndex(index + 1);
  });
  useEffect(() => {
    if (!playing || !ready) return;
    const timer = window.setTimeout(advance, duration);
    return () => window.clearTimeout(timer);
  }, [playing, ready, phase, index, duration]);

  const next = session.steps[index + 1];
  useEffect(() => {
    // Fetch the next page while this one plays, so it appears without a wait.
    if (next) new Image().src = stepScreenshotUrl(projectId, runId, view.variant, shopper.id, next.index, false);
  }, [next, projectId, runId, view.variant, shopper.id]);

  if (!step) return null;
  if (frames.isError) return (
    <div role="alert" className="space-y-2 text-sm text-destructive">
      <p>{frames.error.message}</p>
      <Button size="sm" variant="outline" disabled={frames.isFetching} onClick={() => void frames.refetch()}>{t("studioRetry")}</Button>
    </div>
  );
  const width = frame?.width ?? 1024;
  const height = frame?.height ?? 640;
  const phone = width < 700;
  const windowHeight = Math.min(height, width / (phone ? PHONE_RATIO : DESKTOP_RATIO));
  const aiming = phase !== "arrive" && box !== null;
  const cx = aiming ? (box[0] + box[2]) / 2 : width / 2;
  const cy = aiming ? (box[1] + box[3]) / 2 : windowHeight * 0.45;
  const scroll = aiming ? Math.max(0, Math.min(cy - windowHeight / 2, height - windowHeight)) : 0;
  const move = `${PHASE_MS.aim / speed}ms`;
  const restart = () => { setAt({ index: 0, phase: "arrive" }); onIndex(0); setPlaying(true); };
  const choice = step.choice;
  // The localized action first; the option's own (server-written) label below it.
  const said = choice
    ? step.search_text ? t("onPlaySearch", { text: step.search_text }) : t(ACTION_LABELS[choice.kind])
    : t(OUTCOME_LABELS[session.outcome]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => (ended ? restart() : setPlaying((p) => !p))}>
          {playing ? <Pause aria-hidden /> : <Play aria-hidden />}
          {playing ? t("onPlayPause") : ended ? t("onPlayAgain") : t("onPlayResume")}
        </Button>
        <Button size="icon-sm" variant="ghost" onClick={restart} aria-label={t("onPlayRestart")} title={t("onPlayRestart")}>
          <RotateCcw aria-hidden />
        </Button>
        <div className="inline-flex rounded-md border p-0.5 text-xs" role="group" aria-label={t("onPlaySpeed")}>
          {SPEEDS.map((s) => (
            <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}
              className={cn("rounded px-2 py-0.5 tabular-nums", speed === s ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
              {s}×
            </button>
          ))}
        </div>
        <span className="text-xs tabular-nums text-muted-foreground">{t("onStepOf", { step: index + 1, total: session.steps.length })}</span>
      </div>

      <ol className="flex gap-0.5" aria-label={t("onPlayProgress")}>
        {session.steps.map((s, i) => (
          <li key={s.index} className="min-w-0 flex-1">
            <button type="button" onClick={() => onIndex(i)} aria-current={i === index ? "step" : undefined}
              aria-label={t("onPlayGoTo", { step: i + 1, page: t(PAGE_LABELS[s.page]) })} title={t(PAGE_LABELS[s.page])}
              className={cn("block h-1.5 w-full rounded-full", i < index ? "bg-primary/60" : i === index ? "bg-primary" : "bg-muted")} />
          </li>
        ))}
      </ol>

      {/* The screenshots carry their own browser bar; the window is sized to fit the screen's height. */}
      <div className={cn("mx-auto overflow-hidden rounded-xl border bg-white shadow-sm", phone ? "max-w-[400px]" : "max-w-[900px]")}
        style={{ width: `min(100%, calc(${WINDOW_VH}vh * ${width / windowHeight}))` }}>
        <div className="relative overflow-hidden" style={{ aspectRatio: `${width} / ${windowHeight}` }}>
          <div className="absolute inset-x-0 top-0 transition-transform ease-in-out motion-reduce:transition-none"
            style={{ aspectRatio: `${width} / ${height}`, transform: `translateY(-${(scroll / height) * 100}%)`, transitionDuration: move }}>
            <img key={src} src={src} alt={t("onScreenshotAlt", { title: step.url })}
              onLoad={() => { setLoaded(src); setFailed((previous) => previous === src ? "" : previous); }}
              onError={() => setFailed(src)}
              className={cn("block w-full transition-opacity duration-300", ready ? "opacity-100" : "opacity-0")} />
            {box && (phase === "click" || phase === "read") && (
              <span className="pointer-events-none absolute rounded-lg ring-4 ring-rose-500/80" style={{
                left: `${(box[0] / width) * 100}%`, top: `${(box[1] / height) * 100}%`,
                width: `${((box[2] - box[0]) / width) * 100}%`, height: `${((box[3] - box[1]) / height) * 100}%`,
              }} />
            )}
            {ready && (
              <span className="pointer-events-none absolute z-10 transition-[left,top] ease-in-out motion-reduce:transition-none"
                style={{ left: `${(cx / width) * 100}%`, top: `${(cy / height) * 100}%`, transitionDuration: move }} aria-hidden>
                {phase === "click" && <span className="absolute -top-4 -left-4 size-8 animate-ping rounded-full bg-rose-500/50 motion-reduce:animate-none" />}
                <MousePointer2 className="size-6 -translate-x-1 -translate-y-1 fill-white text-neutral-900 drop-shadow" />
              </span>
            )}
          </div>
          {imageFailed ? (
            <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3 text-center text-xs">
              <p>{t("onPlayImageFailed")}</p>
              <Button size="sm" variant="outline" onClick={() => setRetry((previous) => ({
                page: pageSrc, attempt: previous.page === pageSrc ? previous.attempt + 1 : 1,
              }))}>{t("studioRetry")}</Button>
            </div>
          ) : !ready && <p className="absolute inset-0 grid place-items-center text-xs text-muted-foreground">{t("onPlayLoading")}</p>}
          {ended && (
            <div className="absolute inset-x-3 bottom-3 rounded-xl border bg-background/95 p-3 text-xs shadow-lg animate-in fade-in slide-in-from-bottom-2">
              <div className="text-sm font-semibold">{t(OUTCOME_LABELS[session.outcome])}{session.order_total ? ` · ${money(session.order_total)}` : ""}</div>
              {session.exit_thought && <p className="mt-1 italic">“{session.exit_thought}”</p>}
              {session.rival && rival && (
                <button type="button" onClick={onRival} className="mt-1 text-primary underline-offset-2 hover:underline">
                  {t("onRivalThen", { rival, outcome: t(OUTCOME_LABELS[session.rival.outcome]) })}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="min-h-16 rounded-xl border bg-muted/40 p-2 text-xs" aria-live="polite">
        {phase === "arrive" ? (
          <p className="text-muted-foreground">{t("onPlayOpens", { page: t(PAGE_LABELS[step.page]) })}</p>
        ) : (
          <div key={`${index}:${phase === "read"}`} className="space-y-1 animate-in fade-in">
            <p className="flex items-center gap-1 font-medium">
              {step.search_text ? <Search className="size-3.5 text-primary" aria-hidden /> : <MousePointer2 className="size-3.5 text-primary" aria-hidden />}
              {choice && <span className="rounded bg-rose-600 px-1.5 font-mono text-[0.7rem] font-bold text-white">{choice.number}</span>}
              {said}
            </p>
            {choice && !step.search_text && <p className="truncate text-muted-foreground" title={choice.label}>{choice.label}</p>}
            {step.thought && (phase === "read" || phase === "click") && (
              <p className="flex items-start gap-1 italic"><MessageCircle className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />“{step.thought}”</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
