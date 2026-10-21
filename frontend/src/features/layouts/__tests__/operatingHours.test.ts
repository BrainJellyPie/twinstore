import { expect, it } from "vitest";
import { resolveOperatingHours } from "../templateOptions";

const format = { open_hours: [9, 21] as [number, number], closed_days: [7] };

it("resolves individual blanks against the source format and keeps explicit all-day/all-week values", () => {
  expect(resolveOperatingHours({}, format)).toEqual({ open_hour: 9, close_hour: 21, closed_days: [7] });
  expect(resolveOperatingHours({ open_hour: 6 }, format)).toEqual({ open_hour: 6, close_hour: 21, closed_days: [7] });
  expect(resolveOperatingHours({ close_hour: 24 }, format)).toEqual({ open_hour: 9, close_hour: 24, closed_days: [7] });
  expect(resolveOperatingHours({ open_hour: 0, close_hour: 24, closed_days: [] }, format)).toEqual({ open_hour: 0, close_hour: 24, closed_days: [] });
  expect(resolveOperatingHours({}, { open_hours: [0, 24] })).toEqual({ open_hour: 0, close_hour: 24, closed_days: [] });
  expect(resolveOperatingHours({}, undefined)).toBeNull();
});

it.each([
  { open_hour: -1 }, { open_hour: 24 }, { open_hour: 1.5 }, { open_hour: NaN }, { open_hour: Infinity },
  { close_hour: 0 }, { close_hour: 25 }, { close_hour: 9.5 }, { close_hour: NaN }, { close_hour: Infinity },
  { open_hour: 21 }, { close_hour: 9 }, { open_hour: 22 }, { close_hour: 8 }, { open_hour: 20, close_hour: 6 },
  { closed_days: [0] }, { closed_days: [8] }, { closed_days: [1.5] }, { closed_days: [NaN] },
  { closed_days: [1, 1] }, { closed_days: [1, 2, 3, 4, 5, 6, 7] },
])("rejects invalid effective hours before a bulk update: %j", (patch) => {
  expect(resolveOperatingHours(patch, format)).toBeNull();
});

it.each(Array.from({ length: 7 }, (_, index) => index + 1))("keeps the last open weekday %i", (openDay) => {
  const closed_days = [1, 2, 3, 4, 5, 6, 7].filter((day) => day !== openDay);
  expect(resolveOperatingHours({ open_hour: 23, close_hour: 24, closed_days }, format)).toEqual({ open_hour: 23, close_hour: 24, closed_days });
});

it("normalizes day order without sharing or modifying source arrays", () => {
  const days = [7, 2, 6];
  const resolved = resolveOperatingHours({ closed_days: days }, format)!;
  expect(resolved.closed_days).toEqual([2, 6, 7]);
  expect(days).toEqual([7, 2, 6]);
  resolved.closed_days.push(3);
  expect(days).toEqual([7, 2, 6]);
  resolveOperatingHours({}, format)!.closed_days.push(1);
  expect(format.closed_days).toEqual([7]);
});
