import type { ReservedArea } from "@/shared/api/client";

export const AREA_POSITIONS = [
  ["back_left", "Back left"], ["back_right", "Back right"], ["center", "Center"],
  ["front_left", "Front left"], ["front_right", "Front right"],
] as const;
export type AreaPosition = typeof AREA_POSITIONS[number][0];

function validGrid([width, height]: [number, number]): boolean {
  return Number.isInteger(width) && width >= 8 && width <= 40 && Number.isInteger(height) && height >= 6 && height <= 40;
}

export function moveReservedArea(area: ReservedArea, grid: [number, number], position: AreaPosition): ReservedArea | null {
  if (!validGrid(grid) || !Number.isInteger(area.width) || !Number.isInteger(area.height) ||
    area.width < 1 || area.height < 1 || area.width > grid[0] - 2 || area.height > grid[1] - 2) return null;
  const right = grid[0] - area.width - 1;
  const front = grid[1] - area.height - 1;
  const positions = {
    back_left: [1, 1], back_right: [right, 1], front_left: [1, front], front_right: [right, front],
    center: [Math.floor((grid[0] - area.width) / 2), Math.floor((grid[1] - area.height) / 2)],
  } as const;
  const [x, y] = positions[position];
  return { ...area, x, y };
}

export function swapReservedAreaDimensions(area: ReservedArea, grid: [number, number]): ReservedArea | null {
  if (!validGrid(grid) || ![area.x, area.y, area.width, area.height].every((value) => Number.isInteger(value) && value >= 1) ||
    area.x + area.height > grid[0] - 1 || area.y + area.width > grid[1] - 1) return null;
  return { ...area, width: area.height, height: area.width };
}
