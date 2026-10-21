// A model's reading of a finished study: the reasons respondents gave, coded into themes (split by arm for paired
// studies), and a short commentary on the numbers. Written on request, kept with the study, labelled as model-written
// here and in the print-ready report.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Sparkles, X } from "lucide-react";

import * as api from "@/shared/api/client";
import {
  deleteStudyReading,
  getStudyReading,
  studyReadingKey,
  writeStudyReading,
  type ReasonTheme,
  type StudyPath,
  type StudyReading as Reading,
} from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";

const GROUP_TONE = ["bg-primary", "bg-primary/35"];

type StudyReadingProps = {
  projectId: string; study: StudyPath; jobId: string;
  /** Open answers the study collected; the panel explains what it will read. */
  answers: number;
};

export function StudyReading(props: StudyReadingProps) {
  return <StudyReadingContent key={JSON.stringify([props.projectId, props.study, props.jobId])} {...props} />;
}

function StudyReadingContent({ projectId, study, jobId, answers }: StudyReadingProps) {
  const qc = useQueryClient();
  const key = studyReadingKey(projectId, study, jobId);
  const reading = useQuery({ queryKey: key, queryFn: ({ signal }) => getStudyReading(projectId, study, jobId, signal) });
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [model, setModel] = useState("");
  const write = useMutation({
    mutationFn: () => writeStudyReading(projectId, study, jobId, model),
    onSuccess: async (r) => {
      await qc.cancelQueries({ queryKey: key, exact: true });
      qc.setQueryData(key, r);
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteStudyReading(projectId, study, jobId),
    onSuccess: async () => {
      await qc.cancelQueries({ queryKey: key, exact: true });
      qc.setQueryData(key, null);
    },
  });
  const r = reading.data;
  const busy = write.isPending || remove.isPending;
  const loadError = reading.error ? (
    <div role="alert" className="space-y-2 rounded-xl border border-destructive/30 p-3 text-sm [overflow-wrap:anywhere]">
      <p>Could not load the saved reading. {reading.error.message}</p>
      <Button size="sm" variant="outline" disabled={reading.isFetching} onClick={() => void reading.refetch()}>
        Retry loading reading
      </Button>
    </div>
  ) : null;

  const picker = (
    <select value={model} onChange={(e) => setModel(e.target.value)} disabled={busy}
      className="h-8 max-w-[11rem] rounded-lg border bg-card/60 px-1.5 text-xs" aria-label="Model for the reading">
      <option value="">App's text model</option>
      {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
    </select>
  );

  if (reading.isPending) return null;
  if (!r && loadError) return loadError;
  if (!r) {
    return (
      <section className="flex flex-wrap items-center gap-2 rounded-2xl border border-dashed bg-card/60 px-4 py-3">
        <Sparkles className="size-4 text-primary" aria-hidden />
        <p className="mr-auto min-w-[14rem] flex-1 text-sm">
          <b>Read the answers</b>{" "}
          <span className="text-muted-foreground">
            {answers >= 4
              ? `A model groups the ${answers} reasons respondents gave into themes and writes a commentary on the results.`
              : "A model writes a commentary on the results."}
          </span>
        </p>
        {picker}
        <Button size="sm" onClick={() => write.mutate()} disabled={busy}>
          {write.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
          {write.isPending ? "Reading…" : "Read the answers"}
        </Button>
        {write.error && <p role="alert" className="basis-full text-xs text-destructive">{write.error.message}</p>}
      </section>
    );
  }

  return (
    <section className="rounded-2xl border bg-card p-4" aria-label="Model's reading">
      {loadError}
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="mr-auto flex items-center gap-1.5 text-sm font-semibold">
          <Sparkles className="size-4 text-primary" aria-hidden /> What the answers say
          <span className="font-normal text-muted-foreground">· written by {models.find((m) => m.ref === r.model)?.label ?? (r.model.split(/[:/]/).pop() || "a model")}</span>
        </h3>
        {picker}
        <Button size="sm" variant="outline" onClick={() => write.mutate()} disabled={busy} title="Write the reading again with the chosen model">
          {write.isPending ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} Rewrite
        </Button>
        <Button size="sm" variant="ghost" onClick={() => remove.mutate()} disabled={busy} aria-label="Remove the reading"><X className="size-4" /></Button>
      </header>
      {(write.error || remove.error) && <p role="alert" className="mb-2 text-xs text-destructive">{(write.error ?? remove.error)?.message}</p>}
      <div className={cn("grid gap-5", r.themes.length > 0 && "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]")}>
        <div className="max-w-[68ch] space-y-2 text-sm leading-relaxed">
          <p className="font-medium">{r.summary}</p>
          {r.interpretation && <p className="text-foreground/85">{r.interpretation}</p>}
          {r.next_steps && <p className="text-foreground/85"><span className="text-muted-foreground">Next: </span>{r.next_steps}</p>}
        </div>
        {r.themes.length > 0 && <Themes reading={r} />}
      </div>
    </section>
  );
}

function Themes({ reading }: { reading: Reading }) {
  const groups = reading.groups;
  const totals = Object.fromEntries(groups.map((g) => [g, reading.themes.reduce((n, t) => n + (t.by_group[g] ?? 0), 0)]));
  return (
    <div className="min-w-0">
      <p className="mb-2 text-xs text-muted-foreground">
        Why they answered that way · {reading.answers_coded} reasons grouped by theme
      </p>
      {groups.length > 1 && (
        <p className="mb-2 flex flex-wrap gap-3 text-[0.7rem] text-muted-foreground">
          {groups.map((g, i) => (
            <span key={g} className="inline-flex items-center gap-1"><span className={cn("size-2 rounded-sm", GROUP_TONE[i] ?? "bg-foreground/30")} />{g}</span>
          ))}
          <span>· share of each arm's reasons</span>
        </p>
      )}
      <ul className="space-y-2.5">
        {reading.themes.map((t) => <ThemeRow key={t.label} theme={t} groups={groups} totals={totals} />)}
      </ul>
    </div>
  );
}

function ThemeRow({ theme, groups, totals }: { theme: ReasonTheme; groups: string[]; totals: Record<string, number> }) {
  const split = groups.length > 1;
  return (
    <li>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium">{theme.label}</span>
        <span className="num shrink-0 text-xs text-muted-foreground">{theme.count} · {Math.round(theme.share * 100)} %</span>
      </div>
      {split ? (
        <div className="mt-1 space-y-0.5">
          {groups.map((g, i) => {
            const share = totals[g] ? (theme.by_group[g] ?? 0) / totals[g] : 0;
            return (
              <div key={g} className="flex items-center gap-2" title={`${g}: ${theme.by_group[g] ?? 0} of ${totals[g]} reasons`}>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-foreground/[0.06]">
                  <div className={cn("h-full rounded-full", GROUP_TONE[i] ?? "bg-foreground/30")} style={{ width: `${share * 100}%` }} />
                </div>
                <span className="num w-9 text-right text-[0.68rem] text-muted-foreground">{Math.round(share * 100)} %</span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-foreground/[0.06]">
          <div className="h-full rounded-full bg-primary" style={{ width: `${theme.share * 100}%` }} />
        </div>
      )}
      {theme.examples.length > 0 && (
        <p className="mt-1 text-xs italic text-muted-foreground">{theme.examples.map((x) => `“${x}”`).join("  ")}</p>
      )}
    </li>
  );
}
