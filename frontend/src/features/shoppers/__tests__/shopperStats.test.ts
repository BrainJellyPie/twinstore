import { describe, expect, it } from "vitest";

import type { Journey } from "@/shared/api/interview";
import type { CustomerResult, Persona } from "@/shared/types/domain";

import { shopperRows, sortShoppers, suggestedQuestions } from "../shopperStats";

const ev = (action: string, extra: Partial<CustomerResult["timeline"][number]> = {}) => ({
  elapsed_sec: 0, x: 0, y: 0, action, duration: 0, target_rack: "", face: null, description: "", product_sku: "", product_name: "", price: 0, ...extra,
});

const customers: CustomerResult[] = [
  { persona_id: "A", day: 1, arrival_time: "09:00:00", leave_time: "09:03:00", total_spent: 500,
    timeline: [ev("enter"), ev("browse"), ev("buy", { quantity: 2, origin: "impulse" })] },
  { persona_id: "B", day: 2, arrival_time: "10:00:00", leave_time: "10:10:00", total_spent: 0, timeline: [ev("enter"), ev("browse"), ev("browse")] },
  { persona_id: "C", day: 1, arrival_time: "11:00:00", leave_time: "11:01:00", total_spent: 900, timeline: [ev("buy", { origin: "planned" })] },
];
const personas = [{ id: "A", identity: "Night-shift nurse", age_group: "30s", gender: "Female" }] as Persona[];

describe("shopper picker", () => {
  it("summarises trips", () => {
    const [a, b] = shopperRows(customers, personas);
    expect(a).toMatchObject({ name: "Night-shift nurse", units: 2, impulse: 2, minutes: 3, stops: 1 });
    expect(b).toMatchObject({ name: "B", units: 0, stops: 2, minutes: 10 });
  });

  it("sorts and filters", () => {
    const rows = shopperRows(customers, personas);
    expect(sortShoppers(rows, "spent", "").map((r) => r.id)).toEqual(["C", "A", "B"]);
    expect(sortShoppers(rows, "nothing", "").map((r) => r.id)).toEqual(["B"]);
    expect(sortShoppers(rows, "impulse", "").map((r) => r.id)).toEqual(["A"]);
    expect(sortShoppers(rows, "longest", "").map((r) => r.id)).toEqual(["B", "A", "C"]);
    expect(sortShoppers(rows, "spent", "nurse").map((r) => r.id)).toEqual(["A"]);
  });

  it("suggests questions from the journey", () => {
    const step = (index: number, action: string, extra: object = {}) => ({ index, action, rack_id: "", rack: "", product_name: "", origin: "", ...extra });
    const j = { steps: [step(1, "browse", { rack_id: "r1", rack: "Snacks 1" }), step(2, "buy", { rack_id: "r2", product_name: "Cola", origin: "impulse" })] } as unknown as Journey;
    const qs = suggestedQuestions(j);
    expect(qs[0]).toContain("Cola");
    expect(qs.some((q) => q.includes("Snacks 1"))).toBe(true);
    expect(qs.length).toBeLessThanOrEqual(4);
  });
});
