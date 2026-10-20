import { describe, expect, it } from "vitest";
import type { CustomerResult } from "@/shared/types/domain";
import { MetricsAccumulator, buildEventQueue } from "../eventQueue";

const ev = (elapsed_sec: number, action: string, extra: Partial<CustomerResult["timeline"][number]> = {}) => ({
  elapsed_sec, x: 0, y: 0, action, duration: 0, target_rack: "R1", face: null,
  description: "", product_sku: "", product_name: "", price: 0, ...extra,
});

describe("MetricsAccumulator", () => {
  it("counts quantities and impulse revenue", () => {
    const customer: CustomerResult = {
      persona_id: "p1", day: 1, arrival_time: "10:00:00", leave_time: "", total_spent: 0,
      timeline: [
        ev(0, "enter"),
        ev(5, "buy", { product_sku: "a", product_name: "A", price: 100, quantity: 3, origin: "planned" }),
        ev(9, "buy", { product_sku: "b", product_name: "B", price: 250, origin: "impulse" }),
        ev(20, "pay"),
        ev(30, "exit"),
      ],
    };
    const acc = new MetricsAccumulator();
    for (const e of buildEventQueue([customer])) acc.processEvent(e);
    const snap = acc.snapshot();
    expect(snap.revenue).toBe(3 * 100 + 250);
    expect(snap.impulseRevenue).toBe(250);
    expect(snap.skuSales.find((s) => s.sku === "a")?.quantity).toBe(3);
    expect(snap.paidCount).toBe(1);
  });

  it("treats runs without quantity as one unit per line", () => {
    const customer: CustomerResult = {
      persona_id: "p2", day: 1, arrival_time: "10:00:00", leave_time: "", total_spent: 0,
      timeline: [ev(0, "enter"), ev(3, "buy", { product_sku: "a", price: 100 }), ev(9, "pay")],
    };
    const acc = new MetricsAccumulator();
    for (const e of buildEventQueue([customer])) acc.processEvent(e);
    expect(acc.snapshot().revenue).toBe(100);
  });
});
