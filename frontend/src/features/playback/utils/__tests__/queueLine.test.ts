import { describe, expect, it } from "vitest";
import type { CustomerResult, TimelineEvent } from "@/shared/types/domain";
import { lineUp, waitingSince } from "../queueLine";

const event = (elapsed_sec: number, action: TimelineEvent["action"], duration = 0): TimelineEvent =>
  ({ elapsed_sec, x: 4, y: 2, action, duration } as TimelineEvent);

function shopper(timeline: TimelineEvent[], extra: Partial<CustomerResult> = {}): CustomerResult {
  return { persona_id: "p", day: 1, arrival_time: "10:00:00", leave_time: "", timeline, total_spent: 0, ...extra };
}

describe("waitingSince", () => {
  const paid = shopper([event(0, "enter"), event(40, "move"), event(100, "pay", 30), event(140, "exit")], { queue_wait_sec: 60 });

  it("is the moment the shopper reached the till, while they wait to pay", () => {
    expect(waitingSince(paid, 39)).toBeNull();
    expect(waitingSince(paid, 40)).toBe(40);
    expect(waitingSince(paid, 99)).toBe(40);
    expect(waitingSince(paid, 100)).toBeNull();   // being served now
  });

  it("covers a shopper who gave up for as long as they stood there", () => {
    const left = shopper([event(0, "enter"), event(40, "wander", 90), event(140, "exit")], { queue_wait_sec: 90, left_queue: true });
    expect(waitingSince(left, 40)).toBe(40);
    expect(waitingSince(left, 129)).toBe(40);
    expect(waitingSince(left, 130)).toBeNull();
  });

  it("is null for a shopper who never waited, or a run without the shared store", () => {
    expect(waitingSince(shopper([event(0, "enter"), event(50, "pay")]), 49)).toBeNull();
    expect(waitingSince(shopper([event(0, "enter"), event(50, "pay")], { queue_wait_sec: 0 }), 49)).toBeNull();
  });
});

describe("lineUp", () => {
  it("lines shoppers up behind the till, away from the counter, earliest first", () => {
    const spots = lineUp([
      { id: "late", x: 4, y: 2, since: 30 },
      { id: "early", x: 4, y: 2, since: 10 },
      { id: "other till", x: 8, y: 2, since: 20 },
    ], [{ x: 4, y: 1 }, { x: 8, y: 1 }], 0.5);
    expect(spots.get("early")).toEqual({ x: 4, y: 2.5 });
    expect(spots.get("late")).toEqual({ x: 4, y: 3 });
    expect(spots.get("other till")).toEqual({ x: 8, y: 2.5 });
  });

  it("keeps a straight line toward the back of the store with no counter to lean on", () => {
    const spots = lineUp([{ id: "a", x: 3, y: 3, since: 0 }, { id: "b", x: 3, y: 3, since: 1 }], [], 1);
    expect([spots.get("a"), spots.get("b")]).toEqual([{ x: 3, y: 4 }, { x: 3, y: 5 }]);
  });
});
