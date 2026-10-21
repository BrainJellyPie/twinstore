// Marketing studio API: A/B tests on a layout and survey-style concept tests. Mirrors
// backend domain/marketing.py — keep in sync. Prices are integers in the currency's minor unit.

import { BASE, type MetricComparison } from "./client";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let detail = body;
    try { detail = (JSON.parse(body) as { detail?: string }).detail ?? body; } catch { /* plain text */ }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return (res.status === 204 ? undefined : res.json()) as Promise<T>;
}

export type ChangeKind = "price" | "discount" | "promo" | "move" | "package" | "category_price";
export type ExperimentEngine = "rule" | "vlm";
export type JobState = "pending" | "running" | "completed" | "failed";

export interface VariantChange {
  kind: ChangeKind;
  sku?: string;
  price?: number | null;
  percent?: number | null;
  promo?: string;
  rack_id?: string;
  face?: "N" | "S" | "E" | "W" | null;
  level?: number | null;
  asset_id?: string;
  category?: string;
  charm?: boolean;
  /** price: shoppers keep the current price as the usual one (reference price). */
  keep_reference?: boolean;
}

export interface Variant { name: string; changes: VariantChange[] }

export interface ExperimentRequest {
  setup_id: string;
  name?: string;
  variants: Variant[];
  focus_skus: string[];
  engine: ExperimentEngine;
  model?: string;
  panel: number;
  seed?: number;
}

export interface FocusOutcome {
  sku: string;
  name: string;
  metric: "units" | "spend" | "buyers";
  control: number;
  variant: number;
  diff: number;
  rel_diff: number;
  ci_low: number;
  ci_high: number;
  prob_better: number;
}

export interface SkuSales { sku: string; name: string; units: number; revenue: number; buyers: number }

export interface VariantResult {
  name: string;
  applied: string[];
  warnings: string[];
  revenue_per_visitor: number;
  conversion: number;
  units_per_visitor: number;
  vs_control: MetricComparison[];
  focus: FocusOutcome[];
  top_skus: SkuSales[];
  prices?: Record<string, number>;
}

export interface PricePoint { arm: string; price: number; units: number; units_low: number; units_high: number; revenue: number }
export interface PriceResponse { sku: string; name: string; points: PricePoint[]; elasticity: number | null; best_price: number | null }

export interface ExperimentReport {
  experiment_id: string;
  name: string;
  setup_id: string;
  engine: ExperimentEngine;
  model: string;
  panel_size: number;
  currency: string;
  visitors_per_day: number;
  focus_skus: string[];
  control: VariantResult;
  variants: VariantResult[];
  winner: string;
  price_response?: PriceResponse | null;
  notes: string[];
  seconds: number;
}

export interface JobStatus {
  job_id: string;
  kind: "experiment" | "survey";
  name: string;
  status: JobState;
  stage: string;
  progress: number;
  error: string;
  created_at: string;
  finished_at: string;
}

export interface ExperimentView extends JobStatus { report: ExperimentReport | null; request?: ExperimentRequest | null }

export type QuestionKind = "purchase_intent" | "appeal" | "value" | "uniqueness" | "price_vw" | "preference" | "open";
export type ScaleKind = "purchase_intent" | "appeal" | "value" | "uniqueness";

export interface SurveyRequest {
  name?: string;
  stimuli: string[];
  stimulus_names: string[];
  questions: QuestionKind[];
  context?: string;
  reference_price?: number | null;
  currency: string;
  panel: number;
  age_groups?: string[];
  genders?: string[];
  model?: string;
  seed?: number;
}

export interface SurveyAnswer {
  respondent: string;
  age_group: string;
  gender: string;
  purchase_intent: number[];
  appeal: number[];
  value: number[];
  uniqueness: number[];
  too_cheap: number | null;
  cheap: number | null;
  expensive: number | null;
  too_expensive: number | null;
  preferred: number | null;
  why: string;
  error: string;
}

export interface ScaleSummary {
  question: QuestionKind;
  stimulus: number;
  n: number;
  mean: number;
  ci_low: number;
  ci_high: number;
  top2: number;
  distribution: number[];
}

export interface SegmentRow { segment: string; n: number; values: Record<string, number> }

export interface PriceRange {
  n: number;
  point_of_marginal_cheapness: number | null;
  optimal_price_point: number | null;
  indifference_price_point: number | null;
  point_of_marginal_expensiveness: number | null;
  curve: [number, number, number, number, number][];
}

export interface PreferenceShare { stimulus: number; name: string; share: number; ci_low: number; ci_high: number }

export interface SurveyReport {
  survey_id: string;
  name: string;
  model: string;
  stimuli: string[];
  stimulus_names: string[];
  questions: QuestionKind[];
  currency: string;
  respondents: number;
  errors: number;
  scales: ScaleSummary[];
  segments: SegmentRow[];
  price: PriceRange | null;
  preference: PreferenceShare[];
  verbatims: string[];
  answers: SurveyAnswer[];
  notes: string[];
  seconds: number;
}

export interface SurveyView extends JobStatus { report: SurveyReport | null; request?: SurveyRequest | null }

const root = (pid: string) => `/api/projects/${pid}`;

export const getMarketingInfo = (pid: string, signal?: AbortSignal) => fetchJson<{ currency: string }>(`${root(pid)}/marketing`, { signal });

export const startExperiment = (pid: string, req: ExperimentRequest) =>
  fetchJson<JobStatus>(`${root(pid)}/experiments`, { method: "POST", body: JSON.stringify(req) });
export const listExperiments = (pid: string, signal?: AbortSignal) => fetchJson<JobStatus[]>(`${root(pid)}/experiments`, { signal });
export const getExperiment = (pid: string, eid: string, signal?: AbortSignal) =>
  fetchJson<ExperimentView>(`${root(pid)}/experiments/${eid}`, { signal });
export const deleteExperiment = (pid: string, eid: string) => fetchJson<void>(`${root(pid)}/experiments/${eid}`, { method: "DELETE" });

export interface ReportNarrative { summary: string; interpretation: string; next_steps: string; model: string }
export const experimentReportUrl = (pid: string, eid: string) => `${BASE}${root(pid)}/experiments/${eid}/report.html`;
export const experimentMarkdownUrl = (pid: string, eid: string) => `${BASE}${root(pid)}/experiments/${eid}/report.md`;
export const writeNarrative = (pid: string, eid: string, model: string) =>
  fetchJson<ReportNarrative>(`${root(pid)}/experiments/${eid}/narrative`, { method: "POST", body: JSON.stringify({ model }) });

export const startSurvey = (pid: string, req: SurveyRequest) =>
  fetchJson<JobStatus>(`${root(pid)}/surveys`, { method: "POST", body: JSON.stringify(req) });
export const listSurveys = (pid: string, signal?: AbortSignal) => fetchJson<JobStatus[]>(`${root(pid)}/surveys`, { signal });
export const getSurvey = (pid: string, sid: string, signal?: AbortSignal) => fetchJson<SurveyView>(`${root(pid)}/surveys/${sid}`, { signal });
export const deleteSurvey = (pid: string, sid: string) => fetchJson<void>(`${root(pid)}/surveys/${sid}`, { method: "DELETE" });
export const surveyBoardUrl = (pid: string, sid: string) => `${BASE}${root(pid)}/surveys/${sid}/board.jpg`;
export const surveyReportUrl = (pid: string, sid: string) => `${BASE}${root(pid)}/surveys/${sid}/report.html`;
export const surveyCsvUrl = (pid: string, sid: string) => `${BASE}${root(pid)}/surveys/${sid}/export.csv`;

export const marketingKeys = {
  info: (pid: string) => ["projects", pid, "marketing"] as const,
  experiments: (pid: string) => ["projects", pid, "experiments"] as const,
  experiment: (pid: string, eid: string) => ["projects", pid, "experiments", eid] as const,
  surveys: (pid: string) => ["projects", pid, "surveys"] as const,
  survey: (pid: string, sid: string) => ["projects", pid, "surveys", sid] as const,
  packages: (pid: string) => ["projects", pid, "lab-packages"] as const,
};
