import { expect, it } from "vitest";
import type { DaySchedule } from "@/shared/types/domain";
import { formatWeeklyHours } from "../weeklyHours";

const week = (open = 9, close = 21): DaySchedule[] => Array.from({ length: 7 }, (_, index) => ({ day: index + 1, is_open: true, open_hour: open, close_hour: close }));

it("distinguishes missing hours, all-day opening and a fully closed schedule", () => {
  expect(formatWeeklyHours([])).toBe("Not set");
  expect(formatWeeklyHours(week(0, 24))).toBe("Every day: 00:00–24:00");
  expect(formatWeeklyHours(week().map((day) => ({ ...day, is_open: false })))).toBe("Every day: Closed");
});

it("groups office weekdays and closed weekends", () => {
  expect(formatWeeklyHours(week(6, 15).map((day) => ({ ...day, is_open: day.day <= 5 })))).toBe("Mon–Fri: 06:00–15:00; Sat–Sun: Closed");
});

it.each([
  [1, "Mon: 23:00–24:00; Tue–Sun: Closed"],
  [2, "Mon, Wed–Sun: Closed; Tue: 23:00–24:00"],
  [3, "Mon–Tue, Thu–Sun: Closed; Wed: 23:00–24:00"],
  [4, "Mon–Wed, Fri–Sun: Closed; Thu: 23:00–24:00"],
  [5, "Mon–Thu, Sat–Sun: Closed; Fri: 23:00–24:00"],
  [6, "Mon–Fri, Sun: Closed; Sat: 23:00–24:00"],
  [7, "Mon–Sat: Closed; Sun: 23:00–24:00"],
])("shows a one-hour opening on weekday %i", (openDay, expected) => {
  expect(formatWeeklyHours(week(23, 24).map((day) => ({ ...day, is_open: day.day === openDay })))).toBe(expected);
});

it("keeps gaps between nonconsecutive weekdays visible", () => {
  expect(formatWeeklyHours(week().map((day) => ({ ...day, is_open: [1, 3, 5].includes(day.day) })))).toBe("Mon, Wed, Fri: 09:00–21:00; Tue, Thu, Sat–Sun: Closed");
});

it("retains distinct weekend hours and sorts an unordered schedule without mutation", () => {
  const schedule = week().map((day) => day.day === 6 ? { ...day, open_hour: 10, close_hour: 18 }
    : day.day === 7 ? { ...day, open_hour: 11, close_hour: 15 } : day).reverse();
  const before = structuredClone(schedule);
  expect(formatWeeklyHours(schedule)).toBe("Mon–Fri: 09:00–21:00; Sat: 10:00–18:00; Sun: 11:00–15:00");
  expect(schedule).toEqual(before);
});

it("matches legacy store behavior for missing weekdays and repeated entries", () => {
  expect(formatWeeklyHours([{ day: 1, is_open: true, open_hour: 8, close_hour: 16 }])).toBe("Mon: 08:00–16:00; Tue–Sun: Closed");
  expect(formatWeeklyHours([{ day: 1, is_open: false, open_hour: 0, close_hour: 0 }, { day: 1, is_open: true, open_hour: 6, close_hour: 23 }])).toBe("Every day: Closed");
});
