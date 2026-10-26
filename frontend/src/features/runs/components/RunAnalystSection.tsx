// Ask about this run: questions answered by a model from the run's own numbers (totals, hours, shelves,
// products, shopper groups), each answer listing the figures it rests on.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessageSquareText, RotateCcw, Send, Sparkles } from "lucide-react";

import { analystKey, askAnalyst, clearAnalyst, getAnalyst, suggestAnalystQuestions } from "@/shared/api/interview";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { TestIdeas } from "@/features/assist/TestIdeas";
import { cn } from "@/shared/utils/cn";
import { useAssistStore } from "@/stores/assistStore";
import { ModelWaiting } from "@/shared/components/ModelWaiting";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { NeedsModel } from "@/features/settings/NeedsModel";

const STARTERS: MessageKey[] = ["analystStarterShelf", "analystStarterBusy", "analystStarterSpenders"];

export function RunAnalystSection({ projectId, runId }: { projectId: string; runId: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const key = analystKey(projectId, runId);
  const thread = useQuery({ queryKey: key, queryFn: ({ signal }) => getAnalyst(projectId, runId, signal) });
  const [text, setText] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const ask = useMutation({
    mutationFn: (q: string) => askAnalyst(projectId, runId, q),
    onMutate: (q) => { setPending(q); setText(""); },
    onSuccess: async (thread) => {
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData(key, thread);
    },
    onError: (_error, question) => setText((current) => current || question),
    onSettled: () => setPending(null),
  });
  const clear = useMutation({
    mutationFn: () => clearAnalyst(projectId, runId),
    onSuccess: async () => {
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData(key, { run_id: runId, model: "", messages: [] });
      ask.reset();
    },
  });
  // A question typed in the command palette and routed here is asked as soon as the run is open.
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  const section = useRef<HTMLElement>(null);
  const queueAsk = useQueuedStart(ask.mutate);
  useEffect(() => {
    if (!pendingAsk) return;
    const routed = takeAsk(projectId, ["run_question"]);
    if (!routed) return;
    section.current?.scrollIntoView?.({ block: "start" });
    queueAsk(routed.text);
  }, [pendingAsk, projectId, takeAsk, queueAsk]);
  const messages = thread.data?.messages ?? [];
  const last = [...messages].reverse().find((m) => m.role === "analyst");
  // Starters read off this run (what stands out) replace the generic ones once asked for.
  const ideas = useMutation({ mutationFn: () => suggestAnalystQuestions(projectId, runId) });
  const starters = ideas.data && ideas.data.length > 0 ? ideas.data : STARTERS.map((starter) => t(starter));
  const suggestions = last ? last.follow_ups : messages.length === 0 ? starters : [];
  const busy = ask.isPending || clear.isPending;
  const send = (q: string) => { const question = q.trim(); if (Array.from(question).length >= 2 && !busy) { clear.reset(); ask.mutate(question); } };
  // Follow a new question or answer inside the thread's own scroll box; never scroll the page,
  // which on a phone would jump past the store as soon as the panel mounts.
  const seen = useRef<{ count: number; pending: string | null } | null>(null);
  useEffect(() => {
    if (!thread.isFetched) return;
    const previous = seen.current;
    seen.current = { count: messages.length, pending };
    // The stored thread as first loaded sets the baseline; only later additions scroll.
    if (!previous || !list.current) return;
    if (messages.length > previous.count || (pending !== null && pending !== previous.pending)) {
      list.current.scrollTop = list.current.scrollHeight;
    }
  }, [messages.length, pending, thread.isFetched]);

  return (
    <section ref={section} className="border-t px-3 py-3" aria-label={t("analystTitle")}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-xs font-medium"><MessageSquareText className="size-3.5 text-primary" aria-hidden /> {t("analystTitle")}</h3>
        {messages.length > 0 && (
          <button type="button" onClick={() => clear.mutate()} disabled={busy} className="inline-flex items-center gap-1 text-[0.7rem] text-muted-foreground hover:text-foreground disabled:opacity-50">
            <RotateCcw className="size-3" /> {t("analystClear")}
          </button>
        )}
      </div>
      {thread.error && (
        <div role="alert" className="mb-2 text-[0.72rem] text-destructive">
          {thread.error.message}
          <button type="button" onClick={() => void thread.refetch()} disabled={thread.isFetching}
            className="ml-2 underline disabled:opacity-50">{t("analystRetry")}</button>
        </div>
      )}
      <div ref={list} data-testid="analyst-thread" className="max-h-[28rem] space-y-2 overflow-y-auto overscroll-contain">
        {messages.map((m, i) => m.role === "user" ? (
          <p key={i} className="ml-6 rounded-2xl rounded-br-md bg-primary px-3 py-1.5 text-[0.78rem] text-primary-foreground">{m.text}</p>
        ) : (
          <div key={i} className="mr-2 space-y-1 rounded-2xl rounded-bl-md border bg-card px-3 py-2">
            <p className="text-[0.78rem] leading-snug">{m.text}</p>
            {m.figures.length > 0 && (
              <ul className="space-y-0.5 border-l-2 border-primary/30 pl-2" aria-label={t("figuresUsed")}>
                {m.figures.map((f) => <li key={f} className="num text-[0.68rem] text-muted-foreground">{f}</li>)}
              </ul>
            )}
          </div>
        ))}
        {pending && (
          <>
            <p className="ml-6 rounded-2xl rounded-br-md bg-primary px-3 py-1.5 text-[0.78rem] text-primary-foreground opacity-80">{pending}</p>
            <p className="text-[0.72rem] text-muted-foreground"><ModelWaiting label={t("analystReading")} /></p>
          </>
        )}
        {(ask.error || clear.error) && <p role="alert" className="text-[0.72rem] text-destructive">{(ask.error ?? clear.error)?.message}</p>}
      </div>
      {messages.length === 0 && !pending && !ideas.data && (
        <button type="button" onClick={() => ideas.mutate()} disabled={ideas.isPending}
          className="mt-2 inline-flex items-center gap-1 text-[0.7rem] text-primary hover:underline disabled:opacity-60">
          {ideas.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
          {ideas.isPending ? t("analystReading") : t("analystSuggest")}
        </button>
      )}
      {ideas.error && <p role="alert" className="mt-1 text-[0.7rem] text-destructive">{ideas.error.message}</p>}
      {last && !pending && <div className="mt-2"><TestIdeas key={JSON.stringify(last)} projectId={projectId} runId={runId} source="analyst" /></div>}
      {suggestions.length > 0 && !pending && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((q) => (
            <button key={q} type="button" onClick={() => send(q)} disabled={busy}
              className="rounded-full border px-2.5 py-1 text-left text-[0.7rem] text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground disabled:opacity-50">
              {q}
            </button>
          ))}
        </div>
      )}
      <div className="mt-2"><NeedsModel purpose="assist" /></div>
      <form className="mt-2 flex items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(Array.from(e.target.value).slice(0, 600).join(""))} placeholder={t("analystPlaceholder")}
          aria-label={t("analystQuestion")}
          className={cn("h-8 min-w-0 flex-1 rounded-lg border bg-card/60 px-2.5 text-[0.78rem] outline-none focus-visible:ring-2 focus-visible:ring-ring/40")} />
        <button type="submit" disabled={Array.from(text.trim()).length < 2 || busy} aria-label={t("analystAsk")}
          className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground disabled:opacity-50">
          {ask.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
        </button>
      </form>
    </section>
  );
}
