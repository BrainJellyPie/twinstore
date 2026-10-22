import type { DaySchedule } from "@/shared/types/domain";
import type { Locale } from "@/shared/i18n/messages";
import { weekdayShort } from "@/shared/i18n/timeFormat";
import { translate } from "@/shared/i18n/translate";

function dayRange(days: number[], locale: Locale): string {
  if (days.length === 7) return translate(locale, "everyDay");
  const ranges: string[] = [];
  for (let index = 0; index < days.length; index++) {
    const start = days[index]!;
    let end = start;
    while (days[index + 1] === end + 1) end = days[++index]!;
    ranges.push(start === end ? weekdayShort(start, locale) : `${weekdayShort(start, locale)}–${weekdayShort(end, locale)}`);
  }
  return ranges.join(", ");
}

export function formatWeeklyHours(schedule: DaySchedule[], locale: Locale = "en"): string {
  if (!schedule.length) return translate(locale, "hoursNotSet");
  const groups = new Map<string, number[]>();
  for (let day = 1; day <= 7; day++) {
    // Store.schedule_for uses the first matching entry and closes missing weekdays.
    const entry = schedule.find((item) => item.day === day);
    const hours = entry?.is_open
      ? `${String(entry.open_hour).padStart(2, "0")}:00–${String(entry.close_hour).padStart(2, "0")}:00`
      : translate(locale, "hoursClosed");
    const days = groups.get(hours) ?? [];
    days.push(day);
    groups.set(hours, days);
  }
  return [...groups].map(([hours, days]) => `${dayRange(days, locale)}: ${hours}`).join("; ");
}
