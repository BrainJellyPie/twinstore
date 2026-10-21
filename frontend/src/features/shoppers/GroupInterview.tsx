// Group interview: one question to many shoppers of the run (a segment or a random sample); each answers from
// their own trip, then the answers are coded into themes. Click an answer to open that shopper.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Trash2, UsersRound } from "lucide-react";

import * as api from "@/shared/api/client";
import { askGroup, deleteGroup, interviewKeys, listGroups, type GroupInterview, type GroupSegment } from "@/shared/api/interview";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";

const SEGMENTS: { id: GroupSegment; label: string; question: string }[] = [
  { id: "empty_handed", label: "Left empty-handed", question: "You looked around but left without buying. What would have made you buy something?" },
  { id: "impulse", label: "Impulse buyers", question: "You picked up something you hadn't planned. What made you grab it?" },
  { id: "top_spenders", label: "Top spenders", question: "What do you like about shopping here, and what would you change?" },
  { id: "buyers", label: "Buyers", question: "How did the prices feel to you on this trip?" },
  { id: "all", label: "Anyone", question: "If you could change one thing about this store, what would it be?" },
];

export function GroupInterviewPanel({ projectId, runId, currency, onOpen, onBack }: {
  projectId: string; runId: string; currency: string; onOpen: (sid: string) => void; onBack: () => void;
}) {
  const qc = useQueryClient();
  const groups = useQuery({ queryKey: interviewKeys.groups(projectId, runId), queryFn: ({ signal }) => listGroups(projectId, runId, signal) });
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [segment, setSegment] = useState<GroupSegment>("empty_handed");
  const [question, setQuestion] = useState(SEGMENTS[0]!.question);
  const [size, setSize] = useState(12);
  const [model, setModel] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const ask = useMutation({
    mutationFn: () => askGroup(projectId, runId, { question: question.trim(), segment, size, model }),
    onSuccess: async (g) => {
      setOpen(g.group_id);
      await qc.invalidateQueries({ queryKey: interviewKeys.groups(projectId, runId) });
    },
  });
  const del = useMutation({
    mutationFn: (gid: string) => deleteGroup(projectId, runId, gid),
    onSuccess: () => qc.invalidateQueries({ queryKey: interviewKeys.groups(projectId, runId) }),
  });
  const list = groups.data ?? [];
  const shown = list.find((g) => g.group_id === open) ?? null;

  return (
    <div className="space-y-3 py-3">
      <Button variant="ghost" size="sm" className="-ml-2" onClick={onBack}><ArrowLeft className="size-4" /> All shoppers</Button>
      <section className="space-y-2 rounded-2xl border bg-card p-3">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold"><UsersRound className="size-4 text-primary" /> Group interview</h3>
        <div className="flex flex-wrap gap-1">
          {SEGMENTS.map((s) => (
            <button key={s.id} type="button" onClick={() => { setSegment(s.id); setQuestion(s.question); }}
              className={cn("rounded-full border px-2.5 py-0.5 text-[0.72rem]", segment === s.id ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground hover:border-foreground/25")}>
              {s.label}
            </button>
          ))}
        </div>
        <textarea value={question} onChange={(e) => setQuestion(e.target.value.slice(0, 600))} rows={3}
          className="w-full resize-none rounded-xl border bg-card/60 px-3 py-2 text-[0.8rem] outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
        <div className="flex items-center gap-2 text-[0.72rem] text-muted-foreground">
          <span>Shoppers</span>
          <input type="range" min={4} max={40} step={1} value={size} onChange={(e) => setSize(Number(e.target.value))} className="flex-1" aria-label="Group size" />
          <span className="num w-6 text-right font-semibold text-foreground">{size}</span>
        </div>
        <div className="flex items-center gap-2">
          <select value={model} onChange={(e) => setModel(e.target.value)} className="h-8 min-w-0 flex-1 rounded-lg border bg-card/60 px-1.5 text-xs" aria-label="Model">
            <option value="">App's text model</option>
            {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
          </select>
          <Button size="sm" disabled={!question.trim() || ask.isPending} onClick={() => ask.mutate()}>
            {ask.isPending ? <Loader2 className="size-4 animate-spin" /> : <UsersRound className="size-4" />} Ask {size}
          </Button>
        </div>
        <p className="text-[0.68rem] text-muted-foreground">{size + 1} model calls: one answer per shopper from their own trip, then theme coding.</p>
        {ask.error && <p className="text-[0.75rem] text-destructive">{ask.error.message}</p>}
      </section>

      {shown && <GroupResult key={shown.group_id} group={shown} currency={currency} onOpen={onOpen} />}
      {del.error && <p role="alert" className="text-[0.75rem] text-destructive">{del.error.message}</p>}

      {list.length > 0 && (
        <section className="space-y-1">
          <h4 className="px-1 text-[0.72rem] font-semibold text-muted-foreground uppercase">Earlier questions</h4>
          {list.map((g) => (
            <div key={g.group_id} className={cn("group flex items-start gap-2 rounded-xl border px-2.5 py-2", g.group_id === open ? "border-primary bg-primary/[0.05]" : "bg-card/60")}>
              <button type="button" onClick={() => setOpen(g.group_id === open ? null : g.group_id)} className="min-w-0 flex-1 text-left">
                <span className="line-clamp-2 text-[0.78rem]">{g.question}</span>
                <span className="text-[0.68rem] text-muted-foreground">{g.answers.length} shoppers · {SEGMENTS.find((s) => s.id === g.segment)?.label} · {g.themes.length} themes</span>
              </button>
              <button type="button" onClick={() => del.mutate(g.group_id)} aria-label="Delete group interview"
                className="rounded p-1 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100"><Trash2 className="size-3.5" /></button>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function GroupResult({ group: g, currency, onOpen }: { group: GroupInterview; currency: string; onOpen: (sid: string) => void }) {
  const [theme, setTheme] = useState<number | null>(null);
  const answers = g.answers.filter((a) => a.answer && (theme === null || a.theme === theme));
  return (
    <section className="space-y-2.5 rounded-2xl border bg-card p-3">
      <p className="text-[0.8rem] font-medium">“{g.question}”</p>
      {g.themes.length > 0 && (
        <div className="space-y-1.5">
          {g.themes.map((t, i) => (
            <button key={t.label} type="button" onClick={() => setTheme(theme === i ? null : i)}
              className={cn("grid w-full grid-cols-[1fr_4.5rem] items-center gap-2 rounded-lg px-1 py-0.5 text-left", theme === i && "bg-primary/[0.07]")}>
              <span className="min-w-0">
                <span className="block truncate text-[0.76rem]">{t.label}</span>
                <span className="mt-0.5 block h-2 rounded-r-[4px] bg-foreground/[0.05]">
                  <span className="block h-full rounded-r-[4px]" style={{ width: `${Math.max(3, t.share * 100)}%`, background: "var(--viz-1)" }} />
                </span>
              </span>
              <span className="num text-right text-[0.74rem]"><b>{Math.round(t.share * 100)} %</b> <span className="text-muted-foreground">{t.count}</span></span>
            </button>
          ))}
        </div>
      )}
      <ul className="space-y-1.5">
        {answers.map((a) => (
          <li key={a.persona_id}>
            <button type="button" onClick={() => onOpen(a.persona_id)} className="w-full rounded-xl bg-foreground/[0.035] px-3 py-2 text-left transition-colors hover:bg-primary/[0.07]">
              <span className="block text-[0.78rem] leading-snug">{a.answer}</span>
              <span className="num mt-0.5 block text-[0.66rem] text-muted-foreground">
                {a.identity} · {a.age_group} · {a.units ? `${formatMoney(a.spent, currency)}, ${a.units} item${a.units === 1 ? "" : "s"}` : "bought nothing"}
                {a.theme >= 0 && g.themes[a.theme] ? ` · ${g.themes[a.theme]!.label}` : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {g.errors > 0 && <p className="text-[0.7rem] text-muted-foreground">{g.errors} shopper(s) could not answer (model errors).</p>}
      <p className="text-[0.68rem] text-muted-foreground">Answers are synthetic: each comes from one simulated trip. Use them to find hypotheses, then test them.</p>
    </section>
  );
}
