import type { Locale } from "./messages";

// Formatted in UTC from fixed dates so the viewer's time zone never shifts a weekday or a store clock.
// 2024-01-01 is a Monday.

/** Short weekday name in the selected language; day 1 is Monday, 7 is Sunday. */
export function weekdayShort(day: number, locale: Locale): string {
  const index = (((day - 1) % 7) + 7) % 7;
  return new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(new Date(Date.UTC(2024, 0, 1 + index)));
}

/** Store clock for seconds after midnight: "9:05 am" in English, the selected language's own format otherwise. */
export function clockTime(seconds: number, locale: Locale): string {
  const h = Math.floor(seconds / 3600) % 24;
  const m = Math.floor((seconds % 3600) / 60);
  if (locale === "en") return `${h === 0 ? 12 : h > 12 ? h - 12 : h}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
  return new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit", timeZone: "UTC" }).format(new Date(Date.UTC(2024, 0, 1, h, m)));
}
