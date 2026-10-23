// @vitest-environment jsdom
import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { CustomerResult, Store } from "@/shared/types/domain";
import { useStoreAssets } from "../useStoreAssets";
afterEach(cleanup);
const store: Store = { id: "week", name: "Mixed hours", type: "store", design_theme: "nordic", design_colors: { floor: "#000000" }, currency: "JPY", grid_size: [14, 12], racks: [], weekly_schedule: [] };

it.each([false, true])("covers early and late weekdays regardless of schedule order (reversed=%s)", (reverse) => {
  const schedule = [{ day: 1, is_open: true, open_hour: 9, close_hour: 12 }, { day: 2, is_open: true, open_hour: 23, close_hour: 24 },
    { day: 6, is_open: true, open_hour: 0, close_hour: 1 }, { day: 7, is_open: false, open_hour: 0, close_hour: 24 }];
  const { result } = renderHook(() => useStoreAssets({ ...store, weekly_schedule: reverse ? [...schedule].reverse() : schedule }));
  expect(result.current).toMatchObject({ openHour: 0, closeHour: 24, minTime: 0, maxTime: 86400, availableDays: [1, 2, 6], designColors: { floor: "#000000" }, currency: "JPY" });
});
it("ignores closed-day windows and updates when switching stores", () => {
  const schedule = [{ day: 1, is_open: false, open_hour: 0, close_hour: 24 }, { day: 2, is_open: true, open_hour: 9, close_hour: 12 }, { day: 3, is_open: true, open_hour: 8, close_hour: 20 }];
  const { result, rerender } = renderHook(({ value }) => useStoreAssets(value), { initialProps: { value: { ...store, weekly_schedule: schedule } } });
  expect(result.current).toMatchObject({ openHour: 8, closeHour: 20, minTime: 28800, maxTime: 72000, availableDays: [2, 3] });
  rerender({ value: { ...store, weekly_schedule: [{ day: 7, is_open: true, open_hour: 23, close_hour: 24 }] } });
  expect(result.current).toMatchObject({ minTime: 82800, maxTime: 86400, availableDays: [7] });
});
it.each([[], [{ day: 1, is_open: false, open_hour: 9, close_hour: 18 }]])("keeps the legacy all-day fallback when no days are open: %j", (...entries) => {
  const { result } = renderHook(() => useStoreAssets({ ...store, weekly_schedule: entries }));
  expect(result.current).toMatchObject({ minTime: 0, maxTime: 86400, availableDays: [1] });
});

const shopper = (day: number, arrival: string, elapsed: number, duration: number): CustomerResult => ({
  persona_id: `p${day}`, day, arrival_time: arrival, leave_time: "", total_spent: 0,
  timeline: [{ elapsed_sec: elapsed, duration, action: "exit", x: 0, y: 0, target_rack: "", face: null,
    description: "", product_sku: "", product_name: "", price: 0 }],
});

it.each([
  ["17:59:00", 18, 120, 5, 18 * 3600 + 65],
  ["23:59:00", 24, 120, 5, 24 * 3600 + 65],
  ["23:59:00", 24, 7260, 0, 26 * 3600],
])("includes recorded visits beyond closing: %s", (arrival, closing, elapsed, duration, end) => {
  const value = { ...store, weekly_schedule: [{ day: 1, is_open: true, open_hour: 8, close_hour: closing }] };
  const { result } = renderHook(() => useStoreAssets(value, [shopper(1, arrival, elapsed, duration)]));
  expect(result.current.maxTime).toBe(end);
  expect(result.current.closeHour).toBe(closing);
});

it("includes recorded weekdays and early arrivals when the saved schedule is incomplete", () => {
  const value = { ...store, weekly_schedule: [{ day: 1, is_open: true, open_hour: 9, close_hour: 18 }] };
  const people = [shopper(7, "07:30:00", 60, 0), shopper(2, "10:00:00", 60, 0), shopper(2, "10:30:00", 60, 0)];
  const { result } = renderHook(() => useStoreAssets(value, people));
  expect(result.current).toMatchObject({ minTime: 7.5 * 3600, maxTime: 18 * 3600, availableDays: [1, 2, 7] });
});

it("uses actual visit days for legacy stores and resets the extent when switching runs", () => {
  const { result, rerender } = renderHook(({ people }) => useStoreAssets(store, people), {
    initialProps: { people: [shopper(7, "23:59:00", 180, 0)] },
  });
  expect(result.current).toMatchObject({ maxTime: 24 * 3600 + 120, availableDays: [7] });
  rerender({ people: [shopper(2, "10:00:00", 60, 0)] });
  expect(result.current).toMatchObject({ maxTime: 86400, availableDays: [2] });
});
