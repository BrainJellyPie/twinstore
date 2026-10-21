// @vitest-environment jsdom
import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { Store } from "@/shared/types/domain";
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
