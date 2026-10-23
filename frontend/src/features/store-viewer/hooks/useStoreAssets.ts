import { useMemo } from "react";
import type { CustomerResult, Store, Rack } from "@/shared/types/domain";
import { parseTimeToSeconds } from "@/features/playback/utils/playback";

export interface StoreAssets {
  designTheme: Store["design_theme"];
  designColors?: Store["design_colors"];
  currency: Store["currency"];
  width: number;
  depth: number;
  racks: Rack[];
  doors: Rack[];
  items: Rack[];
  openHour: number;
  closeHour: number;
  minTime: number;
  maxTime: number;
  availableDays: number[];
}

export function useStoreAssets(store: Store, customers?: CustomerResult[]): StoreAssets {
  return useMemo(() => {
    const [width = 0, depth = 0] = store.grid_size;
    const racks = store.racks;
    const doors = racks.filter((f) => f.type === "entrance" || f.type === "exit");
    const items = racks.filter((f) => f.type !== "entrance" && f.type !== "exit");

    const open = (store.weekly_schedule ?? []).filter((day) => day.is_open);
    // Every weekday shares the playback time axis, so include the entire week.
    const openHour = open.length ? Math.min(...open.map((day) => day.open_hour)) : 0;
    const closeHour = open.length ? Math.max(...open.map((day) => day.close_hour)) : 24;

    const days = new Set((store.weekly_schedule ?? [])
      .filter((d) => d.is_open)
      .map((d) => d.day));
    let minTime = openHour * 3600;
    let maxTime = closeHour * 3600;
    // A late arrival can still be paying or leaving after closing, including after midnight.
    for (const customer of customers ?? []) {
      days.add(customer.day ?? 1);
      const arrival = parseTimeToSeconds(customer.arrival_time);
      if (!Number.isFinite(arrival)) continue;
      minTime = Math.min(minTime, arrival);
      maxTime = Math.max(maxTime, arrival);
      for (const event of customer.timeline) {
        const end = arrival + event.elapsed_sec + Math.max(0, event.duration ?? 0);
        if (Number.isFinite(end)) maxTime = Math.max(maxTime, end);
      }
    }
    const availableDays = days.size > 0 ? [...days].sort((a, b) => a - b) : [1];

    return {
      designTheme: store.design_theme,
      designColors: store.design_colors,
      currency: store.currency,
      width,
      depth,
      racks,
      doors,
      items,
      openHour,
      closeHour,
      minTime,
      maxTime,
      availableDays,
    };
  }, [store, customers]);
}
