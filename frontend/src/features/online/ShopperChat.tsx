// Ask an online shopper about their visit. A model answers in their voice from who they are and what they saw and
// did on the site only, and points at the steps it means; a step chip opens that page of the replay.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Send } from "lucide-react";

import * as api from "@/shared/api/client";
import {
  askOnlineShopper, clearShopperInterview, getShopperInterview, onlineKeys, type OnlineShopper, type SessionOutcome,
} from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { ModelWaiting } from "@/shared/components/ModelWaiting";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const OPENERS: Record<SessionOutcome, MessageKey> = {
  purchased: "onAskWhyBought", abandoned_cart: "onAskWhyCart", left: "onAskWhyLeft", bounced: "onAskWhyBounced",
  timed_out: "onAskWhyTimedOut", step_limit: "onAskWhyLeft",
};

export function ShopperChat({ projectId, runId, variant, shopper, outcome, onStep }: {
  projectId: string; runId: string; variant: number; shopper: OnlineShopper; outcome: SessionOutcome;
  onStep: (step: number) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const key = onlineKeys.interview(projectId, runId, variant, shopper.id);
  const transcript = useQuery({ queryKey: key, queryFn: ({ signal }) => getShopperInterview(projectId, runId, variant, shopper.id, signal) });
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [text, setText] = useState("");
  const [model, setModel] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const ask = useMutation({
    mutationFn: (q: string) => askOnlineShopper(projectId, runId, variant, shopper.id, q, model),
    onMutate: (q) => { setPending(q); setText(""); },
    onSuccess: async (thread) => {
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData(key, thread);
    },
    onError: (_error, question) => setText((current) => current || question),
    onSettled: () => setPending(null),
  });
  const reset = useMutation({
    mutationFn: () => clearShopperInterview(projectId, runId, variant, shopper.id),
    onSuccess: async () => {
      await qc.cancelQueries({ queryKey: key });
      await qc.invalidateQueries({ queryKey: key });
    },
  });
  const busy = ask.isPending || reset.isPending;
  const messages = transcript.data?.messages ?? [];
  const name = shopper.identity.split(/[,(]/)[0]?.trim() || shopper.identity;
  const ideas = [t(OPENERS[outcome]), t("onAskEasier"), t("onAskNoticed")];
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [messages.length, pending]);
  const send = (q: string) => {
    const question = q.trim();
    if (question && !busy) ask.mutate(question);
  };

  return (
    <div className="flex flex-col gap-2 text-xs">
      {messages.length === 0 && !pending && (
        <p className="rounded-xl bg-foreground/[0.035] px-3 py-2 text-muted-foreground">{t("onAskIntro", { name })}</p>
      )}
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {messages.map((m, i) => (
          <div key={i} className={cn("flex", m.role === "interviewer" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[90%] rounded-2xl px-3 py-2 leading-snug",
              m.role === "interviewer" ? "rounded-br-md bg-primary text-primary-foreground" : "rounded-bl-md border bg-card")}>
              {m.text}
              {m.steps.length > 0 && (
                <span className="mt-1 flex flex-wrap gap-1">
                  {m.steps.map((s) => (
                    <button key={s} type="button" onClick={() => onStep(s - 1)}
                      className="rounded-full bg-foreground/[0.07] px-1.5 text-[0.7rem] text-muted-foreground hover:text-foreground">
                      {t("interviewStep", { step: s })}
                    </button>
                  ))}
                </span>
              )}
            </div>
          </div>
        ))}
        {pending && (
          <>
            <div className="flex justify-end"><div className="max-w-[90%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-primary-foreground opacity-80">{pending}</div></div>
            <div className="text-muted-foreground"><ModelWaiting label={t("interviewThinking", { name })} /></div>
          </>
        )}
        <div ref={end} />
      </div>
      {ask.error && <p role="alert" className="text-destructive">{t("onAskFailed")} <span className="text-muted-foreground">{ask.error.message}</span></p>}
      {reset.error && <p role="alert" className="text-destructive">{reset.error.message}</p>}
      {messages.length === 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label={t("interviewSuggested")}>
          {ideas.map((q) => (
            <button key={q} type="button" onClick={() => send(q)} disabled={busy}
              className="rounded-full border px-2.5 py-1 text-left text-muted-foreground hover:border-primary/60 hover:text-foreground disabled:opacity-50">{q}</button>
          ))}
        </div>
      )}
      <form className="flex items-end gap-1.5" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <textarea value={text} rows={2} aria-label={t("interviewAskPlaceholder", { name })}
          onChange={(e) => setText(Array.from(e.target.value).slice(0, 600).join(""))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) {
              e.preventDefault(); send(text);
            }
          }}
          placeholder={t("interviewAskPlaceholder", { name })}
          className="min-h-[2.6rem] flex-1 resize-none rounded-xl border bg-card/60 px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
        <Button type="submit" size="sm" className="h-[2.6rem]" disabled={!text.trim() || busy} aria-label={t("analystAsk")}><Send className="size-4" aria-hidden /></Button>
      </form>
      <div className="flex items-center gap-2 text-[0.72rem] text-muted-foreground">
        <select value={model} onChange={(e) => setModel(e.target.value)} className="h-7 min-w-0 flex-1 rounded-lg border bg-card/60 px-1.5" aria-label={t("model")}>
          <option value="">{t("interviewAppModel")}</option>
          {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
        </select>
        {messages.length > 0 && (
          <button type="button" onClick={() => reset.mutate()} disabled={busy} className="inline-flex items-center gap-1 hover:text-foreground disabled:opacity-50">
            <RotateCcw className="size-3" aria-hidden /> {t("interviewStartOver")}
          </button>
        )}
      </div>
    </div>
  );
}
