import { useQuery } from "@tanstack/react-query";

import { previewPilotPlan, type PilotPlanningResult } from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import { NeedsModel } from "@/features/settings/NeedsModel";
import { planningAssumptions, type PlanningInputs } from "./pilotPlanning";

export function PilotPlanner({ projectId, inputs, onChange, counts, onApply }: {
  projectId: string; inputs: PlanningInputs; onChange: (inputs: PlanningInputs) => void;
  counts: number[]; onApply: (counts: number[]) => void;
}) {
  const { t } = useI18n();
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
    <label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={inputs.enabled} onChange={(e) => onChange({ ...inputs, enabled: e.target.checked })} />{t("mkPlanToggle")}</label>
    {inputs.enabled && <>
      <p className="text-xs text-muted-foreground">{t("mkPlanIntro")}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="text-sm">{t("mkMinEffect")}<Input type="number" min={0.1} max={100} step="any" value={inputs.effect} onChange={(e) => onChange({ ...inputs, effect: e.target.value })} placeholder={t("mkMinEffectPlaceholder")} /></label>
        <label className="text-sm">{t("mkTargetPower")}<Input type="number" min={50} max={99} step="any" value={inputs.power} onChange={(e) => onChange({ ...inputs, power: e.target.value })} /></label>
        <label className="text-sm">{t("mkDailyEncounters")}<Input type="number" min={0.1} max={100000} step="any" value={inputs.daily} onChange={(e) => onChange({ ...inputs, daily: e.target.value })} /></label>
        <label className="text-sm">{t("mkAvailableDays")}<Input type="number" min={1} max={3650} step={1} value={inputs.days} onChange={(e) => onChange({ ...inputs, days: e.target.value })} /></label>
      </div>
      {!assumptions && <p className="text-xs text-muted-foreground">{t("mkPlanInvalid")}</p>}
      {!validCounts && <p className="text-xs text-muted-foreground">{t("mkFixBlocks")}</p>}
      {assumptions && validCounts && <>
        {plan.isPending && <p className="text-sm">{t("mkCalcSample")}</p>}
        {plan.error && <p role="alert" className="text-sm text-destructive">{plan.error.message}</p>}
        {plan.error && <div className="basis-full"><NeedsModel purpose="assist" /></div>}
        {plan.data && <>
          <PilotPlanningSummary plan={plan.data} />
          {plan.data.suggested_block_counts && <Button type="button" size="sm" variant="outline" onClick={() => onApply(plan.data.suggested_block_counts!)}>{t("mkUseRecommended")}</Button>}
          <p className="text-xs text-muted-foreground">{t("mkApplyCountsHint")}</p>
        </>}
      </>}
    </>}
  </section>;
}

export function PilotPlanningSummary({ plan }: { plan: PilotPlanningResult }) {
  const { t } = useI18n();
  const a = plan.assumptions;
  const meetsTarget = plan.planned_encounters >= plan.required_encounters;
  const powerFloor = Math.min(99.9, Math.floor(plan.planned_power_lower_bound * 1000) / 10).toFixed(1);
  return <div className="space-y-2 text-sm">
    <p>{t("mkPlanAssumptions", { effect: (a.minimum_effect * 100).toFixed(1), power: (a.target_power * 100).toFixed(1), daily: String(a.eligible_per_day), days: String(a.available_days) })}</p>
    <p className="font-medium">{t("mkCurrentPlan", { encounters: plan.planned_encounters, power: powerFloor, days: plan.planned_days })}</p>
    <p>{t("mkHalfWidth", { value: (plan.planned_ci_half_width * 100).toFixed(1) })} {meetsTarget ? t("mkMeetsTarget") : t("mkMissesTarget")}</p>
    <p>{t("mkRequired", { encounters: plan.required_encounters, days: plan.required_days })}</p>
    {plan.planned_days > a.available_days && <p className="font-medium">{t("mkCurrentExceedsDays")}</p>}
    {plan.required_days > a.available_days && <p className="font-medium">{t("mkRequiredExceedsDays")}</p>}
    {!plan.suggested_block_counts && <p className="font-medium">{t("mkExceedsCapacity")}</p>}
    {!plan.suggested_block_counts && plan.required_encounters <= 10000 && <p>{t("mkBlocksNeeded", { needed: Math.ceil(plan.required_encounters / 2000), current: plan.block_counts.length })}</p>}
    <details><summary className="cursor-pointer text-xs font-medium">{t("mkPlanMethod")}</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{plan.notes.map((note) => <li key={note}>{note}</li>)}</ul><p className="mt-2 text-xs">{t("mkMethodValue", { value: plan.method })}</p></details>
  </div>;
}
