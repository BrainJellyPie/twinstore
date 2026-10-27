// Other operations plans on a finished run: the same shoppers making the same choices, the store run another way.
// Replays and plans are server-side and take no model call.

import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Plus, Save, Sparkles, X } from "lucide-react";

import * as api from "@/shared/api/client";
import type { MemoryConfig, OperationsConfig, OperationsCosts, OperationsOutcome, OperationsReport, RosterRules } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { RequestError } from "@/shared/components/RequestError";
import { queryKeys } from "@/shared/queries/keys";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { currencyCode, formatMoney, formatPercent, minorUnitDivisor, toMinor } from "@/shared/utils/money";
import { weekdayShort } from "@/shared/i18n/timeFormat";

import { choiceFromConfig, DEFAULT_SHARED_STORE, sharedStoreOptions, wholeIn, type SharedStoreChoice } from "../sharedStore";
import { describeShift, NEW_SHIFT, shiftFromText, shiftText, type ShiftText } from "../shifts";
import { SharedStoreControls } from "./SharedStoreControls";
import { WeeksView } from "./WeeksView";

type CostText = { till: string; refill: string; unit: string };
type MemoryText = { weeks: string; missing: string; line: string; wait: string; churn: string };
type LabRequest = { operations: OperationsConfig; costs: OperationsCosts; memory?: MemoryConfig; roster?: RosterRules };
const WEEK = [1, 2, 3, 4, 5, 6, 7];

const MEMORY_DEFAULT: MemoryText = { weeks: "8", missing: "3", line: "25", wait: "1", churn: "1" };

function chance(text: string): number | null {
  const value = Number(text.trim());
  return text.trim() !== "" && Number.isFinite(value) && value >= 0 && value <= 100 ? value / 100 : null;
}

const ROWS: { key: keyof OperationsOutcome; label: MessageKey; kind: "money" | "wait" | "count" | "hours" }[] = [
  { key: "revenue", label: "labRevenue", kind: "money" },
  { key: "lost_revenue", label: "labLost", kind: "money" },
  { key: "abandoned_revenue", label: "labAbandoned", kind: "money" },
  { key: "avg_wait_sec", label: "labWait", kind: "wait" },
  { key: "till_hours", label: "labTillHours", kind: "hours" },
  { key: "crew_hours", label: "opsCrewHours", kind: "hours" },
  { key: "restocks", label: "labRefills", kind: "count" },
  { key: "face_refills", label: "opsFaceRefills", kind: "count" },
  { key: "stock_units", label: "labUnits", kind: "count" },
  { key: "labor_cost", label: "labLaborCost", kind: "money" },
  { key: "restock_cost", label: "labRefillCost", kind: "money" },
  { key: "holding_cost", label: "labHoldingCost", kind: "money" },
  { key: "net", label: "labNet", kind: "money" },
];

/** `report`: the run's own shared-store report; null for a run whose shoppers each had the store alone. */
export function OperationsLab({ projectId, runId, setupId, report, currency }: {
  projectId: string;
  runId: string;
  /** The run's layout: its saved operations can be set from here. */
  setupId?: string;
  report: OperationsReport | null;
  currency?: string;
}) {
  const { locale, t } = useI18n();
  const id = useId();
  const code = currencyCode(currency);
  const divisor = minorUnitDivisor(code);
  const [choice, setChoice] = useState<SharedStoreChoice>(() => report ? choiceFromConfig(report.config) : DEFAULT_SHARED_STORE);
  const [hourTills, setHourTills] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(report?.config.till_schedule ?? {}).map(([hour, n]) => [hour, String(n)])));
  const [hourCrew, setHourCrew] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(report?.config.crew_schedule ?? {}).map(([hour, n]) => [hour, String(n)])));
  const [overrides, setOverrides] = useState<Record<string, number>>(() => report?.config.stock_overrides ?? {});
  const [costs, setCosts] = useState<CostText>({ till: "", refill: "", unit: "" });
  const [remember, setRemember] = useState(false);
  const [memoryText, setMemoryText] = useState<MemoryText>(MEMORY_DEFAULT);
  const [shifts, setShifts] = useState<ShiftText[]>(() => (report?.config.crew_shifts ?? []).map(shiftText));
  const [rosterOn, setRosterOn] = useState(false);
  const [rosterText, setRosterText] = useState({ min: "4", max: "8" });
  const replay = useMutation({ mutationFn: ({ roster: _, ...body }: LabRequest) => api.replayOperations(projectId, runId, body) });
  const plan = useMutation({ mutationFn: (body: LabRequest) => api.planOperations(projectId, runId, body) });
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (operations: OperationsConfig) => api.saveLayoutOperations(projectId, setupId!, operations),
    onSuccess: (saved) => queryClient.setQueryData(queryKeys.layoutOperations(projectId, setupId!), saved.operations),
  });
  const busy = replay.isPending || plan.isPending;

  // With a crew the hours staff the crew (tills and shelves); without one, the tills.
  const crewMode = choice.crew.trim() !== "";
  const byHour = crewMode ? hourCrew : hourTills;
  const setByHour = crewMode ? setHourCrew : setHourTills;
  const hourMax = crewMode ? 100 : 50;
  const hours = [...new Set([...(report?.hours ?? []), ...(replay.data?.report.hours ?? [])].map((h) => h.hour)
    .concat(Object.keys(byHour)))].sort();
  const base = sharedStoreOptions({ ...choice, enabled: true });
  const scheduleValid = Object.values(hourTills).every((v) => v.trim() === "" || wholeIn(v, 0, 50) !== null)
    && (!crewMode || Object.values(hourCrew).every((v) => v.trim() === "" || wholeIn(v, 0, 100) !== null));
  const money = (text: string) => text.trim() === "" ? 0 : toMinor(text, divisor);
  const costValues = { till_hour: money(costs.till), restock_round: money(costs.refill), stock_unit_day: money(costs.unit) };
  const costsValid = Object.values(costValues).every((v) => v !== null);
  const weeks = wholeIn(memoryText.weeks, 2, 52);
  const chances = [chance(memoryText.missing), chance(memoryText.line), chance(memoryText.wait), chance(memoryText.churn)];
  const memoryValid = !remember || (weeks !== null && chances.every((c) => c !== null));
  // With a crew, shifts (when there are any) decide who is on duty instead of the hours.
  const roster = crewMode && shifts.length > 0;
  const parsedShifts = shifts.map(shiftFromText);
  const shiftsValid = !crewMode || parsedShifts.every((shift) => shift !== null);
  const rosterMin = wholeIn(rosterText.min, 1, 12);
  const rosterMax = wholeIn(rosterText.max, 1, 16);
  const rosterValid = !crewMode || !rosterOn || (rosterMin !== null && rosterMax !== null && rosterMax >= rosterMin);
  const valid = base !== "invalid" && base !== undefined && scheduleValid && costsValid && memoryValid && shiftsValid;

  const request = () => {
    if (base === "invalid" || base === undefined || !costsValid) return null;
    const numbers = (text: Record<string, string>) => Object.fromEntries(Object.entries(text)
      .filter(([, v]) => v.trim() !== "").map(([hour, v]) => [hour, Number(v)]));
    const operations: OperationsConfig = {
      ...(report?.config ?? {}), ...base, till_schedule: numbers(hourTills), stock_overrides: overrides,
      crew_schedule: crewMode ? numbers(hourCrew) : {},
      crew_shifts: crewMode ? parsedShifts.filter((shift) => shift !== null) : [],
    };
    const [missing, line, wait, churn] = chances;
    const memory: MemoryConfig | undefined = remember && weeks !== null && missing != null && line != null && wait != null && churn != null
      ? { weeks, leave_per_missing_unit: missing, leave_after_line: line, leave_per_wait_minute: wait, weekly_churn: churn }
      : undefined;
    const rules = crewMode && rosterOn && rosterMin !== null && rosterMax !== null ? { min_hours: rosterMin, max_hours: rosterMax } : null;
    return { operations, costs: costValues as OperationsCosts, ...(memory ? { memory } : {}), ...(rules ? { roster: rules } : {}) };
  };
  const run = (which: "replay" | "plan") => {
    const body = request();
    if (!body) return;
    (which === "replay" ? replay : plan).mutate(body);
  };
  const applyPlan = (config: OperationsReport["config"]) => {
    setChoice(choiceFromConfig(config));
    setHourTills(Object.fromEntries(Object.entries(config.till_schedule).map(([hour, n]) => [hour, String(n)])));
    setHourCrew(Object.fromEntries(Object.entries(config.crew_schedule ?? {}).map(([hour, n]) => [hour, String(n)])));
    setShifts((config.crew_shifts ?? []).map(shiftText));
    setOverrides(config.stock_overrides);
  };

  const shown = (value: number, kind: (typeof ROWS)[number]["kind"]) => kind === "money" ? formatMoney(value, code, { locale })
    : kind === "wait" ? (value < 90 ? t("opsSeconds", { seconds: Math.round(value) }) : t("opsMinutes", { minutes: (value / 60).toLocaleString(locale, { maximumFractionDigits: 1 }) }))
    : kind === "hours" ? value.toLocaleString(locale, { maximumFractionDigits: 1 }) : value.toLocaleString(locale);
  const columns: { label: MessageKey; outcome: OperationsOutcome; crew: boolean; weeksNet?: number }[] = [
    ...(plan.data ? [{ label: "labNowCol" as const, outcome: plan.data.current, crew: plan.data.current_config.crew != null, weeksNet: plan.data.current_weeks?.net }] : []),
    ...(replay.data ? [{ label: "labReplayCol" as const, outcome: replay.data.outcome, crew: replay.data.report.config.crew != null, weeksNet: replay.data.weeks?.net }] : []),
    ...(plan.data ? [{ label: "labPlanCol" as const, outcome: plan.data.best, crew: plan.data.config.crew != null, weeksNet: plan.data.best_weeks?.net }] : []),
  ];
  // Crew hours and shelves refilled only where a column had a crew; till hours and refill rounds unless every column
  // had one.
  const crewed = (c: (typeof columns)[number]) => c.crew;
  const rows = ROWS.filter((row) => row.key === "crew_hours" || row.key === "face_refills" ? columns.some(crewed)
    : row.key === "till_hours" || row.key === "restocks" ? !columns.every(crewed) : true);
  const memoryField = (key: keyof MemoryText, label: MessageKey) => (
    <div className="space-y-1">
      <label className="block font-medium" htmlFor={`${id}-mem-${key}`}>{t(label)}</label>
      <Input id={`${id}-mem-${key}`} type="number" min={key === "weeks" ? 2 : 0} max={key === "weeks" ? 52 : 100}
        step={key === "weeks" ? 1 : 0.5} className="h-7" value={memoryText[key]}
        onChange={(e) => setMemoryText({ ...memoryText, [key]: e.target.value })}
        aria-invalid={key === "weeks" ? weeks === null : chance(memoryText[key]) === null}
        aria-describedby={(key === "weeks" ? weeks === null : chance(memoryText[key]) === null) ? `${id}-mem-invalid` : undefined} />
    </div>
  );
  const costField = (key: keyof CostText, label: MessageKey) => (
    // Labels wrap to different heights side by side: the fields line up along the bottom.
    <div className="flex flex-col justify-end gap-1">
      <label className="block font-medium" htmlFor={`${id}-${key}`}>{t(label)}</label>
      <Input id={`${id}-${key}`} inputMode="decimal" className="h-7" value={costs[key]} placeholder="0"
        onChange={(e) => setCosts({ ...costs, [key]: e.target.value })} aria-invalid={money(costs[key]) === null}
        aria-describedby={money(costs[key]) === null ? `${id}-cost-invalid` : undefined} />
    </div>
  );

  return (
    <details className="group mt-3 rounded-md border" data-testid="operations-lab">
      <summary className="flex cursor-pointer list-none items-center gap-2 p-2 text-xs font-medium">
        <FlaskConical className="size-3.5 shrink-0" aria-hidden />{t("labTitle")}
      </summary>
      <div className="space-y-3 border-t p-2 text-xs">
        <p className="text-muted-foreground">{t(report ? "labIntro" : "labIntroAlone")}</p>
        <SharedStoreControls value={{ ...choice, enabled: true }} onChange={setChoice} fieldsOnly />
        {hours.length > 0 && !roster && (
          <fieldset className="space-y-1">
            <legend className="font-medium">{t(crewMode ? "labCrewByHourTitle" : "opsHoursTitle")}</legend>
            <div className="grid grid-cols-2 gap-1.5 min-[400px]:grid-cols-3">
              {hours.map((hour) => (
                <label key={hour} className="flex items-center gap-1">
                  <span className="w-10 shrink-0 tabular-nums text-muted-foreground">{t("opsHourLabel", { hour })}</span>
                  <Input type="number" min={0} max={hourMax} step={1} className="h-7" value={byHour[hour] ?? ""}
                    aria-label={t(crewMode ? "labCrewAt" : "labTillsAt", { hour: t("opsHourLabel", { hour }) })}
                    aria-invalid={(byHour[hour] ?? "").trim() !== "" && wholeIn(byHour[hour] ?? "", 0, hourMax) === null}
                    aria-describedby={(byHour[hour] ?? "").trim() !== "" && wholeIn(byHour[hour] ?? "", 0, hourMax) === null ? `${id}-hours-invalid` : undefined}
                    onChange={(e) => setByHour({ ...byHour, [hour]: e.target.value })} />
                </label>
              ))}
            </div>
            <p className="text-muted-foreground">{t(crewMode ? "labCrewByHourHint" : "labTillsByHourHint")}</p>
            {!scheduleValid && <p id={`${id}-hours-invalid`} role="alert" className="text-destructive">{t("labHoursInvalid", { max: hourMax })}</p>}
          </fieldset>
        )}
        {crewMode && (
          <fieldset className="space-y-1.5">
            <legend className="font-medium">{t("labShiftsTitle")}</legend>
            <p className="text-muted-foreground">{t("labShiftsHint")}</p>
            {shifts.map((shift, index) => {
              const set = (patch: Partial<ShiftText>) => setShifts(shifts.map((s, i) => i === index ? { ...s, ...patch } : s));
              return (
                <div key={index} role="group" aria-label={t("labShiftN", { n: index + 1 })} className="space-y-1 rounded-md border p-1.5">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <label className="flex items-center gap-1">{t("labShiftFrom")}
                      <Input type="number" min={0} max={23} step={1} className="h-7 w-16 px-2" value={shift.start}
                        aria-invalid={parsedShifts[index] === null} aria-describedby={parsedShifts[index] === null ? `${id}-shift-invalid` : undefined}
                        onChange={(e) => set({ start: e.target.value })} />
                    </label>
                    <label className="flex items-center gap-1">{t("labShiftTo")}
                      <Input type="number" min={1} max={24} step={1} className="h-7 w-16 px-2" value={shift.end}
                        aria-invalid={parsedShifts[index] === null} aria-describedby={parsedShifts[index] === null ? `${id}-shift-invalid` : undefined}
                        onChange={(e) => set({ end: e.target.value })} />
                    </label>
                    <label className="flex items-center gap-1">{t("labShiftStaff")}
                      <Input type="number" min={1} max={100} step={1} className="h-7 w-16 px-2" value={shift.staff}
                        aria-invalid={parsedShifts[index] === null} aria-describedby={parsedShifts[index] === null ? `${id}-shift-invalid` : undefined}
                        onChange={(e) => set({ staff: e.target.value })} />
                    </label>
                    <Button type="button" size="icon" variant="ghost" className="size-7" aria-label={t("labRemoveShift", { n: index + 1 })}
                      onClick={() => setShifts(shifts.filter((_, i) => i !== index))}><X className="size-3.5" aria-hidden /></Button>
                  </div>
                  <div role="group" aria-label={t("labShiftDays")} className="flex flex-wrap gap-1">
                    {WEEK.map((day) => {
                      const on = shift.days.includes(day);
                      return (
                        <button key={day} type="button" aria-pressed={on}
                          className={on ? "rounded border border-primary bg-primary px-1.5 py-0.5 text-primary-foreground" : "rounded border px-1.5 py-0.5"}
                          onClick={() => set({ days: on ? shift.days.filter((d) => d !== day) : [...shift.days, day] })}>
                          {weekdayShort(day, locale)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
            <Button type="button" size="sm" variant="outline" onClick={() => setShifts([...shifts, NEW_SHIFT])}>
              <Plus className="size-3.5" aria-hidden />{t("labAddShift")}
            </Button>
            {!shiftsValid && <p id={`${id}-shift-invalid`} role="alert" className="text-destructive">{t("labShiftInvalid")}</p>}
            <label className="flex items-start gap-2 pt-1 font-medium" htmlFor={`${id}-roster`}>
              <input id={`${id}-roster`} type="checkbox" className="mt-0.5 size-4 accent-primary" checked={rosterOn}
                onChange={(e) => setRosterOn(e.target.checked)} aria-describedby={`${id}-roster-hint`} />
              {t("labPlanRoster")}
            </label>
            <p id={`${id}-roster-hint`} className="text-muted-foreground">{t("labPlanRosterHint")}</p>
            {rosterOn && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="block font-medium" htmlFor={`${id}-roster-min`}>{t("labRosterMin")}</label>
                  <Input id={`${id}-roster-min`} type="number" min={1} max={12} step={1} className="h-7" value={rosterText.min}
                    onChange={(e) => setRosterText({ ...rosterText, min: e.target.value })} aria-invalid={rosterMin === null}
                    aria-describedby={rosterValid ? undefined : `${id}-roster-invalid`} />
                </div>
                <div className="space-y-1">
                  <label className="block font-medium" htmlFor={`${id}-roster-max`}>{t("labRosterMax")}</label>
                  <Input id={`${id}-roster-max`} type="number" min={1} max={16} step={1} className="h-7" value={rosterText.max}
                    onChange={(e) => setRosterText({ ...rosterText, max: e.target.value })} aria-invalid={rosterMax === null}
                    aria-describedby={rosterValid ? undefined : `${id}-roster-invalid`} />
                </div>
              </div>
            )}
            {!rosterValid && <p id={`${id}-roster-invalid`} role="alert" className="text-destructive">{t("labRosterInvalid")}</p>}
          </fieldset>
        )}
        <fieldset className="space-y-1.5">
          <legend className="font-medium">{t("labCosts", { currency: code })}</legend>
          <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-3">
            {costField("till", crewMode ? "labCrewHourCost" : "labTillHourCost")}
            {costField("refill", "labRestockCost")}
            {costField("unit", "labUnitDayCost")}
          </div>
          {!costsValid && <p id={`${id}-cost-invalid`} role="alert" className="text-destructive">{t("labInvalidCost")}</p>}
        </fieldset>
        <fieldset className="space-y-1.5">
          <label className="flex items-start gap-2 font-medium" htmlFor={`${id}-remember`}>
            <input id={`${id}-remember`} type="checkbox" className="mt-0.5 size-4 accent-primary" checked={remember}
              onChange={(e) => setRemember(e.target.checked)} aria-describedby={`${id}-remember-hint`} />
            {t("memTitle")}
          </label>
          <p id={`${id}-remember-hint`} className="text-muted-foreground">{t("memHint")}</p>
          {remember && (
            <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
              {memoryField("weeks", "memWeeks")}
              {memoryField("missing", "memMissing")}
              {memoryField("line", "memLine")}
              {memoryField("wait", "memWait")}
              {memoryField("churn", "memChurn")}
            </div>
          )}
          {!memoryValid && <p id={`${id}-mem-invalid`} role="alert" className="text-destructive">{t("memInvalid")}</p>}
        </fieldset>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={!valid || busy} onClick={() => run("replay")}>
            {replay.isPending ? t("labReplaying") : t("labReplay")}
          </Button>
          <Button size="sm" disabled={!valid || !rosterValid || busy} onClick={() => run("plan")}>
            <Sparkles className="size-3.5" aria-hidden />{plan.isPending ? t("labPlanning") : t("labFindPlan")}
          </Button>
          {setupId && (
            <Button size="sm" variant="ghost" disabled={!valid || save.isPending}
              onClick={() => { const body = request(); if (body) save.mutate(body.operations); }}>
              <Save className="size-3.5" aria-hidden />{save.isPending ? t("labSaving") : t("labSaveForLayout")}
            </Button>
          )}
        </div>
        {save.isSuccess && <p role="status" className="text-positive">{t("labSavedForLayout")}</p>}
        <RequestError error={replay.error ?? plan.error ?? save.error} />

        {replay.data && (
          <p>{t("labKept", {
            planned: formatMoney(replay.data.planned_revenue, code, { locale }),
            kept: formatMoney(replay.data.outcome.revenue, code, { locale }),
            share: formatPercent(replay.data.planned_revenue ? replay.data.outcome.revenue / replay.data.planned_revenue : 1, 0),
          })}</p>
        )}
        {columns.length > 0 && (
          <div role="region" aria-label={t("labTitle")} tabIndex={0} className="overflow-x-auto">
          <table className="w-full tabular-nums [&_td]:px-2 [&_th]:px-2">
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-0.5 text-left font-normal"><span className="sr-only">{t("labTitle")}</span></th>
                {columns.map((c) => <th key={c.label} scope="col" className="py-0.5 text-right font-normal">{t(c.label)}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className={row.key === "net" ? "border-t font-semibold" : "border-t"}>
                  <th scope="row" className="py-1 text-left font-normal">{t(row.label)}</th>
                  {columns.map((c) => <td key={c.label} className="py-1 text-right">{shown(c.outcome[row.key] ?? 0, row.kind)}</td>)}
                </tr>
              ))}
              {columns.some((c) => c.weeksNet != null) && (
                <tr className="border-t font-semibold">
                  <th scope="row" className="py-1 text-left font-normal">{t("memNet")}</th>
                  {columns.map((c) => <td key={c.label} className="py-1 text-right">{c.weeksNet == null ? "—" : shown(c.weeksNet, "money")}</td>)}
                </tr>
              )}
            </tbody>
          </table>
          </div>
        )}
        {plan.data?.current_weeks && plan.data.best_weeks ? (
          <WeeksView code={code} series={[{ label: "labNowCol", report: plan.data.current_weeks }, { label: "labPlanCol", report: plan.data.best_weeks }]} />
        ) : replay.data?.weeks ? (
          <WeeksView code={code} series={[{ label: "labReplayCol", report: replay.data.weeks }]} />
        ) : null}
        {plan.data && (
          <div className="space-y-1 rounded-md border bg-muted/30 p-2">
            <p className="font-medium">{(() => {
              const now = plan.data.current_weeks?.net ?? plan.data.current.net;
              const best = plan.data.best_weeks?.net ?? plan.data.best.net;
              return best > now ? t("labNetGain", { amount: formatMoney(best - now, code, { locale }) }) : t("labNoBetter");
            })()}</p>
            <p className="text-muted-foreground">{t("labPlanSummary", {
              stock: plan.data.config.stock_per_facing.toLocaleString(locale),
              refill: plan.data.config.crew != null
                ? t("labRefillAtPoint", { percent: formatPercent(plan.data.config.refill_at ?? 0.5, 0) })
                : plan.data.config.restock_every_min == null ? t("labRefillNever") : t("labRefillEvery", { minutes: plan.data.config.restock_every_min }),
              raised: plan.data.raised_skus.length.toLocaleString(locale),
              tried: plan.data.replays.toLocaleString(locale),
            })}</p>
            {(plan.data.config.crew_shifts ?? []).length > 0 && (
              <p className="text-muted-foreground">{t("labPlanShifts", {
                shifts: (plan.data.config.crew_shifts ?? []).map((shift) => describeShift(shift, locale, t("shiftEveryDay"))).join(" · "),
              })}</p>
            )}
            {plan.data.config.crew != null && (plan.data.config.crew_shifts ?? []).length === 0 && (
              <p className="text-muted-foreground">{t("labPlanCrew", { crew: plan.data.config.crew.toLocaleString(locale) })}
                {Object.keys(plan.data.config.crew_schedule ?? {}).length > 0 && <> · {t("labPlanCrewHours", {
                  hours: Object.entries(plan.data.config.crew_schedule ?? {})
                    .map(([hour, crew]) => t("labPlanCrewHour", { hour: t("opsHourLabel", { hour }), crew })).join(" · "),
                })}</>}
              </p>
            )}
            {plan.data.config.crew == null && Object.keys(plan.data.config.till_schedule).length > 0 && (
              <p className="text-muted-foreground">{t("labPlanTills", {
                hours: Object.entries(plan.data.config.till_schedule)
                  .map(([hour, tills]) => t("labPlanTillsHour", { hour: t("opsHourLabel", { hour }), tills })).join(" · "),
              })}</p>
            )}
            {plan.data.complete === false && <p className="text-muted-foreground">{t("labPartial")}</p>}
            <Button size="sm" variant="outline" onClick={() => applyPlan(plan.data.config)}>{t("labUsePlan")}</Button>
          </div>
        )}
      </div>
    </details>
  );
}
