import { useQuery } from "@tanstack/react-query";

import { previewPilotPlan, type PilotPlanningResult } from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { planningAssumptions, type PlanningInputs } from "./pilotPlanning";

export function PilotPlanner({ projectId, inputs, onChange, counts, onApply }: {
  projectId: string; inputs: PlanningInputs; onChange: (inputs: PlanningInputs) => void;
  counts: number[]; onApply: (counts: number[]) => void;
}) {
  const assumptions = planningAssumptions(inputs);
  const total = counts.reduce((a, b) => a + b, 0);
  const validCounts = counts.length >= 1 && counts.length <= 30 && total >= 40 && total <= 10000
    && counts.every((n) => Number.isInteger(n) && n >= 4 && n <= 2000 && n % 2 === 0);
  const plan = useQuery({
    queryKey: ["projects", projectId, "pilot-planning", assumptions, counts],
    queryFn: ({ signal }) => previewPilotPlan(projectId, assumptions!, counts, signal),
    enabled: !!assumptions && validCounts, retry: false, staleTime: Infinity,
  });
  return <section className="space-y-3 rounded-xl border p-3">
    <label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={inputs.enabled} onChange={(e) => onChange({ ...inputs, enabled: e.target.checked })} />Plan sample size and duration</label>
    {inputs.enabled && <>
      <p className="text-xs text-muted-foreground">Choose assumptions before collecting data. This uses the same conservative 95% interval as the final report. Enter your smallest worthwhile absolute conversion difference and estimated unique eligible encounters; synthetic ratings are not conversion rates.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">Minimum effect (percentage points)<Input type="number" min={0.1} max={100} step="any" value={inputs.effect} onChange={(e) => onChange({ ...inputs, effect: e.target.value })} placeholder="e.g. 5 means 20% versus 25%" /></label>
        <label className="text-sm">Target power lower bound (%)<Input type="number" min={50} max={99} step="any" value={inputs.power} onChange={(e) => onChange({ ...inputs, power: e.target.value })} /></label>
        <label className="text-sm">Eligible encounters per operating day<Input type="number" min={0.1} max={100000} step="any" value={inputs.daily} onChange={(e) => onChange({ ...inputs, daily: e.target.value })} /></label>
        <label className="text-sm">Available operating days<Input type="number" min={1} max={3650} step={1} value={inputs.days} onChange={(e) => onChange({ ...inputs, days: e.target.value })} /></label>
      </div>
      {!assumptions && <p className="text-xs text-muted-foreground">Enter an effect of 0.1–100 pp, power of 50–99%, daily capacity of 0.1–100,000, and 1–3,650 whole operating days.</p>}
      {!validCounts && <p className="text-xs text-muted-foreground">Correct the planned block counts before calculating.</p>}
      {assumptions && validCounts && <>
        {plan.isPending && <p className="text-sm">Calculating sample requirements…</p>}
        {plan.error && <p role="alert" className="text-sm text-destructive">{plan.error.message}</p>}
        {plan.data && <>
          <PilotPlanningSummary plan={plan.data} />
          {plan.data.suggested_block_counts && <Button type="button" size="sm" variant="outline" onClick={() => onApply(plan.data.suggested_block_counts!)}>Use recommended counts evenly across these blocks</Button>}
          <p className="text-xs text-muted-foreground">Applying counts changes staff/shift weights. Review each block's capacity. The assessment is saved with the fixed pilot plan; it cannot resize an existing pilot.</p>
        </>}
      </>}
    </>}
  </section>;
}

export function PilotPlanningSummary({ plan }: { plan: PilotPlanningResult }) {
  const a = plan.assumptions;
  const meetsTarget = plan.planned_encounters >= plan.required_encounters;
  const powerFloor = Math.min(99.9, Math.floor(plan.planned_power_lower_bound * 1000) / 10).toFixed(1);
  return <div className="space-y-2 text-sm">
    <p>Planning assumptions: {(a.minimum_effect * 100).toFixed(1)} pp minimum effect · {(a.target_power * 100).toFixed(1)}% target power bound · {a.eligible_per_day} eligible encounters/day · {a.available_days} available days.</p>
    <p className="font-medium">Current plan: {plan.planned_encounters.toLocaleString()} encounters · at least {powerFloor}% power under these assumptions · {plan.planned_days.toLocaleString()} operating days.</p>
    <p>Unclipped 95% interval half-width: {(plan.planned_ci_half_width * 100).toFixed(1)} pp. {meetsTarget ? "The current sample meets the target power bound." : "The current sample does not meet the target power bound."}</p>
    <p>Required for the target: {plan.required_encounters.toLocaleString()} encounters · {plan.required_days.toLocaleString()} operating days, plus outcome follow-up.</p>
    {plan.planned_days > a.available_days && <p className="font-medium">The current sample exceeds the available operating days.</p>}
    {plan.required_days > a.available_days && <p className="font-medium">The required sample exceeds the available operating days.</p>}
    {!plan.suggested_block_counts && <p className="font-medium">The required sample exceeds the current block capacity or the 10,000-encounter pilot limit. No smaller sample is presented as sufficient.</p>}
    {!plan.suggested_block_counts && plan.required_encounters <= 10000 && <p>At least {Math.ceil(plan.required_encounters / 2000)} staff/shift blocks are needed at 2,000 encounters each; this plan has {plan.block_counts.length}. Add blocks only for staff/shifts you can actually operate.</p>}
    <details><summary className="cursor-pointer text-xs font-medium">Sample planning method and assumptions</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{plan.notes.map((note) => <li key={note}>{note}</li>)}</ul><p className="mt-2 text-xs">Method: {plan.method}</p></details>
  </div>;
}
