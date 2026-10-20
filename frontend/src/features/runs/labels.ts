import type { RunListItem } from "@/shared/api/client";

export function engineLabel(engine: string | undefined): string {
  if (engine === "rule_based") return "Rule-based";
  if (engine === "pattern_intent_impulse") return "LLM";
  if (engine === "vlm_glance") return "Vision";
  return engine ? engine : "LLM";
}

function shortTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date().toDateString() === d.toDateString();
  return today
    ? d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// e.g. "LLM · seed 0 · final · Oct 20, 17:40"
export function runLabel(run: RunListItem): string {
  const engine = engineLabel(run.engine_type ?? run.manifest?.engine_type);
  const seed = run.seed ?? run.manifest?.seed;
  const rep = run.replicate ?? run.manifest?.replicate;
  const parts = [engine];
  if (seed !== undefined) parts.push(`seed ${seed}${rep ? `/${rep}` : ""}`);
  const scenario = run.scenario ?? run.manifest?.scenario;
  if (scenario) parts.push(scenario);
  parts.push(run.preview ? "preview" : "final");
  const when = shortTime(run.created_at);
  if (when) parts.push(when);
  return parts.join(" · ");
}

export const METRIC_LABELS: Record<string, string> = {
  spend: "Spend / visitor",
  units: "Units / visitor",
  bought: "Conversion",
  impulse_spend: "Impulse spend / visitor",
  visit_sec: "Visit time (s)",
  path_tiles: "Walking distance (tiles)",
};
