import type { PilotPlanningAssumptions } from "@/shared/api/fieldPilot";

export interface PlanningInputs { enabled: boolean; effect: string; power: string; daily: string; days: string }
export const emptyPlanningInputs: PlanningInputs = { enabled: false, effect: "", power: "80", daily: "", days: "" };

export function planningAssumptions(inputs: PlanningInputs): PilotPlanningAssumptions | null {
  const effect = Number(inputs.effect), power = Number(inputs.power), daily = Number(inputs.daily), days = Number(inputs.days);
  if (!inputs.enabled || ![effect, power, daily, days].every(Number.isFinite)
    || effect < 0.1 || effect > 100 || power < 50 || power > 99 || daily < 0.1 || daily > 100000
    || !Number.isInteger(days) || days < 1 || days > 3650) return null;
  return { minimum_effect: effect / 100, target_power: power / 100, eligible_per_day: daily, available_days: days };
}
