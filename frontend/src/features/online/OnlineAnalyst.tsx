// Ask about an online run: a model answers from the run's report (each store's funnel, money, friction, survey, ads,
// segments and the paired differences) and lists the report lines it used; lines not in the report are dropped.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownRight, CheckCircle2, DoorOpen, Loader2, RotateCcw, Scale, Send, Sparkles, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import * as api from "@/shared/api/client";
import { askOnlineAnalyst, clearOnlineAnalyst, getOnlineAnalyst, onlineKeys, suggestOnlineAnalystQuestions } from "@/shared/api/online";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import { useI18n } from "@/shared/i18n/i18n";
import { useAssistStore } from "@/stores/assistStore";
import type { MessageKey } from "@/shared/i18n/messages";

import { figureSection } from "./figureSections";

function showSection(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView?.({ behavior: "smooth", block: "start" });
  el.classList.remove("figure-flash");
  void el.offsetWidth;  // restart the highlight when the same section is shown again
  el.classList.add("figure-flash");
  window.setTimeout(() => el.classList.remove("figure-flash"), 1700);
}

export function OnlineAnalyst({ projectId, runId, compared }: { projectId: string; runId: string; compared: boolean }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const key = onlineKeys.analyst(projectId, runId);
  const thread = useQuery({ queryKey: key, queryFn: ({ signal }) => getOnlineAnalyst(projectId, runId, signal) });
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [text, setText] = useState("");
  const [model, setModel] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const list = useRef<HTMLDivElement>(null);
  // Follow the newest question inside the thread's own box; never scroll the page.
  const follow = () => requestAnimationFrame(() => { if (list.current) list.current.scrollTop = list.current.scrollHeight; });
  const ask = useMutation({
    mutationFn: (q: string) => askOnlineAnalyst(projectId, runId, q, model),
    onMutate: (q) => { setPending(q); setText(""); follow(); },
    onSuccess: async (next) => {
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData(key, next);
      follow();
    },
    onError: (_error, question) => setText((current) => current || question),
    onSettled: () => setPending(null),
  });
  const clear = useMutation({
    mutationFn: () => clearOnlineAnalyst(projectId, runId),
    onSuccess: async () => {
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData(key, { run_id: runId, model: "", messages: [] });
      ask.reset();
    },
  });
  // A question about the web shop typed in the command palette is asked as soon as the run is open.
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  const root = useRef<HTMLDivElement>(null);
  const queueAsk = useQueuedStart(ask.mutate);
  useEffect(() => {
    if (!pendingAsk) return;
    const routed = takeAsk(projectId, ["online_question"]);
    if (!routed) return;
    root.current?.scrollIntoView?.({ block: "center" });
    queueAsk(routed.text);
  }, [pendingAsk, projectId, takeAsk, queueAsk]);
  const busy = ask.isPending || clear.isPending;
  const messages = thread.data?.messages ?? [];
  const last = [...messages].reverse().find((m) => m.role === "analyst");
  const send = (q: string) => {
    const question = q.trim();
    if (Array.from(question).length >= 2 && !busy) { clear.reset(); ask.mutate(question); }
  };
  const builtIn: { icon: LucideIcon; text: MessageKey }[] = [
    compared ? { icon: Scale, text: "onAnalystStarterWinner" } : { icon: Sparkles, text: "onAnalystStarterFix" },
    { icon: DoorOpen, text: "onAnalystStarterLeave" },
    { icon: Users, text: "onAnalystStarterSegment" },
  ];
  // Starters read off this run (what stands out) replace the built-in ones once asked for.
  const ideas = useMutation({ mutationFn: () => suggestOnlineAnalystQuestions(projectId, runId, model) });
  const starters = ideas.data && ideas.data.length > 0
    ? ideas.data.map((text) => ({ icon: Sparkles, text }))
    : builtIn.map(({ icon, text }) => ({ icon, text: t(text) }));

  return (
    <div ref={root} className="flex flex-col gap-3">
      {thread.error && (
        <p role="alert" className="text-xs text-destructive">
          {thread.error.message}
          <button type="button" onClick={() => void thread.refetch()} disabled={thread.isFetching} className="ml-2 underline disabled:opacity-50">{t("analystRetry")}</button>
        </p>
      )}
      {messages.length === 0 && !pending ? (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">{t("onAnalystIntro")}</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {starters.map(({ icon: Icon, text: starter }) => (
              <button key={starter} type="button" onClick={() => send(starter)} disabled={busy}
                className="group flex items-start gap-2.5 rounded-2xl border bg-card/50 p-3 text-left text-xs leading-snug transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-[0_12px_30px_-18px_var(--heat-2)] disabled:opacity-50">
                <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground" aria-hidden>
                  <Icon className="size-3.5" />
                </span>
                {starter}
              </button>
            ))}
          </div>
          {!ideas.data && (
            <button type="button" onClick={() => ideas.mutate()} disabled={ideas.isPending}
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline disabled:opacity-60">
              {ideas.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Sparkles className="size-3.5" aria-hidden />}
              {ideas.isPending ? t("analystReading") : t("analystSuggest")}
            </button>
          )}
          {ideas.error && <p role="alert" className="text-xs text-destructive">{ideas.error.message}</p>}
        </div>
      ) : (
        <div ref={list} data-testid="online-analyst-thread" className="max-h-[32rem] space-y-3 overflow-y-auto overscroll-contain pr-1">
          {messages.map((m, i) => m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-[0.8rem] text-primary-foreground">{m.text}</p>
            </div>
          ) : (
            <div key={i} className="flex gap-2.5">
              <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full heat-gradient text-white shadow-[0_6px_18px_-6px_var(--heat-2)]" aria-hidden>
                <Sparkles className="size-3.5" />
              </span>
              <div className="min-w-0 max-w-[92%] space-y-2 rounded-2xl rounded-tl-md border bg-card px-3.5 py-2.5">
                <p className="text-[0.82rem] leading-relaxed">{m.text}</p>
                {m.figures.length > 0 && (
                  <ul className="space-y-1" aria-label={t("figuresUsed")}>
                    {m.figures.map((f) => {
                      const section = figureSection(f);
                      const body = (
                        <>
                          <CheckCircle2 className="mt-px size-3 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
                          <span className="num min-w-0 break-words">{f}</span>
                          {section && <ArrowDownRight className="mt-px ml-auto size-3 shrink-0 opacity-60" aria-hidden />}
                        </>
                      );
                      return (
                        <li key={f}>
                          {section ? (
                            <button type="button" onClick={() => showSection(section)} title={t("onAnalystShow")}
                              className="flex w-full items-start gap-1.5 rounded-lg bg-foreground/[0.04] px-2 py-1 text-left text-[0.68rem] leading-snug text-muted-foreground transition-colors hover:bg-primary/10 hover:text-foreground">
                              {body}
                            </button>
                          ) : (
                            <div className="flex items-start gap-1.5 rounded-lg bg-foreground/[0.04] px-2 py-1 text-[0.68rem] leading-snug text-muted-foreground">{body}</div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          ))}
          {pending && (
            <>
              <div className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-[0.8rem] text-primary-foreground opacity-80">{pending}</p>
              </div>
              <p className="flex items-center gap-1.5 pl-9 text-xs text-muted-foreground"><Loader2 className="size-3.5 animate-spin" aria-hidden /> {t("analystReading")}</p>
            </>
          )}
        </div>
      )}
      {ask.error && <p role="alert" className="text-xs text-destructive">{t("onAnalystFailed")} <span className="text-muted-foreground">{ask.error.message}</span></p>}
      {clear.error && <p role="alert" className="text-xs text-destructive">{clear.error.message}</p>}
      {last && !pending && last.follow_ups.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pl-9">
          {last.follow_ups.map((q) => (
            <button key={q} type="button" onClick={() => send(q)} disabled={busy}
              className="rounded-full border px-2.5 py-1 text-left text-[0.72rem] text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground disabled:opacity-50">{q}</button>
          ))}
        </div>
      )}
      <form className="flex items-center gap-1.5 rounded-2xl border bg-card/60 p-1.5 focus-within:ring-2 focus-within:ring-ring/40"
        onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(Array.from(e.target.value).slice(0, 600).join(""))} placeholder={t("onAnalystPlaceholder")}
          aria-label={t("analystQuestion")} className="h-9 min-w-0 flex-1 bg-transparent px-2 text-sm outline-none" />
        <button type="submit" disabled={Array.from(text.trim()).length < 2 || busy} aria-label={t("analystAsk")}
          className="grid size-9 place-items-center rounded-xl heat-gradient text-white transition-opacity disabled:opacity-40">
          {ask.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
        </button>
      </form>
      <div className="flex items-center gap-2 text-[0.72rem] text-muted-foreground">
        <select value={model} onChange={(e) => setModel(e.target.value)} className="h-7 min-w-0 max-w-[16rem] flex-1 rounded-lg border bg-card/60 px-1.5" aria-label={t("model")}>
          <option value="">{t("interviewAppModel")}</option>
          {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
        </select>
        {messages.length > 0 && (
          <button type="button" onClick={() => clear.mutate()} disabled={busy} className="ml-auto inline-flex items-center gap-1 hover:text-foreground disabled:opacity-50">
            <RotateCcw className="size-3" aria-hidden /> {t("analystClear")}
          </button>
        )}
      </div>
    </div>
  );
}
