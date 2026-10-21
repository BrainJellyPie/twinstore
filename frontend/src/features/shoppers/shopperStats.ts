// Per-shopper summaries for the picker, and interview questions suggested by a journey.

import type { CustomerResult, Persona } from "@/shared/types/domain";
import type { Journey } from "@/shared/api/interview";
import { parseTimeToSeconds } from "@/features/playback/utils/playback";

export interface ShopperRow {
  id: string;
  name: string;
  age: string;
  gender: string;
  day: number;
  arrival: string;
  spent: number;
  units: number;
  impulse: number;
  minutes: number;
  stops: number;
}

export type ShopperSort = "spent" | "nothing" | "impulse" | "longest";

export function shopperRows(customers: CustomerResult[], personas: Persona[]): ShopperRow[] {
  const byId = new Map(personas.map((p) => [p.id, p]));
  return customers.map((c) => {
    const p = byId.get(c.persona_id);
    let units = 0;
    let impulse = 0;
    let stops = 0;
    for (const e of c.timeline) {
      if (e.action === "buy") {
        units += e.quantity ?? 1;
        if (e.origin === "impulse") impulse += e.quantity ?? 1;
      }
      if (e.action === "browse") stops += 1;
    }
    const start = parseTimeToSeconds(c.arrival_time);
    const end = c.leave_time ? parseTimeToSeconds(c.leave_time) : start;
    return {
      id: c.persona_id, name: p?.identity ?? c.persona_id, age: p?.age_group ?? "", gender: p?.gender ?? "", day: c.day,
      arrival: c.arrival_time.slice(0, 5), spent: c.total_spent, units, impulse, minutes: Math.max(0, (end - start) / 60), stops,
    };
  });
}

export function sortShoppers(rows: ShopperRow[], sort: ShopperSort, query: string): ShopperRow[] {
  const q = query.trim().toLowerCase();
  const hit = q ? rows.filter((r) => r.id.toLowerCase().includes(q) || r.name.toLowerCase().includes(q)) : rows;
  const out = sort === "nothing" ? hit.filter((r) => r.units === 0 && r.stops > 0) : sort === "impulse" ? hit.filter((r) => r.impulse > 0) : [...hit];
  const key: Record<ShopperSort, (r: ShopperRow) => number> = {
    spent: (r) => -r.spent,
    nothing: (r) => -r.stops,
    impulse: (r) => -r.impulse,
    longest: (r) => -r.minutes,
  };
  return out.sort((a, b) => key[sort](a) - key[sort](b));
}

/** Questions a researcher would ask after this trip. */
export function suggestedQuestions(j: Journey): string[] {
  const out: string[] = [];
  const buys = j.steps.filter((s) => s.action === "buy");
  const impulse = buys.find((s) => s.origin === "impulse");
  const planned = buys.find((s) => s.origin !== "impulse");
  if (impulse) out.push(`What made you pick up the ${impulse.product_name}? Was it planned?`);
  if (planned) out.push(`Why that ${planned.product_name} and not another one on the shelf?`);
  const emptyStop = j.steps.find((s) => s.action === "browse" && !buys.some((b) => b.rack_id === s.rack_id));
  if (emptyStop) out.push(`You stopped at ${emptyStop.rack} but didn't buy anything there. Why?`);
  if (!buys.length) out.push("You left without buying anything. What was missing?");
  out.push("How did the prices feel to you today?");
  out.push("What would have made you spend more on this trip?");
  return out.slice(0, 4);
}
