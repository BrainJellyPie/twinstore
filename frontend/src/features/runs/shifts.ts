// Crew shifts as the lab edits them and as results describe them.

import type { CrewShift } from "@/shared/api/client";
import type { Locale } from "@/shared/i18n/messages";
import { weekdayShort } from "@/shared/i18n/timeFormat";
import { wholeIn } from "./sharedStore";

/** A shift as typed: hours and staff kept as text so a half-written number is not rewritten under the cursor. */
export interface ShiftText { start: string; end: string; staff: string; days: number[] }

export const NEW_SHIFT: ShiftText = { start: "8", end: "16", staff: "1", days: [] };

export function shiftText(shift: CrewShift): ShiftText {
  return { start: String(shift.start), end: String(shift.end), staff: String(shift.staff), days: [...shift.days] };
}

/** The shift for its text, or null while it is impossible (hours 0–24, the end after the start, staff 1–100). */
export function shiftFromText(text: ShiftText): CrewShift | null {
  const start = wholeIn(text.start, 0, 23);
  const end = wholeIn(text.end, 1, 24);
  const staff = wholeIn(text.staff, 1, 100);
  if (start === null || end === null || staff === null || end <= start) return null;
  return { start, end, staff, days: [...text.days].sort((a, b) => a - b) };
}

const hh = (hour: number) => `${String(hour).padStart(2, "0")}:00`;

/** "Mon, Sat 08:00–16:00 ×2"; `everyDay` names a shift on every day. */
export function describeShift(shift: CrewShift, locale: Locale, everyDay: string): string {
  const days = shift.days.length === 0 || shift.days.length === 7 ? everyDay : shift.days.map((day) => weekdayShort(day, locale)).join(", ");
  return `${days} ${hh(shift.start)}–${hh(shift.end)} ×${shift.staff}`;
}
