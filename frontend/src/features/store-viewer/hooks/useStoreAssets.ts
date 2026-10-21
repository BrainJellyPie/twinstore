import { useMemo } from "react";
import type { Store, Rack } from "@/shared/types/domain";

export interface StoreAssets {
  designTheme: Store["design_theme"];
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

export function useStoreAssets(store: Store): StoreAssets {
  return useMemo(() => {
    const [width = 0, depth = 0] = store.grid_size;
    const racks = store.racks;
    const doors = racks.filter((f) => f.type === "entrance" || f.type === "exit");
    const items = racks.filter((f) => f.type !== "entrance" && f.type !== "exit");

    const open = store.weekly_schedule?.find((d) => d.is_open);
    const openHour = open?.open_hour ?? 0;
    const closeHour = open?.close_hour ?? 24;

    const days = (store.weekly_schedule ?? [])
      .filter((d) => d.is_open)
      .map((d) => d.day)
      .sort((a, b) => a - b);
    const availableDays = days.length > 0 ? days : [1];

    return {
      designTheme: store.design_theme,
      width,
      depth,
      racks,
      doors,
      items,
      openHour,
      closeHour,
      minTime: openHour * 3600,
      maxTime: closeHour * 3600,
      availableDays,
    };
  }, [store]);
}
