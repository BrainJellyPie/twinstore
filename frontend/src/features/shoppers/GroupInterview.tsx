// Group interview: one question to many shoppers of the run (a segment or a random sample); each answers from
// their own trip, then the answers are coded into themes. Click an answer to open that shopper.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Sparkles, Trash2, UsersRound } from "lucide-react";

import * as api from "@/shared/api/client";
import { askGroup, deleteGroup, interviewKeys, listGroups, suggestGroupQuestions, type GroupInterview, type GroupSegment } from "@/shared/api/interview";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { TestIdeas } from "@/features/assist/TestIdeas";
import { cn } from "@/shared/utils/cn";
import { formatMoney, formatPercent } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { personaLabel } from "@/shared/i18n/personaLabels";
import type { MessageKey } from "@/shared/i18n/messages";

const SEGMENTS: { id: GroupSegment; label: MessageKey; question: MessageKey }[] = [
  { id: "empty_handed", label: "shopperSortNothing", question: "groupAskEmptyHanded" },
  { id: "impulse", label: "groupImpulseBuyers", question: "groupAskImpulse" },
  { id: "top_spenders", label: "shopperSortSpent", question: "groupAskTopSpenders" },
  { id: "buyers", label: "groupBuyers", question: "groupAskBuyers" },
  { id: "all", label: "groupAnyone", question: "groupAskAnyone" },
];

const FOUND_QUESTION: MessageKey = "groupAskFound";

function segmentLabel(segment: GroupSegment, t: (key: MessageKey) => string): string {
  const label = SEGMENTS.find((s) => s.id === segment)?.label;
  return label ? t(label) : "";
}

export function GroupInterviewPanel({ projectId, runId, currency, preset, onOpen, onBack }: {
  projectId: string; runId: string; currency: string;
  /** Shoppers found from a description, offered as the group to ask (in their found order). */
  preset?: { label: string; personaIds: string[] };
  onOpen: (sid: string) => void; onBack: () => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const groups = useQuery({ queryKey: interviewKeys.groups(projectId, runId), queryFn: ({ signal }) => listGroups(projectId, runId, signal) });
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [segment, setSegment] = useState<GroupSegment | "found">(preset ? "found" : "empty_handed");
  const [question, setQuestion] = useState(() => t(preset ? FOUND_QUESTION : SEGMENTS[0]!.question));
  const presetMax = Math.min(40, preset?.personaIds.length ?? 40);
  const [size, setSize] = useState(Math.min(12, presetMax));
  const maxSize = segment === "found" ? presetMax : 40;
  const askedSize = Math.min(size, maxSize);
  const [model, setModel] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const ask = useMutation({
    mutationFn: () => askGroup(projectId, runId, segment === "found" && preset
      ? { question: question.trim(), segment: "all", size: askedSize, model, persona_ids: preset.personaIds.slice(0, askedSize) }
      : { question: question.trim(), segment: segment === "found" ? "all" : segment, size: askedSize, model }),
    onSuccess: async (g) => {
      setOpen(g.group_id);
      await qc.invalidateQueries({ queryKey: interviewKeys.groups(projectId, runId) });
    },
  });
  const ideas = useMutation({ mutationFn: () => suggestGroupQuestions(projectId, runId, model) });
  const del = useMutation({
    mutationFn: (gid: string) => deleteGroup(projectId, runId, gid),
    onSuccess: () => qc.invalidateQueries({ queryKey: interviewKeys.groups(projectId, runId) }),
  });
  // Every answer cost a model call: the first click asks, the second deletes; leaving the button cancels.
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const list = groups.data ?? [];
  const shown = list.find((g) => g.group_id === open) ?? null;

  return (
    <div className="space-y-3 py-3">
      <Button variant="ghost" size="sm" className="-ml-2" onClick={onBack}><ArrowLeft className="size-4" /> {t("allShoppers")}</Button>
      <section className="space-y-2 rounded-2xl border bg-card p-3">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold"><UsersRound className="size-4 text-primary" /> {t("groupInterview")}</h3>
        <div className="flex flex-wrap gap-1">
          {preset && (
            <button type="button" onClick={() => { setSegment("found"); setQuestion(t(FOUND_QUESTION)); }}
              className={cn("rounded-full border px-2.5 py-0.5 text-[0.72rem]", segment === "found" ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground hover:border-foreground/25")}>
              {preset.label} · {preset.personaIds.length}
            </button>
          )}
          {SEGMENTS.map((s) => (
            <button key={s.id} type="button" onClick={() => { setSegment(s.id); setQuestion(t(s.question)); }}
              className={cn("rounded-full border px-2.5 py-0.5 text-[0.72rem]", segment === s.id ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground hover:border-foreground/25")}>
              {t(s.label)}
            </button>
          ))}
        </div>
        <div className="space-y-1">
          <button type="button" onClick={() => ideas.mutate()} disabled={ideas.isPending}
            className="inline-flex items-center gap-1 text-[0.72rem] text-primary hover:underline disabled:opacity-60">
            {ideas.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
            {ideas.isPending ? t("analystReading") : t("analystSuggest")}
          </button>
          {ideas.data?.map((q) => (
            <button key={q.question} type="button" onClick={() => { setSegment(q.segment); setQuestion(q.question); }}
              className={cn("block w-full rounded-xl border px-2.5 py-1.5 text-left text-[0.74rem] transition-colors hover:border-primary/60",
                question === q.question && "border-primary bg-primary/[0.05]")}>
              <span className="block">{q.question}</span>
              <span className="block text-[0.66rem] text-muted-foreground">{segmentLabel(q.segment, t)}{q.why ? ` · ${q.why}` : ""}</span>
            </button>
          ))}
          {ideas.error && <p role="alert" className="text-[0.72rem] text-destructive">{ideas.error.message}</p>}
        </div>
        <textarea value={question} onChange={(e) => setQuestion(Array.from(e.target.value).slice(0, 600).join(""))} rows={3} aria-label={t("groupQuestion")}
          className="w-full resize-none rounded-xl border bg-card/60 px-3 py-2 text-[0.8rem] outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
        <div className="flex items-center gap-2 text-[0.72rem] text-muted-foreground">
          <span>{t("spShoppers")}</span>
          <input type="range" min={Math.min(4, maxSize)} max={maxSize} step={1} value={askedSize} onChange={(e) => setSize(Number(e.target.value))} className="flex-1" aria-label={t("groupSize")} />
          <span className="num w-6 text-right font-semibold text-foreground">{askedSize}</span>
        </div>
        <div className="flex items-center gap-2">
          <select value={model} onChange={(e) => setModel(e.target.value)} className="h-8 min-w-0 flex-1 rounded-lg border bg-card/60 px-1.5 text-xs" aria-label={t("model")}>
            <option value="">{t("interviewAppModel")}</option>
            {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
          </select>
          <Button size="sm" disabled={!question.trim() || ask.isPending} onClick={() => ask.mutate()}>
            {ask.isPending ? <Loader2 className="size-4 animate-spin" /> : <UsersRound className="size-4" />} {t("groupAsk", { count: askedSize })}
          </Button>
        </div>
        <p className="text-[0.68rem] text-muted-foreground">{t("groupCalls", { count: askedSize + 1 })}{segment === "found" ? ` ${t("groupFoundNote")}` : ""}</p>
        {ask.error && <p className="text-[0.75rem] text-destructive">{ask.error.message}</p>}
      </section>

      {shown && <GroupResult key={shown.group_id} group={shown} currency={currency} onOpen={onOpen} projectId={projectId} runId={runId} />}
      {del.error && <p role="alert" className="text-[0.75rem] text-destructive">{del.error.message}</p>}

      {list.length > 0 && (
        <section className="space-y-1">
          <h4 className="px-1 text-[0.72rem] font-semibold text-muted-foreground uppercase">{t("groupEarlier")}</h4>
          {list.map((g) => (
            <div key={g.group_id} className={cn("group flex items-start gap-2 rounded-xl border px-2.5 py-2", g.group_id === open ? "border-primary bg-primary/[0.05]" : "bg-card/60")}>
              <button type="button" onClick={() => setOpen(g.group_id === open ? null : g.group_id)} className="min-w-0 flex-1 text-left">
                <span className="line-clamp-2 text-[0.78rem]">{g.question}</span>
                <span className="text-[0.68rem] text-muted-foreground">{t("groupMeta", { count: g.answers.length, segment: segmentLabel(g.segment, t), themes: g.themes.length })}</span>
              </button>
              <button type="button" onClick={() => (confirmDelete === g.group_id ? del.mutate(g.group_id) : setConfirmDelete(g.group_id))}
                onBlur={() => setConfirmDelete(null)} disabled={del.isPending}
                aria-label={confirmDelete === g.group_id ? t("mkDeleteConfirm") : t("groupDelete")}
                className={cn("inline-flex shrink-0 items-center gap-1 rounded p-1 text-[0.68rem]", confirmDelete === g.group_id
                  ? "bg-destructive text-white" : "text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100")}>
                <Trash2 className="size-3.5" />{confirmDelete === g.group_id ? ` ${t("mkDeleteConfirm")}` : ""}
              </button>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function GroupResult({ group: g, currency, onOpen, projectId, runId }: {
  group: GroupInterview; currency: string; onOpen: (sid: string) => void; projectId: string; runId: string;
}) {
  const { t } = useI18n();
  const [theme, setTheme] = useState<number | null>(null);
  const answers = g.answers.filter((a) => a.answer && (theme === null || a.theme === theme));
  return (
    <section className="space-y-2.5 rounded-2xl border bg-card p-3">
      <p className="text-[0.8rem] font-medium">“{g.question}”</p>
      {g.themes.length > 0 && (
        <div className="space-y-1.5">
          {g.themes.map((item, i) => (
            <button key={item.label} type="button" onClick={() => setTheme(theme === i ? null : i)}
              className={cn("grid w-full grid-cols-[1fr_4.5rem] items-center gap-2 rounded-lg px-1 py-0.5 text-left", theme === i && "bg-primary/[0.07]")}>
              <span className="min-w-0">
                <span className="block truncate text-[0.76rem]">{item.label}</span>
                <span className="mt-0.5 block h-2 rounded-r-[4px] bg-foreground/[0.05]">
                  <span className="block h-full rounded-r-[4px]" style={{ width: `${Math.max(3, item.share * 100)}%`, background: "var(--viz-1)" }} />
                </span>
              </span>
              <span className="num text-right text-[0.74rem]"><b>{formatPercent(item.share, 0)}</b> <span className="text-muted-foreground">{item.count}</span></span>
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
                {a.identity} · {personaLabel(a.age_group, t)} · {a.units ? t(a.units === 1 ? "groupSpentOne" : "groupSpentMany", { amount: formatMoney(a.spent, currency), count: a.units }) : t("groupBoughtNothing")}
                {a.theme >= 0 && g.themes[a.theme] ? ` · ${g.themes[a.theme]!.label}` : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {g.errors > 0 && <p className="text-[0.7rem] text-muted-foreground">{t("groupErrors", { count: g.errors })}</p>}
      <p className="text-[0.68rem] text-muted-foreground">{t("groupSynthetic")}</p>
      {g.answers.some((a) => a.answer) && <TestIdeas projectId={projectId} runId={runId} source="group" groupId={g.group_id} />}
    </section>
  );
}
