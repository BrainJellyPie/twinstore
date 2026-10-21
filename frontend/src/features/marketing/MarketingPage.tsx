// Marketing studio: A/B tests of price, promotion, placement and packaging on the store's twin, concept tests with
// synthetic respondents, and the product image library both use.

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, FlaskConical, Images, Loader2, Plus, Trash2, TriangleAlert } from "lucide-react";

import * as api from "@/shared/api/client";
import {
  deleteExperiment,
  deleteSurvey,
  getExperiment,
  getMarketingInfo,
  getSurvey,
  listExperiments,
  listSurveys,
  marketingKeys,
  type JobStatus,
} from "@/shared/api/marketing";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";

import { ExperimentBuilder } from "./ExperimentBuilder";
import { ExperimentReportView } from "./ExperimentReport";
import { usePackages } from "./hooks";
import { ProductLibrary } from "./ProductLibrary";
import { storeProducts } from "./products";
import { SurveyBuilder } from "./SurveyBuilder";
import { SurveyReportView } from "./SurveyReport";

type Tab = "ab" | "survey" | "products";

const TABS: { id: Tab; label: string; icon: typeof FlaskConical; blurb: string }[] = [
  { id: "ab", label: "A/B tests", icon: FlaskConical, blurb: "Price, discount, promotion, placement and packaging on the same shoppers" },
  { id: "survey", label: "Concept tests", icon: ClipboardList, blurb: "Synthetic respondents rate packs, prices and preference" },
  { id: "products", label: "Products", icon: Images, blurb: "Package images, brands and the shelf products they show" },
];

const busy = (s: JobStatus["status"]) => s === "pending" || s === "running";

export function MarketingPage({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<Tab>("ab");
  const [selected, setSelected] = useState<Record<"ab" | "survey", string | null>>({ ab: null, survey: null });
  const project = useQuery({ queryKey: queryKeys.project(projectId), queryFn: ({ signal }) => api.getProject(projectId, signal) });
  const setups = project.data?.setups ?? [];
  const [setupId, setSetupId] = useState("");
  const activeSetup = setupId || project.data?.state.activeSetupId || setups[0]?.id || "";
  const setup = useQuery({
    queryKey: queryKeys.setup(projectId, activeSetup),
    queryFn: ({ signal }) => api.getSetup(projectId, activeSetup, signal),
    enabled: !!activeSetup,
  });
  const products = useMemo(() => storeProducts(setup.data?.store), [setup.data?.store]);
  const info = useQuery({ queryKey: marketingKeys.info(projectId), queryFn: ({ signal }) => getMarketingInfo(projectId, signal), staleTime: 60_000 });
  const currency = info.data?.currency ?? "USD";
  const packages = usePackages(projectId).data ?? [];

  const experiments = useQuery({
    queryKey: marketingKeys.experiments(projectId),
    queryFn: ({ signal }) => listExperiments(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some((j) => busy(j.status)) ? 1500 : false),
  });
  const surveys = useQuery({
    queryKey: marketingKeys.surveys(projectId),
    queryFn: ({ signal }) => listSurveys(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some((j) => busy(j.status)) ? 1500 : false),
  });
  const jobs = useMemo(() => (tab === "ab" ? experiments.data ?? [] : tab === "survey" ? surveys.data ?? [] : []), [tab, experiments.data, surveys.data]);
  const current = tab === "products" ? null : selected[tab];
  const select = (id: string | null) => tab !== "products" && setSelected((s) => ({ ...s, [tab]: id }));

  useEffect(() => {
    if (tab === "products" || selected[tab] !== null || !jobs.length) return;
    // Open the latest test on first visit; "New test" sets the selection to "" afterwards.
    setSelected((s) => ({ ...s, [tab]: jobs[0]!.job_id }));
  }, [tab, jobs, selected]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-[1.7rem] leading-tight tracking-[-0.04em]">Marketing <span className="font-accent aurora-text">studio</span></h1>
          <p className="text-sm text-muted-foreground">{TABS.find((t) => t.id === tab)!.blurb}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Layout
            <select value={activeSetup} onChange={(e) => setSetupId(e.target.value)} className="h-9 rounded-xl border bg-card/60 px-2.5 text-sm text-foreground">
              {setups.map((s) => <option key={s.id} value={s.id}>{s.name || s.id}</option>)}
            </select>
          </label>
          <div className="flex rounded-xl bg-foreground/[0.055] p-1" role="tablist">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                className={cn("inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  tab === id ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>
                <Icon className="size-4" /> {label}
                {id === "products" && packages.length > 0 && <span className="num rounded-full bg-foreground/[0.08] px-1.5 text-[0.68rem]">{packages.length}</span>}
              </button>
            ))}
          </div>
        </div>
      </header>

      {tab === "products" ? (
        <div className="min-h-0 flex-1 overflow-y-auto pr-1"><ProductLibrary projectId={projectId} products={products} /></div>
      ) : (
        <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[17rem_minmax(0,1fr)]">
          <aside className="flex min-h-0 flex-col gap-2 overflow-y-auto">
            <button type="button" onClick={() => select("")}
              className={cn("flex items-center gap-2 rounded-2xl border-2 border-dashed px-3 py-3 text-sm transition-colors",
                current === "" ? "border-primary text-foreground" : "border-foreground/15 text-muted-foreground hover:border-primary/60 hover:text-foreground")}>
              <Plus className="size-4" /> New {tab === "ab" ? "A/B test" : "concept test"}
            </button>
            {jobs.map((j) => <JobItem key={j.job_id} projectId={projectId} job={j} active={current === j.job_id} onSelect={() => select(j.job_id)} onDeleted={() => select("")} />)}
          </aside>
          <main className="min-h-0 overflow-y-auto pr-1">
            {tab === "ab" && (current ? <ExperimentJob projectId={projectId} id={current} setups={setups} /> : setup.data?.store ? (
              <ExperimentBuilder key={activeSetup} projectId={projectId} setupId={activeSetup} products={products} store={setup.data.store} currency={currency}
                onStarted={(j) => select(j.job_id)} />
            ) : <Loading />)}
            {tab === "survey" && (current ? <SurveyJob projectId={projectId} id={current} /> : (
              <SurveyBuilder projectId={projectId} personaCount={project.data?.personas.length ?? 0} onStarted={(j) => select(j.job_id)} />
            ))}
          </main>
        </div>
      )}
    </div>
  );
}

function Loading() {
  return <div className="grid h-40 place-items-center text-sm text-muted-foreground"><Loader2 className="size-5 animate-spin" /></div>;
}

function JobItem({ projectId, job, active, onSelect, onDeleted }: { projectId: string; job: JobStatus; active: boolean; onSelect: () => void; onDeleted: () => void }) {
  const qc = useQueryClient();
  const del = useMutation({
    mutationFn: () => (job.kind === "experiment" ? deleteExperiment(projectId, job.job_id) : deleteSurvey(projectId, job.job_id)),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: job.kind === "experiment" ? marketingKeys.experiments(projectId) : marketingKeys.surveys(projectId) });
      if (active) onDeleted();
    },
  });
  const when = job.created_at ? new Date(job.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  return (
    <div className={cn("group relative rounded-2xl border px-3 py-2.5 transition-colors", active ? "border-primary bg-primary/[0.06]" : "bg-card/60 hover:border-foreground/20")}>
      <button type="button" onClick={onSelect} className="block w-full text-left">
        <span className="block truncate pr-6 text-sm font-medium">{job.name || job.job_id}</span>
        <span className="flex items-center gap-1.5 text-[0.7rem] text-muted-foreground">
          {busy(job.status) ? <><Loader2 className="size-3 animate-spin" /> {Math.round(job.progress * 100)} % · {job.stage}</>
            : job.status === "failed" ? <><TriangleAlert className="size-3 text-destructive" /> failed</> : when}
        </span>
        {busy(job.status) && <span className="mt-1.5 block h-1 overflow-hidden rounded-full bg-foreground/[0.08]"><span className="block h-full bg-primary transition-[width]" style={{ width: `${Math.max(4, job.progress * 100)}%` }} /></span>}
      </button>
      {!busy(job.status) && <button type="button" onClick={() => del.mutate()} aria-label={`Delete ${job.name}`}
        className="absolute top-2 right-2 rounded-md p-1 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100">
        <Trash2 className="size-3.5" />
      </button>}
    </div>
  );
}

function JobState({ job }: { job: JobStatus }) {
  if (job.status === "failed") return <p className="rounded-2xl border tone-bad px-4 py-3 text-sm">{job.error || "The job failed."}</p>;
  return (
    <div className="grid h-56 place-items-center rounded-2xl border bg-card/60">
      <div className="w-72 space-y-2 text-center">
        <Loader2 className="mx-auto size-6 animate-spin text-primary" />
        <p className="text-sm font-medium">{job.name}</p>
        <p className="text-xs text-muted-foreground">{job.stage || "queued"} · {Math.round(job.progress * 100)} %</p>
        <span className="block h-1.5 overflow-hidden rounded-full bg-foreground/[0.08]"><span className="block h-full bg-primary transition-[width]" style={{ width: `${Math.max(4, job.progress * 100)}%` }} /></span>
      </div>
    </div>
  );
}

function ExperimentJob({ projectId, id, setups }: { projectId: string; id: string; setups: api.SetupSummary[] }) {
  const view = useQuery({
    queryKey: marketingKeys.experiment(projectId, id),
    queryFn: ({ signal }) => getExperiment(projectId, id, signal),
    refetchInterval: (q) => (q.state.data && !busy(q.state.data.status) ? false : 1200),
  });
  if (!view.data) return view.error ? <p className="text-sm text-destructive">{view.error.message}</p> : <Loading />;
  const report = view.data.report;
  return report ? <ExperimentReportView report={report} layoutName={setups.find((s) => s.id === report.setup_id)?.name} /> : <JobState job={view.data} />;
}

function SurveyJob({ projectId, id }: { projectId: string; id: string }) {
  const view = useQuery({
    queryKey: marketingKeys.survey(projectId, id),
    queryFn: ({ signal }) => getSurvey(projectId, id, signal),
    refetchInterval: (q) => (q.state.data && !busy(q.state.data.status) ? false : 1500),
  });
  if (!view.data) return view.error ? <p className="text-sm text-destructive">{view.error.message}</p> : <Loading />;
  return view.data.report ? <SurveyReportView projectId={projectId} report={view.data.report} /> : <JobState job={view.data} />;
}
