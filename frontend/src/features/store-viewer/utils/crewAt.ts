// Where the crew is at a moment of playback: at a till, at a shelf refilling it, or waiting for work.

import type { CrewTask } from "@/shared/api/client";

export interface CrewPlan {
  tasks: CrewTask[];
  crew: number;                       // on duty unless the hour says otherwise
  schedule: Record<string, number>;   // "HH" → crew on duty
}

export type CrewDoing =
  | { member: number; kind: "till"; rackId: string }
  | { member: number; kind: "refill"; rackId: string; face: string; name: string }
  | { member: number; kind: "idle" };

/** Each member's tasks of each day, by start: found again with a binary search every frame. */
export function crewIndex(tasks: CrewTask[]): Map<string, CrewTask[]> {
  const index = new Map<string, CrewTask[]>();
  for (const task of tasks) {
    const key = `${task.day}:${task.member}`;
    const list = index.get(key) ?? [];
    list.push(task);
    index.set(key, list);
  }
  for (const list of index.values()) list.sort((a, b) => a.start - b.start);
  return index;
}

export function crewOnDuty(plan: Pick<CrewPlan, "crew" | "schedule">, second: number): number {
  const hour = String(Math.floor(second / 3600) % 24).padStart(2, "0");
  return plan.schedule[hour] ?? plan.crew;
}

/** What each crew member on duty is doing at `second` (clock seconds) of `day`. */
export function crewAt(index: Map<string, CrewTask[]>, plan: Pick<CrewPlan, "crew" | "schedule">, day: number, second: number): CrewDoing[] {
  const out: CrewDoing[] = [];
  for (let member = 0; member < crewOnDuty(plan, second); member++) {
    const list = index.get(`${day}:${member}`) ?? [];
    let lo = 0;
    let hi = list.length;
    while (lo < hi) {   // the first task starting after `second`
      const mid = (lo + hi) >> 1;
      if (list[mid]!.start <= second) lo = mid + 1;
      else hi = mid;
    }
    const task = lo > 0 ? list[lo - 1]! : null;
    if (task && second < task.end) {
      out.push(task.kind === "till" ? { member, kind: "till", rackId: task.rack_id }
        : { member, kind: "refill", rackId: task.rack_id, face: task.face, name: task.name || task.sku });
    } else {
      out.push({ member, kind: "idle" });
    }
  }
  return out;
}
