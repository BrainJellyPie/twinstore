// Marketing studio: A/B tests of price, promotion, placement and packaging on the store's twin, concept tests with
// synthetic respondents, and the product image library both use.

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Copy, FlaskConical, Grid3x3, Images, Loader2, MessagesSquare, Plus, Rows3, Trash2, TriangleAlert } from "lucide-react";

import * as api from "@/shared/api/client";
import {
  deleteConjoint,
  deleteExperiment,
  deleteSurvey,
  deletePitch,
  getPitch,
  listPitches,
  getConjoint,
  getExperiment,
  getMarketingInfo,
  getShelfTest,
  listShelfTests,
  deleteShelfTest,
  getSurvey,
  listConjoints,
  listExperiments,
  listSurveys,
  marketingKeys,
  type ConjointRequest,
  type ExperimentRequest,
  type JobStatus,
  type ShelfTestRequest,
  type SurveyRequest,
} from "@/shared/api/marketing";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { useAssistStore } from "@/stores/assistStore";

import { ConjointBuilder } from "./ConjointBuilder";
import { ConjointReportView } from "./ConjointReport";
import { ExperimentBuilder } from "./ExperimentBuilder";
import { ExperimentReportView } from "./ExperimentReport";
import { usePackages } from "./hooks";
import { ProductLibrary } from "./ProductLibrary";
import { storeProducts } from "./products";
import { ShelfTestBuilder, ShelfTestReportView } from "./ShelfTest";
import { SurveyBuilder } from "./SurveyBuilder";
import { SurveyReportView } from "./SurveyReport";
import { Protocols } from "./Protocols";
import { PriceChecks } from "./PriceChecks";
import { UnitPrices } from "./UnitPrices";
import { InventoryReview } from "./InventoryReview";
import { FieldPilots } from "./FieldPilots";
import { StaffPitchBuilder } from "./StaffPitchBuilder";
import { StaffPitchReportView } from "./StaffPitchReport";

type Tab = "ab" | "shelf" | "survey" | "conjoint" | "pitch" | "pilot" | "products" | "inventory" | "prices" | "protocols" | "priceChecks";
type JobTab = "ab" | "shelf" | "survey" | "conjoint" | "pitch";

const TABS: { id: Tab; label: string; icon: typeof FlaskConical; blurb: string }[] = [
  { id: "ab", label: "A/B tests", icon: FlaskConical, blurb: "Price, discount, promotion, placement and packaging on the same shoppers" },
  { id: "shelf", label: "Shelf tests", icon: Rows3, blurb: "A new pack, price or sign on the shelf: pick share and stand-out on the same respondents" },
  { id: "survey", label: "Concept tests", icon: ClipboardList, blurb: "Synthetic respondents rate packs, prices and preference" },
  { id: "conjoint", label: "Conjoint", icon: Grid3x3, blurb: "Which features and prices win the choice: part-worths, willingness to pay and a market simulator" },
  { id: "pitch", label: "Staff scripts", icon: MessagesSquare, blurb: "Compare wording with paired intent, trust and pressure ratings" },
  { id: "pilot", label: "Field pilots", icon: ClipboardList, blurb: "Preassigned staff/shift experiments and observed purchase conversion" },
  { id: "protocols", label: "Protocols", icon: ClipboardList, blurb: "Record original research plans and explain later amendments" },
  { id: "priceChecks", label: "Price checks", icon: ClipboardList, blurb: "Reconcile observed shelf labels and checkout prices with explicit exclusions" },
  { id: "prices", label: "Unit prices", icon: ClipboardList, blurb: "Compare observed competitor offers by pack quantity, date and eligibility" },
  { id: "inventory", label: "Inventory", icon: ClipboardList, blurb: "Reconcile observed stock and review period margin, turnover and net unit sell-through" },
  { id: "products", label: "Products", icon: Images, blurb: "Package images, brands and the shelf products they show" },
];

const busy = (s: JobStatus["status"]) => s === "pending" || s === "running";

export function MarketingPage({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<Tab>("ab");
  const [selected, setSelected] = useState<Record<JobTab, string | null>>({ ab: null, shelf: null, survey: null, conjoint: null, pitch: null });
  // A request routed here from the command palette opens the right builder and drafts from the same words.
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  const [prefill, setPrefill] = useState<{ tab: "ab" | "shelf" | "conjoint" | "survey" | "pitch"; text: string; id: number } | null>(null);
  useEffect(() => {
    if (!pendingAsk) return;
    const ask = takeAsk(projectId, ["ab_test", "shelf_test", "conjoint", "concept_test", "staff_script"]);
    if (!ask) return;
    const tabs = { ab_test: "ab", shelf_test: "shelf", conjoint: "conjoint", concept_test: "survey", staff_script: "pitch" } as const;
    const target = tabs[ask.destination as keyof typeof tabs];
    setTab(target);
    setSelected((s) => ({ ...s, [target]: "" }));
    setPrefill({ tab: target, text: ask.text, id: ask.id });
  }, [pendingAsk, projectId, takeAsk]);
  const project = useQuery({ queryKey: queryKeys.project(projectId), queryFn: ({ signal }) => api.getProject(projectId, signal) });
  const setups = project.data?.setups ?? [];
  const [setupId, setSetupId] = useState("");
  const activeSetup = [setupId, project.data?.state.activeSetupId]
    .find((id) => setups.some((candidate) => candidate.id === id)) ?? setups[0]?.id ?? "";
  const setup = useQuery({
    queryKey: queryKeys.setup(projectId, activeSetup),
    queryFn: ({ signal }) => api.getSetup(projectId, activeSetup, signal),
    enabled: !!activeSetup,
  });
  const products = useMemo(() => storeProducts(setup.data?.store), [setup.data?.store]);
  const info = useQuery({ queryKey: marketingKeys.info(projectId), queryFn: ({ signal }) => getMarketingInfo(projectId, signal), staleTime: 60_000 });
  const budgetCurrency = project.data?.metadata.currency ?? info.data?.currency ?? "USD";
  const currency = setup.data?.store?.currency ?? budgetCurrency;
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
  const pitches = useQuery({
    queryKey: marketingKeys.pitches(projectId),
    queryFn: ({ signal }) => listPitches(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some((j) => busy(j.status)) ? 1500 : false),
  });
  const shelfTests = useQuery({
    queryKey: marketingKeys.shelfTests(projectId),
    queryFn: ({ signal }) => listShelfTests(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some((j) => busy(j.status)) ? 1500 : false),
  });
  const conjoints = useQuery({
    queryKey: marketingKeys.conjoints(projectId),
    queryFn: ({ signal }) => listConjoints(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some((j) => busy(j.status)) ? 1500 : false),
  });
  const jobs = useMemo(() => (tab === "ab" ? experiments.data ?? [] : tab === "shelf" ? shelfTests.data ?? [] : tab === "survey" ? surveys.data ?? []
    : tab === "conjoint" ? conjoints.data ?? [] : tab === "pitch" ? pitches.data ?? [] : []),
  [tab, experiments.data, shelfTests.data, surveys.data, conjoints.data, pitches.data]);
  const current = (tab === "products" || tab === "pilot" || tab === "inventory" || tab === "prices" || tab === "protocols" || tab === "priceChecks") ? null : selected[tab];
  const select = (id: string | null) => tab !== "products" && tab !== "pilot" && tab !== "inventory" && tab !== "prices" && tab !== "protocols" && tab !== "priceChecks" && setSelected((s) => ({ ...s, [tab]: id }));
  // "Duplicate and edit": the builder opens pre-filled with a finished test's request.
  const [abDraft, setAbDraft] = useState<{ key: number; req: ExperimentRequest } | null>(null);
  const [surveyDraft, setSurveyDraft] = useState<{ key: number; req: SurveyRequest } | null>(null);
  const duplicateExperiment = (req: ExperimentRequest) => {
    if (setups.some((s) => s.id === req.setup_id)) setSetupId(req.setup_id);
    setAbDraft({ key: Date.now(), req });
    select("");
  };
  const [shelfDraft, setShelfDraft] = useState<{ key: number; req: ShelfTestRequest } | null>(null);
  const duplicateShelf = (req: ShelfTestRequest) => {
    if (setups.some((s) => s.id === req.setup_id)) setSetupId(req.setup_id);
    setShelfDraft({ key: Date.now(), req });
    select("");
  };
  const [conjointDraft, setConjointDraft] = useState<{ key: number; req: ConjointRequest } | null>(null);
  const duplicateConjoint = (req: ConjointRequest) => {
    setConjointDraft({ key: Date.now(), req });
    select("");
  };
  const duplicateSurvey = (req: SurveyRequest) => {
    setSurveyDraft({ key: Date.now(), req });
    select("");
  };

  useEffect(() => {
    if (tab === "products" || tab === "pilot" || tab === "inventory" || tab === "prices" || tab === "protocols" || tab === "priceChecks" || selected[tab] !== null || !jobs.length) return;
    // Open the latest test on first visit; "New test" sets the selection to "" afterwards.
    setSelected((s) => ({ ...s, [tab]: jobs[0]!.job_id }));
  }, [tab, jobs, selected]);

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-3">
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
          <div className="flex flex-wrap rounded-xl bg-foreground/[0.055] p-1" role="tablist">
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

      {tab === "priceChecks" ? <div className="min-h-64 flex-1 overflow-y-auto pr-1"><PriceChecks key={projectId} projectId={projectId} /></div> : tab === "protocols" ? <div className="min-h-64 flex-1 overflow-y-auto pr-1"><Protocols key={projectId} projectId={projectId} /></div> : tab === "prices" ? <div className="min-h-64 flex-1 overflow-y-auto pr-1"><UnitPrices key={projectId} projectId={projectId} /></div> : tab === "inventory" ? <div className="min-h-64 flex-1 overflow-y-auto pr-1"><InventoryReview key={projectId} projectId={projectId} /></div> : tab === "pilot" ? <div className="min-h-64 flex-1 overflow-y-auto pr-1"><FieldPilots projectId={projectId} /></div> : tab === "products" ? (
        <div className="min-h-64 flex-1 overflow-y-auto pr-1"><ProductLibrary projectId={projectId} products={products} setupId={activeSetup} /></div>
      ) : (
        <div className="grid min-h-64 flex-1 gap-3 lg:grid-cols-[17rem_minmax(0,1fr)]">
          <aside className="flex min-h-0 flex-col gap-2 overflow-y-auto">
            <button type="button" onClick={() => select("")}
              className={cn("flex items-center gap-2 rounded-2xl border-2 border-dashed px-3 py-3 text-sm transition-colors",
                current === "" ? "border-primary text-foreground" : "border-foreground/15 text-muted-foreground hover:border-primary/60 hover:text-foreground")}>
              <Plus className="size-4" /> New {tab === "ab" ? "A/B test" : tab === "shelf" ? "shelf test" : tab === "pitch" ? "staff script test" : tab === "conjoint" ? "conjoint study" : "concept test"}
            </button>
            {jobs.map((j) => <JobItem key={j.job_id} projectId={projectId} job={j} active={current === j.job_id} onSelect={() => select(j.job_id)} onDeleted={() => select("")} />)}
          </aside>
          <main className="min-h-0 overflow-y-auto pr-1">
            {tab === "ab" && (current ? <ExperimentJob projectId={projectId} id={current} setups={setups} onDuplicate={duplicateExperiment} /> : setup.data?.store ? (
              <ExperimentBuilder key={`${activeSetup}:${abDraft?.key ?? 0}`} projectId={projectId} setupId={activeSetup} products={products}
                store={setup.data.store} currency={currency} initial={abDraft?.req} prefill={prefill?.tab === "ab" ? prefill : undefined}
                onStarted={(j) => { setAbDraft(null); select(j.job_id); }} />
            ) : <Loading />)}
            {tab === "shelf" && (current ? <ShelfJob projectId={projectId} id={current} onDuplicate={duplicateShelf} /> : setup.data?.store ? (
              <ShelfTestBuilder key={`${activeSetup}:${shelfDraft?.key ?? 0}`} projectId={projectId} setupId={activeSetup} store={setup.data.store}
                currency={currency} initial={shelfDraft?.req} prefill={prefill?.tab === "shelf" ? prefill : undefined}
                onStarted={(j) => { setShelfDraft(null); select(j.job_id); }} />
            ) : <Loading />)}
            {tab === "survey" && (current ? <SurveyJob projectId={projectId} id={current} onDuplicate={duplicateSurvey} /> : (
              <SurveyBuilder key={`${surveyDraft?.key ?? 0}:${budgetCurrency}`} projectId={projectId} personaCount={project.data?.personas.length ?? 0}
                defaultCurrency={budgetCurrency} initial={surveyDraft?.req} setupId={activeSetup || undefined}
                prefill={prefill?.tab === "survey" ? prefill : undefined}
                onStarted={(j) => { setSurveyDraft(null); select(j.job_id); }} />
            ))}
            {tab === "conjoint" && (current ? <ConjointJob projectId={projectId} id={current} onDuplicate={duplicateConjoint} /> : (
              <ConjointBuilder key={`${conjointDraft?.key ?? 0}:${budgetCurrency}`} projectId={projectId} personaCount={project.data?.personas.length ?? 0}
                defaultCurrency={budgetCurrency} initial={conjointDraft?.req} setupId={currency === budgetCurrency ? activeSetup : undefined}
                prefill={prefill?.tab === "conjoint" ? prefill : undefined}
                onStarted={(j) => { setConjointDraft(null); select(j.job_id); }} />
            ))}
            {tab === "pitch" && (current ? <PitchJob projectId={projectId} id={current} /> : setup.data?.store ? (
              <StaffPitchBuilder key={activeSetup} projectId={projectId} setupId={activeSetup} products={products} currency={currency}
                prefill={prefill?.tab === "pitch" ? prefill : undefined}
                personaCount={project.data?.personas.length ?? 0} onStarted={(j) => select(j.job_id)} />
            ) : <Loading />)}
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
    mutationFn: () => (job.kind === "experiment" ? deleteExperiment(projectId, job.job_id) : job.kind === "pitch" ? deletePitch(projectId, job.job_id)
      : job.kind === "shelf" ? deleteShelfTest(projectId, job.job_id) : job.kind === "conjoint" ? deleteConjoint(projectId, job.job_id)
        : deleteSurvey(projectId, job.job_id)),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: job.kind === "experiment" ? marketingKeys.experiments(projectId) : job.kind === "pitch" ? marketingKeys.pitches(projectId)
        : job.kind === "shelf" ? marketingKeys.shelfTests(projectId) : job.kind === "conjoint" ? marketingKeys.conjoints(projectId)
          : marketingKeys.surveys(projectId) });
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

function DuplicateBar({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <div className="mb-2 flex justify-end">
      <button type="button" onClick={onClick}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-foreground/[0.05] hover:text-foreground">
        <Copy className="size-3.5" /> {label}
      </button>
    </div>
  );
}

function ExperimentJob({ projectId, id, setups, onDuplicate }: {
  projectId: string; id: string; setups: api.SetupSummary[]; onDuplicate: (req: ExperimentRequest) => void;
}) {
  const view = useQuery({
    queryKey: marketingKeys.experiment(projectId, id),
    queryFn: ({ signal }) => getExperiment(projectId, id, signal),
    refetchInterval: (q) => (q.state.data && !busy(q.state.data.status) ? false : 1200),
  });
  if (!view.data) return view.error ? <p className="text-sm text-destructive">{view.error.message}</p> : <Loading />;
  const report = view.data.report;
  const request = view.data.request;
  return (
    <>
      {request && <DuplicateBar label="Duplicate and edit" onClick={() => onDuplicate(request)} />}
      {report ? <ExperimentReportView projectId={projectId} report={report} layoutName={setups.find((s) => s.id === report.setup_id)?.name} /> : <JobState job={view.data} />}
    </>
  );
}

function SurveyJob({ projectId, id, onDuplicate }: { projectId: string; id: string; onDuplicate: (req: SurveyRequest) => void }) {
  const view = useQuery({
    queryKey: marketingKeys.survey(projectId, id),
    queryFn: ({ signal }) => getSurvey(projectId, id, signal),
    refetchInterval: (q) => (q.state.data && !busy(q.state.data.status) ? false : 1500),
  });
  if (!view.data) return view.error ? <p className="text-sm text-destructive">{view.error.message}</p> : <Loading />;
  const request = view.data.request;
  return (
    <>
      {request && <DuplicateBar label="Duplicate and edit" onClick={() => onDuplicate(request)} />}
      {view.data.report ? <SurveyReportView projectId={projectId} report={view.data.report} /> : <JobState job={view.data} />}
    </>
  );
}

function ShelfJob({ projectId, id, onDuplicate }: { projectId: string; id: string; onDuplicate: (req: ShelfTestRequest) => void }) {
  const view = useQuery({
    queryKey: marketingKeys.shelfTest(projectId, id),
    queryFn: ({ signal }) => getShelfTest(projectId, id, signal),
    refetchInterval: (q) => (q.state.data && !busy(q.state.data.status) ? false : 1500),
  });
  if (!view.data) return view.error ? <p className="text-sm text-destructive">{view.error.message}</p> : <Loading />;
  const request = view.data.request;
  return (
    <>
      {request && <DuplicateBar label="Duplicate and edit" onClick={() => onDuplicate(request)} />}
      {view.data.report ? <ShelfTestReportView projectId={projectId} report={view.data.report} /> : <JobState job={view.data} />}
    </>
  );
}

function ConjointJob({ projectId, id, onDuplicate }: { projectId: string; id: string; onDuplicate: (req: ConjointRequest) => void }) {
  const view = useQuery({
    queryKey: marketingKeys.conjoint(projectId, id),
    queryFn: ({ signal }) => getConjoint(projectId, id, signal),
    refetchInterval: (q) => (q.state.data && !busy(q.state.data.status) ? false : 1500),
  });
  if (!view.data) return view.error ? <p className="text-sm text-destructive">{view.error.message}</p> : <Loading />;
  const request = view.data.request;
  return (
    <>
      {request && <DuplicateBar label="Duplicate and edit" onClick={() => onDuplicate(request)} />}
      {view.data.report ? <ConjointReportView projectId={projectId} report={view.data.report} /> : <JobState job={view.data} />}
    </>
  );
}

function PitchJob({ projectId, id }: { projectId: string; id: string }) {
  const view = useQuery({
    queryKey: marketingKeys.pitch(projectId, id),
    queryFn: ({ signal }) => getPitch(projectId, id, signal),
    refetchInterval: (q) => (q.state.data && !busy(q.state.data.status) ? false : 1500),
  });
  if (!view.data) return view.error ? <p className="text-sm text-destructive">{view.error.message}</p> : <Loading />;
  return view.data.report ? <div className="space-y-4"><StaffPitchReportView projectId={projectId} report={view.data.report} /><FieldPilots projectId={projectId} source={view.data.report} /></div> : <JobState job={view.data} />;
}
