// One shopper's visit, step by step: the page they saw (drawn again exactly as it was, with the same badge
// numbers), the option they picked and what they thought.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Columns2, Film, ListOrdered, Mail, MessageCircle, Play } from "lucide-react";

import { getSession, journeyGifUrl, onlineKeys, stepScreenshotUrl, type SessionView } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { cn } from "@/shared/utils/cn";
import { currencyCode, formatMoney, formatDecimal } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { personaLabel } from "@/shared/i18n/personaLabels";

import { JourneyPlayer } from "./JourneyPlayer";
import { ShopperChat } from "./ShopperChat";
import { SideBySide } from "./SideBySide";
import { ACTION_LABELS, ARRIVAL_LABELS, DEVICE_LABELS, FUNNEL_LABELS, MISSION_LABELS, OUTCOME_LABELS, PAGE_LABELS, VISION_LABELS } from "./labels";

/** `rival`: the run's rival shop ("" without one); its visits are the store index after the variants. `play`: open on
 * the animated playback instead of the step-by-step view; `compare`: on the control and this store played side by
 * side. */
export function JourneyViewer({ projectId, runId, variant, shopperId, variants, rival = "", currency, play = false, compare = false,
  onVariant, onClose }: {
  projectId: string; runId: string; variant: number; shopperId: string; variants: string[]; rival?: string; currency: string;
  play?: boolean; compare?: boolean; onVariant: (variant: number) => void; onClose: () => void;
}) {
  const { t } = useI18n();
  const [sideBySide, setSideBySide] = useState(compare && variants.length > 1);
  const pairable = variants.length > 1 && variant < variants.length;
  const code = currencyCode(currency);
  const session = useQuery({
    queryKey: onlineKeys.session(projectId, runId, variant, shopperId),
    queryFn: ({ signal }) => getSession(projectId, runId, variant, shopperId, signal),
  });
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-h-[94vh] overflow-y-auto sm:max-w-[1100px]">
        <DialogHeader>
          <DialogTitle>{t("onJourneyTitle")}</DialogTitle>
          <DialogDescription>{t("onJourneyHint")}</DialogDescription>
        </DialogHeader>
        {(variants.length > 1 || variant >= variants.length) && (
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex flex-wrap rounded-md border p-0.5 text-xs" role="group" aria-label={t("onRunStores")}>
              {/* The rival tab shows only while its visit is open: not every shopper went there. */}
              {[...variants, ...(variant >= variants.length ? [t("onRivalTab", { rival })] : [])].map((name, i) => (
                <button key={i} type="button" aria-pressed={variant === i} onClick={() => onVariant(i)}
                  className={cn("rounded px-2 py-0.5", variant === i ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>{name}</button>
              ))}
            </div>
            {pairable && (
              <Button size="xs" variant={sideBySide ? "default" : "outline"} aria-pressed={sideBySide}
                onClick={() => setSideBySide((x) => !x)} title={t("onSideHint")}>
                <Columns2 aria-hidden /> {t("onSideBySide")}
              </Button>
            )}
          </div>
        )}
        {sideBySide && pairable ? (
          <SideBySide key={variant} projectId={projectId} runId={runId} shopperId={shopperId} stores={[0, variant || 1]}
            names={variants} money={(x) => formatMoney(x, code)} />
        ) : (
          <>
            {session.isPending && <p className="text-sm text-muted-foreground">{t("studioLoading")}</p>}
            {session.isError && <p role="alert" className="text-sm text-destructive">{session.error.message}</p>}
            {session.data && (
              <Journey key={`${variant}:${shopperId}`} projectId={projectId} runId={runId} view={session.data} currency={currency}
                rival={rival} play={play} onRival={() => onVariant(variants.length)} />
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Journey({ projectId, runId, view, currency, rival, play, onRival }: {
  projectId: string; runId: string; view: SessionView; currency: string; rival: string; play: boolean; onRival: () => void;
}) {
  const { t } = useI18n();
  const { shopper, session } = view;
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(play);
  const [narrow, setNarrow] = useState(shopper.device === "mobile");
  const [asking, setAsking] = useState(false);
  const step = session.steps[Math.min(index, session.steps.length - 1)];
  const code = currencyCode(currency);
  const money = (x: number) => formatMoney(x, code);
  if (!step) return null;
  const choice = step.choice;
  return (
    <div className="grid grid-cols-1 gap-4 text-sm lg:grid-cols-[300px_minmax(0,1fr)]">
      <div className="space-y-3">
        <div className="rounded-xl border p-3 text-xs">
          <div className="font-semibold">{shopper.identity}</div>
          <div className="text-muted-foreground">
            {personaLabel(shopper.age_group, t)} · {personaLabel(shopper.gender, t)} · {t(DEVICE_LABELS[shopper.device])}
            {shopper.vision !== "typical" ? ` · ${t(VISION_LABELS[shopper.vision])}` : ""}
            {shopper.arrival && shopper.arrival !== "direct" ? ` · ${t(ARRIVAL_LABELS[shopper.arrival])}` : ""}
          </div>
          <div className="mt-2"><span className="rounded bg-primary/10 px-1.5 py-0.5 text-primary">{t(MISSION_LABELS[shopper.mission])}</span></div>
          <p className="mt-1">{shopper.goal}</p>
          <p className="mt-1 text-muted-foreground">
            {shopper.budget ? t("onBudget", { amount: money(shopper.budget) }) : t("onNoBudget")}
            {" · "}{t("onPatience", { minutes: Math.round(shopper.patience_sec / 60) })}
            {shopper.has_account ? ` · ${t("onHasAccount")}` : ""}
          </p>
        </div>
        <div className="rounded-xl border p-3 text-xs">
          <div className="font-semibold">{t(OUTCOME_LABELS[session.outcome])}</div>
          <div className="text-muted-foreground">
            {t("onJourneyStats", { steps: session.steps.filter((s) => s.choice).length, seconds: Math.round(session.seconds) })}
            {session.order_total ? ` · ${money(session.order_total)}` : ""}
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {session.reached.map((r) => <span key={r} className="rounded bg-muted px-1.5">{t(FUNNEL_LABELS[r])}</span>)}
          </div>
          {session.order.length > 0 && (
            <ul className="mt-2 list-disc pl-4">{session.order.map((line) => <li key={line.product_id}>{line.name} ×{line.quantity}</li>)}</ul>
          )}
          {session.exit_thought && <p className="mt-2 italic">“{session.exit_thought}”</p>}
          {session.rival && rival && (
            <div className="mt-2 rounded-md bg-amber-500/10 px-2 py-1">
              <div className="font-medium">
                {t("onRivalThen", { rival, outcome: t(OUTCOME_LABELS[session.rival.outcome]) })}
                {session.rival.order_total ? ` · ${money(session.rival.order_total)}` : ""}
              </div>
              <button type="button" onClick={onRival} className="text-primary underline-offset-2 hover:underline">{t("onRivalReplay")}</button>
            </div>
          )}
        </div>
        {session.survey && (
          <div className="rounded-xl border p-3 text-xs">
            <div className="font-semibold">{t("onSurveys")}</div>
            <div className="text-muted-foreground">
              {t("onSurveyLine", { satisfaction: session.survey.satisfaction, ease: session.survey.ease, recommend: session.survey.recommend })}
              {" · "}{session.survey.would_return ? t("onSurveyWouldReturn") : t("onSurveyWouldNotReturn")}
            </div>
            {session.survey.frustration && <p className="mt-1">“{session.survey.frustration}”</p>}
            {session.survey.improvement && <p className="mt-1 text-muted-foreground">→ {session.survey.improvement}</p>}
          </div>
        )}
        <div className="rounded-xl border p-3">
          <button type="button" aria-expanded={asking} onClick={() => setAsking((x) => !x)}
            className="flex w-full items-center gap-1.5 text-left text-xs font-semibold">
            <MessageCircle className="size-3.5 text-primary" aria-hidden /> {t("onAskTitle")}
          </button>
          {asking && (
            <div className="mt-2">
              <ShopperChat projectId={projectId} runId={runId} variant={view.variant} shopper={shopper} outcome={session.outcome}
                onStep={(i) => setIndex(Math.min(Math.max(0, i), session.steps.length - 1))} />
            </div>
          )}
        </div>
        <ol className="max-h-[50vh] space-y-1 overflow-y-auto">
          {session.steps.map((s, i) => (
            <li key={s.index}>
              {s.index === session.returned_at && (
                <p className="my-1 flex items-center gap-1 rounded-md bg-sky-500/10 px-2 py-1 text-[0.7rem] font-medium">
                  <Mail className="size-3.5" aria-hidden />
                  {t(s.state.reminder_percent ? "onReturnedDiscount" : "onReturned", { percent: s.state.reminder_percent ?? 0 })}
                </p>
              )}
              <button type="button" onClick={() => setIndex(i)} aria-current={i === index ? "step" : undefined}
                className={cn("w-full rounded-lg border px-2 py-1 text-left text-xs", i === index ? "border-primary bg-primary/8" : "hover:bg-muted")}>
                <span className="font-medium">{i + 1}. {t(PAGE_LABELS[s.page])}</span>
                {s.choice && <span className="block text-muted-foreground">→ {t(ACTION_LABELS[s.choice.kind])}{s.search_text ? `: “${s.search_text}”` : ""}</span>}
              </button>
            </li>
          ))}
        </ol>
      </div>
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-md border p-0.5 text-xs" role="group" aria-label={t("onPlayMode")}>
            <button type="button" aria-pressed={playing} onClick={() => setPlaying(true)}
              className={cn("inline-flex items-center gap-1 rounded px-2 py-0.5", playing ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
              <Play className="size-3.5" aria-hidden /> {t("onPlayVisit")}
            </button>
            <button type="button" aria-pressed={!playing} onClick={() => setPlaying(false)}
              className={cn("inline-flex items-center gap-1 rounded px-2 py-0.5", !playing ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
              <ListOrdered className="size-3.5" aria-hidden /> {t("onPlaySteps")}
            </button>
          </div>
          <a className="ml-auto inline-flex h-7 shrink-0 items-center gap-1 rounded-[0.7rem] border px-2 text-xs hover:bg-muted"
            href={journeyGifUrl(projectId, runId, view.variant, shopper.id)} download title={t("onReplayGifHint")}>
            <Film className="size-3.5" aria-hidden /> {t("onReplayGif")}
          </a>
        </div>
        {playing ? (
          <JourneyPlayer projectId={projectId} runId={runId} view={view} index={Math.min(index, session.steps.length - 1)} onIndex={setIndex}
            money={money} rival={rival} onRival={onRival} />
        ) : (
          <>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon-sm" disabled={index === 0} onClick={() => setIndex(index - 1)} aria-label={t("onPrevStep")}><ChevronLeft aria-hidden /></Button>
              <span className="text-xs tabular-nums">{t("onStepOf", { step: index + 1, total: session.steps.length })}</span>
              <Button variant="outline" size="icon-sm" disabled={index >= session.steps.length - 1} onClick={() => setIndex(index + 1)} aria-label={t("onNextStep")}><ChevronRight aria-hidden /></Button>
              <span className="min-w-0 flex-1 truncate font-mono text-[0.7rem] text-muted-foreground" title={step.url}>{step.url}</span>
            </div>
            {choice && (
              <div className="rounded-xl border bg-muted/40 p-2 text-xs">
                <div>
                  <span className="mr-1 rounded bg-rose-600 px-1.5 font-mono font-bold text-white">{choice.number}</span>
                  <span className="font-medium">{choice.label}</span>
                  {step.search_text && <span> — “{step.search_text}”</span>}
                  {choice.ad_id && <span className="ml-1 rounded bg-amber-500/20 px-1.5 text-[0.7rem] font-medium">{t("onStepAdClick")}</span>}
                </div>
                {step.thought && <p className="mt-1 italic">“{step.thought}”</p>}
                <p className="mt-1 text-muted-foreground">
                  {t("onStepTime", { seconds: formatDecimal(step.seconds, 1), load: formatDecimal(step.load_seconds, 1), options: step.options })}
                  {" · "}{t(step.source === "model" ? "onSourceModel" : step.source === "fallback" ? "onSourceFallback" : "onSourceRule")}
                  {step.ads.length > 0 && <>{" · "}{t("onStepAds", { count: step.ads.length })}</>}
                </p>
                {step.error && <p role="alert" className="mt-1 break-words text-destructive">{step.error}</p>}
              </div>
            )}
            <div className={cn("mx-auto overflow-hidden rounded-xl border bg-white", narrow ? "max-w-[430px]" : "max-w-[1024px]")}>
              <img src={stepScreenshotUrl(projectId, runId, view.variant, shopper.id, step.index)} alt={t("onScreenshotAlt", { title: step.url })}
                className="block w-full" onLoad={(e) => setNarrow(e.currentTarget.naturalWidth < 500)} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
