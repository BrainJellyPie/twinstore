// Shoppers waiting at the tills, drawn as a line instead of a heap on the till's tile.
// In a shared-store run a shopper reaches the till and waits `queue_wait_sec` before paying (or, having given up,
// stands that long and leaves). They are lined up behind the till in the order they arrived, away from the counter.

import type { CustomerResult } from "@/shared/types/domain";

export interface Point { x: number; y: number }
export interface Waiting extends Point { id: string; since: number }

/** Till position and seconds into the visit when this wait began, if the shopper is waiting at `rel`. */
export function waitingAt(customer: CustomerResult, rel: number): Omit<Waiting, "id"> | null {
  const wait = customer.queue_wait_sec ?? 0;
  if (wait <= 0) return null;
  const timeline = customer.timeline;
  if (customer.left_queue) {
    // The give-up stands in for the payment: the last stop of the visit before walking out.
    for (let i = timeline.length - 1; i >= 0; i--) {
      const event = timeline[i]!;
      if (event.action === "wander") {
        return rel >= event.elapsed_sec && rel < event.elapsed_sec + wait
          ? { x: event.x, y: event.y, since: event.elapsed_sec } : null;
      }
    }
    return null;
  }
  const pay = timeline.find((event) => event.action === "pay");
  if (!pay) return null;
  const since = pay.elapsed_sec - wait;
  return rel >= since && rel < pay.elapsed_sec ? { x: pay.x, y: pay.y, since } : null;
}

/** Where each waiting shopper stands: one behind another on their till's tile, leading away from the nearest
 *  counter, earliest first (the shopper at the till itself is being served). */
export function lineUp(waiting: Waiting[], counters: Point[], spacing = 0.55): Map<string, Point> {
  const lines = new Map<string, Waiting[]>();
  for (const w of waiting) {
    const key = `${w.x},${w.y}`;
    const line = lines.get(key) ?? [];
    line.push(w);
    lines.set(key, line);
  }
  const out = new Map<string, Point>();
  for (const line of lines.values()) {
    line.sort((a, b) => a.since - b.since || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const { x, y } = line[0]!;
    let dx = 0;
    let dy = 1;
    let best = Infinity;
    for (const c of counters) {
      const d = (x - c.x) ** 2 + (y - c.y) ** 2;
      if (d < best && d > 0) {
        best = d;
        const len = Math.sqrt(d);
        dx = (x - c.x) / len;
        dy = (y - c.y) / len;
      }
    }
    line.forEach((w, i) => out.set(w.id, { x: x + dx * spacing * (i + 1), y: y + dy * spacing * (i + 1) }));
  }
  return out;
}
