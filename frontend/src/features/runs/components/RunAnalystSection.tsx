// Ask about this run: questions answered by a model from the run's own numbers (totals, hours, shelves,
// products, shopper groups), each answer listing the figures it rests on.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessageSquareText, RotateCcw, Send } from "lucide-react";

import { analystKey, askAnalyst, clearAnalyst, getAnalyst } from "@/shared/api/interview";
import { cn } from "@/shared/utils/cn";

const STARTERS = ["Which shelf converts worst, and why might that be?", "When is the store busiest, and does spend follow?",
  "Which shoppers spend the most per visit?"];

export function RunAnalystSection({ projectId, runId }: { projectId: string; runId: string }) {
  const qc = useQueryClient();
  const key = analystKey(projectId, runId);
  const thread = useQuery({ queryKey: key, queryFn: ({ signal }) => getAnalyst(projectId, runId, signal) });
  const [text, setText] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const ask = useMutation({
    mutationFn: (q: string) => askAnalyst(projectId, runId, q),
    onMutate: (q) => { setPending(q); setText(""); },
    onSuccess: async (t) => {
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData(key, t);
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
  const messages = thread.data?.messages ?? [];
  const last = [...messages].reverse().find((m) => m.role === "analyst");
  const suggestions = last ? last.follow_ups : messages.length === 0 ? STARTERS : [];
  const busy = ask.isPending || clear.isPending;
  const send = (q: string) => { const t = q.trim(); if (Array.from(t).length >= 2 && !busy) { clear.reset(); ask.mutate(t); } };
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [messages.length, pending]);

  return (
    <section className="border-t px-3 py-3" aria-label="Ask about this run">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-xs font-medium"><MessageSquareText className="size-3.5 text-primary" aria-hidden /> Ask about this run</h3>
        {messages.length > 0 && (
          <button type="button" onClick={() => clear.mutate()} disabled={busy} className="inline-flex items-center gap-1 text-[0.7rem] text-muted-foreground hover:text-foreground disabled:opacity-50">
            <RotateCcw className="size-3" /> Clear
          </button>
        )}
      </div>
      {thread.error && (
        <div role="alert" className="mb-2 text-[0.72rem] text-destructive">
          {thread.error.message}
          <button type="button" onClick={() => void thread.refetch()} disabled={thread.isFetching}
            className="ml-2 underline disabled:opacity-50">Retry</button>
        </div>
      )}
      <div className="space-y-2">
        {messages.map((m, i) => m.role === "user" ? (
          <p key={i} className="ml-6 rounded-2xl rounded-br-md bg-primary px-3 py-1.5 text-[0.78rem] text-primary-foreground">{m.text}</p>
        ) : (
          <div key={i} className="mr-2 space-y-1 rounded-2xl rounded-bl-md border bg-card px-3 py-2">
            <p className="text-[0.78rem] leading-snug">{m.text}</p>
            {m.figures.length > 0 && (
              <ul className="space-y-0.5 border-l-2 border-primary/30 pl-2" aria-label="Figures used">
                {m.figures.map((f) => <li key={f} className="num text-[0.68rem] text-muted-foreground">{f}</li>)}
              </ul>
            )}
          </div>
        ))}
        {pending && (
          <>
            <p className="ml-6 rounded-2xl rounded-br-md bg-primary px-3 py-1.5 text-[0.78rem] text-primary-foreground opacity-80">{pending}</p>
            <p className="flex items-center gap-1.5 text-[0.72rem] text-muted-foreground"><Loader2 className="size-3 animate-spin" /> Reading the run…</p>
          </>
        )}
        {(ask.error || clear.error) && <p role="alert" className="text-[0.72rem] text-destructive">{(ask.error ?? clear.error)?.message}</p>}
        <div ref={end} />
      </div>
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
      <form className="mt-2 flex items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(Array.from(e.target.value).slice(0, 600).join(""))} placeholder="e.g. Why does the ice cream freezer sell so little?"
          aria-label="Question about this run"
          className={cn("h-8 min-w-0 flex-1 rounded-lg border bg-card/60 px-2.5 text-[0.78rem] outline-none focus-visible:ring-2 focus-visible:ring-ring/40")} />
        <button type="submit" disabled={Array.from(text.trim()).length < 2 || busy} aria-label="Ask"
          className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground disabled:opacity-50">
          {ask.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
        </button>
      </form>
    </section>
  );
}
