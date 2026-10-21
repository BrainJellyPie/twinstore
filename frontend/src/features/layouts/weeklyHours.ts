import type { DaySchedule } from "@/shared/types/domain";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function dayRange(days: number[]): string {
  if (days.length === 7) return "Every day";
  const ranges: string[] = [];
  for (let index = 0; index < days.length; index++) {
    const start = days[index]!;
    let end = start;
    while (days[index + 1] === end + 1) end = days[++index]!;
    ranges.push(start === end ? DAYS[start - 1]! : `${DAYS[start - 1]}–${DAYS[end - 1]}`);
  }
  return ranges.join(", ");
}

export function formatWeeklyHours(schedule: DaySchedule[]): string {
  if (!schedule.length) return "Not set";
  const groups = new Map<string, number[]>();
  for (let day = 1; day <= 7; day++) {
    // Store.schedule_for uses the first matching entry and closes missing weekdays.
    const entry = schedule.find((item) => item.day === day);
    const hours = entry?.is_open
      ? `${String(entry.open_hour).padStart(2, "0")}:00–${String(entry.close_hour).padStart(2, "0")}:00`
      : "Closed";
    const days = groups.get(hours) ?? [];
    days.push(day);
    groups.set(hours, days);
  }
  return [...groups].map(([hours, days]) => `${dayRange(days)}: ${hours}`).join("; ");
}
