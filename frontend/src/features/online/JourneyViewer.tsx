// One shopper's visit, step by step: the page they saw (drawn again exactly as it was, with the same badge
// numbers), the option they picked and what they thought.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { getSession, onlineKeys, stepScreenshotUrl, type SessionView } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { cn } from "@/shared/utils/cn";
import { currencyCode, formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { personaLabel } from "@/shared/i18n/personaLabels";

import { ACTION_LABELS, DEVICE_LABELS, FUNNEL_LABELS, MISSION_LABELS, OUTCOME_LABELS, PAGE_LABELS, VISION_LABELS } from "./labels";

export function JourneyViewer({ projectId, runId, variant, shopperId, variants, currency, onVariant, onClose }: {
  projectId: string; runId: string; variant: number; shopperId: string; variants: string[]; currency: string;
  onVariant: (variant: number) => void; onClose: () => void;
}) {
  const { t } = useI18n();
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
        {variants.length > 1 && (
          <div className="inline-flex flex-wrap rounded-md border p-0.5 text-xs" role="group" aria-label={t("onRunStores")}>
            {variants.map((name, i) => (
              <button key={i} type="button" aria-pressed={variant === i} onClick={() => onVariant(i)}
                className={cn("rounded px-2 py-0.5", variant === i ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>{name}</button>
            ))}
          </div>
        )}
        {session.isPending && <p className="text-sm text-muted-foreground">{t("studioLoading")}</p>}
        {session.isError && <p role="alert" className="text-sm text-destructive">{session.error.message}</p>}
        {session.data && <Journey key={`${variant}:${shopperId}`} projectId={projectId} runId={runId} view={session.data} currency={currency} />}
      </DialogContent>
    </Dialog>
  );
}

function Journey({ projectId, runId, view, currency }: { projectId: string; runId: string; view: SessionView; currency: string }) {
  const { t } = useI18n();
  const { shopper, session } = view;
  const [index, setIndex] = useState(0);
  const [narrow, setNarrow] = useState(shopper.device === "mobile");
  const step = session.steps[Math.min(index, session.steps.length - 1)];
  const code = currencyCode(currency);
  const money = (x: number) => formatMoney(x, code);
  if (!step) return null;
  const choice = step.choice;
  return (
    <div className="grid gap-4 text-sm lg:grid-cols-[300px_minmax(0,1fr)]">
      <div className="space-y-3">
        <div className="rounded-xl border p-3 text-xs">
          <div className="font-semibold">{shopper.identity}</div>
          <div className="text-muted-foreground">
            {personaLabel(shopper.age_group, t)} · {personaLabel(shopper.gender, t)} · {t(DEVICE_LABELS[shopper.device])}
            {shopper.vision !== "typical" ? ` · ${t(VISION_LABELS[shopper.vision])}` : ""}
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
        <ol className="max-h-[50vh] space-y-1 overflow-y-auto">
          {session.steps.map((s, i) => (
            <li key={s.index}>
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
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-sm" disabled={index === 0} onClick={() => setIndex(index - 1)} aria-label={t("onPrevStep")}><ChevronLeft aria-hidden /></Button>
          <span className="text-xs tabular-nums">{t("onStepOf", { step: index + 1, total: session.steps.length })}</span>
          <Button variant="outline" size="icon-sm" disabled={index >= session.steps.length - 1} onClick={() => setIndex(index + 1)} aria-label={t("onNextStep")}><ChevronRight aria-hidden /></Button>
          <span className="truncate font-mono text-[0.7rem] text-muted-foreground" title={step.url}>{step.url}</span>
        </div>
        {choice && (
          <div className="rounded-xl border bg-muted/40 p-2 text-xs">
            <div>
              <span className="mr-1 rounded bg-rose-600 px-1.5 font-mono font-bold text-white">{choice.number}</span>
              <span className="font-medium">{choice.label}</span>
              {step.search_text && <span> — “{step.search_text}”</span>}
            </div>
            {step.thought && <p className="mt-1 italic">“{step.thought}”</p>}
            <p className="mt-1 text-muted-foreground">
              {t("onStepTime", { seconds: step.seconds.toFixed(1), load: step.load_seconds.toFixed(1), options: step.options })}
              {" · "}{t(step.source === "model" ? "onSourceModel" : step.source === "fallback" ? "onSourceFallback" : "onSourceRule")}
            </p>
            {step.error && <p className="mt-1 break-words text-destructive">{step.error}</p>}
          </div>
        )}
        <div className={cn("mx-auto overflow-hidden rounded-xl border bg-white", narrow ? "max-w-[430px]" : "max-w-[1024px]")}>
          <img src={stepScreenshotUrl(projectId, runId, view.variant, shopper.id, step.index)} alt={t("onScreenshotAlt", { title: step.url })}
            className="block w-full" onLoad={(e) => setNarrow(e.currentTarget.naturalWidth < 500)} />
        </div>
      </div>
    </div>
  );
}
