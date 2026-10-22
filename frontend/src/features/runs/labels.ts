import type { RunListItem } from "@/shared/api/client";
import { translate } from "@/shared/i18n/translate";
import type { Locale, MessageKey } from "@/shared/i18n/messages";

export function engineLabel(engine: string | undefined, locale: Locale = "en"): string {
  if (engine === "rule_based") return translate(locale, "engineRuleBased");
  if (engine === "pattern_intent_impulse") return "LLM";
  if (engine === "vlm_glance") return translate(locale, "engineVision");
  return engine ? engine : "LLM";
}

function shortTime(iso: string, locale: Locale): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date().toDateString() === d.toDateString();
  // English keeps the browser's own date and time style.
  const format = locale === "en" ? undefined : locale;
  return today
    ? d.toLocaleTimeString(format, { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString(format, { month: "short", day: "numeric" });
}

// e.g. "LLM · seed 0 · final · Oct 20, 17:40"
export function runLabel(run: RunListItem, locale: Locale = "en"): string {
  const engine = engineLabel(run.engine_type ?? run.manifest?.engine_type, locale);
  const seed = run.seed ?? run.manifest?.seed;
  const rep = run.replicate ?? run.manifest?.replicate;
  const parts = [engine];
  if (seed !== undefined) parts.push(translate(locale, "runLabelSeed", { seed: `${seed}${rep ? `/${rep}` : ""}` }));
  const scenario = run.scenario ?? run.manifest?.scenario;
  if (scenario) parts.push(scenario);
  parts.push(translate(locale, run.preview ? "runLabelPreview" : "runLabelFinal"));
  const when = shortTime(run.created_at, locale);
  if (when) parts.push(when);
  return parts.join(" · ");
}

const METRIC_LABELS: Record<string, MessageKey> = {
  spend: "metricSpend",
  units: "metricUnits",
  bought: "kpiConversion",
  impulse_spend: "metricImpulseSpend",
  visit_sec: "metricVisitSec",
  path_tiles: "metricPathTiles",
};

export function metricLabel(metric: string, locale: Locale = "en"): string {
  const key = Object.prototype.hasOwnProperty.call(METRIC_LABELS, metric) ? METRIC_LABELS[metric] : undefined;
  return key ? translate(locale, key) : metric;
}
