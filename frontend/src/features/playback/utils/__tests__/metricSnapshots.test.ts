import { describe, expect, it } from "vitest";
import type { CustomerResult, TimelineEvent } from "@/shared/types/domain";
import { buildDayCheckpoints, buildEventQueue, MetricsAccumulator } from "../eventQueue";

const event = (elapsed_sec: number, action: string, extra: Partial<TimelineEvent> = {}): TimelineEvent => ({
  elapsed_sec, action, x: 0, y: 0, duration: 0, target_rack: "rack", face: null,
  description: "", product_sku: "", product_name: "", price: 0, ...extra,
});
const shopper = (day: number, quantity: number): CustomerResult => ({
  persona_id: `p${day}`, day, arrival_time: "10:00:00", leave_time: "", total_spent: quantity * 100,
  timeline: [event(0, "enter"), event(1, "buy", { product_sku: "paid", product_name: "Paid", price: 100, quantity }),
    event(2, "pay"), event(3, "exit")],
});

describe("free purchases", () => {
  it.each([1, 2, 100, undefined].flatMap(quantity =>
    (["planned", "impulse"] as const).flatMap(origin => [false, true].map(mixed => ({ quantity, origin, mixed }))),
  ))("retains settled units for $quantity/$origin/mixed=$mixed", ({ quantity, origin, mixed }) => {
    const customer = shopper(1, 2);
    customer.timeline = [event(0, "enter"), event(1, "buy", {
      product_sku: "free", product_name: "Free", target_rack: "free-rack", price: 0, quantity, origin,
    }), ...(mixed ? [customer.timeline[1]!] : []), event(2, "pay"), event(3, "exit")];
    const acc = new MetricsAccumulator();
    for (const ev of buildEventQueue([customer])) acc.processEvent(ev);
    const snap = acc.snapshot();
    expect(snap.skuSales.find(s => s.sku === "free")).toMatchObject({ quantity: quantity ?? 1, revenue: 0 });
    expect(snap.rackMetrics.find(r => r.rackId === "free-rack")).toMatchObject({ revenue: 0, visitors: 1, visitorIds: ["p1"] });
    expect(snap).toMatchObject({ revenue: mixed ? 200 : 0, impulseRevenue: 0, paidCount: 1, entered: 1, exited: 1, inStore: 0 });
  });

  it("does not count an abandoned free item as a settled sale", () => {
    const customer = shopper(1, 1);
    customer.timeline[1] = event(1, "buy", { product_sku: "free", price: 0, quantity: 2 });
    customer.timeline.splice(2, 1);
    const acc = new MetricsAccumulator();
    for (const ev of buildEventQueue([customer])) acc.processEvent(ev);
    expect(acc.snapshot()).toMatchObject({ revenue: 0, paidCount: 0, skuSales: [], rackMetrics: [] });
  });
});

describe("playback metric snapshots", () => {
  it("keeps prior-day SKU totals consistent with prior-day revenue", () => {
    const checkpoints = buildDayCheckpoints([shopper(1, 1), shopper(2, 2), shopper(3, 3)], [1, 2, 3]);
    for (const [day, quantity] of [[1, 0], [2, 1], [3, 3]]) {
      const snap = checkpoints.get(day!)!;
      expect(snap.revenue).toBe(quantity! * 100);
      expect(snap.skuSales.reduce((sum, row) => sum + row.revenue, 0)).toBe(snap.revenue);
      expect(snap.skuSales.reduce((sum, row) => sum + row.quantity, 0)).toBe(quantity);
    }
  });

  it("keeps a saved snapshot stable as the same SKU is purchased again", () => {
    const acc = new MetricsAccumulator();
    for (const ev of buildEventQueue([shopper(1, 1)])) acc.processEvent(ev);
    const first = acc.snapshot();
    for (const ev of buildEventQueue([shopper(2, 2)])) acc.processEvent(ev);
    expect(first.skuSales[0]).toMatchObject({ quantity: 1, revenue: 100 });
    expect(acc.snapshot().skuSales[0]).toMatchObject({ quantity: 3, revenue: 300 });
    first.skuSales[0]!.quantity = 999;
    expect(acc.snapshot().skuSales[0]!.quantity).toBe(3);
  });

  it("restores a day checkpoint repeatedly without counting future sales", () => {
    const checkpoints = buildDayCheckpoints([shopper(1, 1), shopper(2, 2), shopper(3, 3)], [1, 2, 3]);
    const acc = new MetricsAccumulator();
    for (let seek = 0; seek < 3; seek++) {
      acc.loadSnapshot(checkpoints.get(2)!);
      expect(acc.snapshot().skuSales[0]).toMatchObject({ quantity: 1, revenue: 100 });
      for (const ev of buildEventQueue([shopper(2, 2)])) acc.processEvent(ev);
      expect(acc.snapshot()).toMatchObject({ revenue: 300, skuSales: [expect.objectContaining({ quantity: 3, revenue: 300 })] });
    }
    expect(checkpoints.get(2)!.skuSales[0]).toMatchObject({ quantity: 1, revenue: 100 });
  });
});
