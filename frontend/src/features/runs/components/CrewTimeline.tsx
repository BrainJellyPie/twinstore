// The crew's day in a crew run's results: one row per staff member, their time at the tills and refilling shelves,
// for the day the playback shows (with a mark at its clock).

import { useMemo } from "react";

import type { OperationsReport } from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import { weekdayLong } from "@/shared/i18n/timeFormat";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";

const TASKS_KEPT = 3000;   // the report keeps the first this many (shared_store._TASKS_REPORTED)

export function CrewTimeline({ report }: { report: OperationsReport }) {
  const { locale, t } = useI18n();
  const shownDay = useSimulationMetricsStore((s) => s.currentDay);
  const clock = useSimulationMetricsStore((s) => s.currentMinute);
  const tasks = useMemo(() => report.crew_tasks ?? [], [report.crew_tasks]);
  const days = useMemo(() => [...new Set(tasks.map((task) => task.day))].sort((a, b) => a - b), [tasks]);
  const day = days.includes(shownDay) ? shownDay : days[0];
  const today = useMemo(() => tasks.filter((task) => task.day === day), [tasks, day]);
  if (day === undefined || today.length === 0) return null;
  const from = Math.floor(Math.min(...today.map((task) => task.start)) / 3600) * 3600;
  const to = Math.ceil(Math.max(...today.map((task) => task.end)) / 3600) * 3600;
  const span = Math.max(3600, to - from);
  const crew = Math.max(report.config.crew ?? 1, ...Object.values(report.config.crew_schedule ?? {}), ...today.map((task) => task.member + 1));
  const at = (second: number) => `${((second - from) / span) * 100}%`;
  const hours = Array.from({ length: Math.round(span / 3600) + 1 }, (_, i) => from + i * 3600);
  const clockLabel = (second: number) =>
    `${String(Math.floor(second / 3600) % 24).padStart(2, "0")}:${String(Math.floor((second % 3600) / 60)).padStart(2, "0")}`;

  return (
    <figure className="mt-3" aria-label={t("opsCrewTimeline", { day: weekdayLong(day, locale) })}>
      <figcaption className="mb-1 text-xs font-medium text-muted-foreground">
        {t("opsCrewTimeline", { day: weekdayLong(day, locale) })}
      </figcaption>
      <div className="space-y-1">
        {Array.from({ length: crew }, (_, member) => (
          <div key={member} className="flex items-center gap-2 text-[0.72rem]">
            <span className="w-14 shrink-0 text-muted-foreground">{t("crewLabel", { n: member + 1 })}</span>
            <div className="relative h-3 flex-1 overflow-hidden rounded-sm bg-muted" data-testid={`crew-row-${member}`}>
              {today.filter((task) => task.member === member).map((task) => (
                <div key={`${task.start}:${task.kind}`} title={`${clockLabel(task.start)} ${task.kind === "refill"
                  ? t("crewRefilling", { name: task.name || task.sku }) : t("opsCrewTill")}`}
                  className={task.kind === "till" ? "absolute inset-y-0 bg-chart-1" : "absolute inset-y-0 bg-chart-4"}
                  style={{ left: at(task.start), width: `max(1px, ${((task.end - task.start) / span) * 100}%)` }} />
              ))}
              {clock >= from && clock <= to && <div className="absolute inset-y-0 w-px bg-foreground" style={{ left: at(clock) }} />}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-0.5 flex justify-between pl-16 text-[0.65rem] tabular-nums text-muted-foreground">
        {hours.filter((_, i) => i % Math.max(1, Math.ceil(hours.length / 6)) === 0).map((second) => <span key={second}>{clockLabel(second)}</span>)}
      </div>
      <div className="mt-1 flex gap-3 text-[0.72rem] text-muted-foreground">
        <span className="flex items-center gap-1"><span className="inline-block size-2 rounded-sm bg-chart-1" aria-hidden />{t("opsCrewTill")}</span>
        <span className="flex items-center gap-1"><span className="inline-block size-2 rounded-sm bg-chart-4" aria-hidden />{t("opsCrewRefill")}</span>
      </div>
      {tasks.length >= TASKS_KEPT && <p className="mt-1 text-[0.72rem] text-muted-foreground">{t("opsCrewTasksCut", { count: TASKS_KEPT.toLocaleString(locale) })}</p>}
    </figure>
  );
}
