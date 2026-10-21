// Interview a shopper after their trip. Answers come from the persona and the trip only and cite the steps
// they are about; hovering a citation highlights the step on the map and in the journey.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw, Send, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { askShopper, clearInterview, getInterview, interviewKeys, suggestQuestions, type Journey } from "@/shared/api/interview";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";

import { suggestedQuestions } from "./shopperStats";

export function InterviewChat({ projectId, runId, journey, onCite }: {
  projectId: string; runId: string; journey: Journey; onCite: (steps: number[] | null) => void;
}) {
  const sid = journey.persona.id;
  const qc = useQueryClient();
  const key = interviewKeys.interview(projectId, runId, sid);
  const transcript = useQuery({ queryKey: key, queryFn: ({ signal }) => getInterview(projectId, runId, sid, signal) });
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [text, setText] = useState("");
  const [model, setModel] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: (q: string) => askShopper(projectId, runId, sid, q, model),
    onMutate: (q) => { setPending(q); setText(""); },
    onSuccess: async (t) => {
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData(key, t);
    },
    onSettled: () => setPending(null),
  });
  const reset = useMutation({
    mutationFn: () => clearInterview(projectId, runId, sid),
    onSuccess: async () => {
      await qc.cancelQueries({ queryKey: key });
      await qc.invalidateQueries({ queryKey: key });
    },
  });
  const busy = ask.isPending || reset.isPending;
  const messages = transcript.data?.messages ?? [];
  const first = journey.persona.identity.split(/[,(]/)[0]?.trim() || "the shopper";
  // Next questions written by the model for this trip and this conversation; stored ones are reused until the
  // conversation moves on. Without a model (or on error) the trip-based templates stay.
  const stored = transcript.data?.suggested_after === messages.length ? transcript.data.suggestions ?? [] : [];
  const ideas = useQuery({
    queryKey: interviewKeys.suggestions(projectId, runId, sid, messages, model),
    queryFn: ({ signal }) => suggestQuestions(projectId, runId, sid, model, signal),
    enabled: transcript.isSuccess && !stored.length && !busy,
    staleTime: Infinity,
    retry: false,
  });
  const written = stored.length ? stored
    : ideas.data?.suggested_after === messages.length && JSON.stringify(ideas.data.messages) === JSON.stringify(messages)
      ? ideas.data.suggestions ?? [] : [];
  const chips = written.length ? written : messages.length === 0 || ideas.isError || ideas.isSuccess ? suggestedQuestions(journey) : [];

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length, pending]);

  const send = (q: string) => {
    const t = q.trim();
    if (t && !busy) ask.mutate(t);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="space-y-2">
        {messages.length === 0 && !pending && (
          <p className="rounded-xl bg-foreground/[0.035] px-3 py-2 text-[0.78rem] text-muted-foreground">
            Ask {first} about the trip. Answers come only from what this shopper saw and did, and point at the steps they mean.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={cn("flex", m.role === "interviewer" ? "justify-end" : "justify-start")}>
            <div
              onPointerEnter={() => m.steps.length && onCite(m.steps)}
              onPointerLeave={() => onCite(null)}
              className={cn("max-w-[88%] rounded-2xl px-3 py-2 text-[0.8rem] leading-snug",
                m.role === "interviewer" ? "rounded-br-md bg-primary text-primary-foreground" : "rounded-bl-md border bg-card")}
            >
              {m.text}
              {m.steps.length > 0 && (
                <span className="mt-1 flex flex-wrap gap-1">
                  {m.steps.map((s) => <span key={s} className="num rounded-full bg-foreground/[0.07] px-1.5 text-[0.65rem] text-muted-foreground">step {s}</span>)}
                </span>
              )}
            </div>
          </div>
        ))}
        {pending && (
          <>
            <div className="flex justify-end"><div className="max-w-[88%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-[0.8rem] text-primary-foreground opacity-80">{pending}</div></div>
            <div className="flex items-center gap-1.5 text-[0.75rem] text-muted-foreground"><Loader2 className="size-3.5 animate-spin" /> {first} is thinking…</div>
          </>
        )}
        {ask.error && <p className="text-[0.75rem] text-destructive">{ask.error.message}</p>}
        {reset.error && <p role="alert" className="text-[0.75rem] text-destructive">{reset.error.message}</p>}
        <div ref={end} />
      </div>
      {written.length > 0 && (
        <p className="flex items-center gap-1 text-[0.7rem] text-muted-foreground" aria-label="Written for this trip">
          <Sparkles className="size-3 text-primary/80" /> Follow-ups for this trip
        </p>
      )}
      <div className="-mt-0.5 flex flex-wrap items-center gap-1.5" aria-label="Suggested questions">
        {chips.map((q) => (
          <button key={q} type="button" onClick={() => send(q)} disabled={busy}
            className="rounded-full border px-2.5 py-1 text-left text-[0.72rem] text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground disabled:opacity-50">
            {q}
          </button>
        ))}
        {!written.length && ideas.isFetching && messages.length > 0 && (
          <span className="inline-flex items-center gap-1 text-[0.72rem] text-muted-foreground">
            <Loader2 className="size-3 animate-spin" /> Thinking of follow-ups…
          </span>
        )}
      </div>
      <form className="flex items-end gap-1.5" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, 600))}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }}
          rows={2}
          placeholder={`Ask ${first}…`}
          className="min-h-[2.6rem] flex-1 resize-none rounded-xl border bg-card/60 px-3 py-2 text-[0.8rem] outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        />
        <Button type="submit" size="sm" className="h-[2.6rem]" disabled={!text.trim() || busy} aria-label="Ask"><Send className="size-4" /></Button>
      </form>
      <div className="flex items-center gap-2 text-[0.72rem] text-muted-foreground">
        <select value={model} onChange={(e) => setModel(e.target.value)} className="h-7 min-w-0 flex-1 rounded-lg border bg-card/60 px-1.5" aria-label="Model">
          <option value="">App's text model</option>
          {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
        </select>
        {messages.length > 0 && (
          <button type="button" onClick={() => reset.mutate()} disabled={busy} className="inline-flex items-center gap-1 hover:text-foreground disabled:opacity-50"><RotateCcw className="size-3" /> Start over</button>
        )}
      </div>
    </div>
  );
}
