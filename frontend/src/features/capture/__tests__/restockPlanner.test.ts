import { describe, expect, it } from "vitest";

import type { AuditFinding, AuditReport } from "@/shared/api/client";
import { planRestocking, restockCsv, type RestockAssumptions } from "../restockPlanner";

const assumptions: RestockAssumptions = { tradingDays: 2, contributionMarginPercent: 25, overheadMinor: 100 };
const finding = (sku: string, loss: number | null, ci: [number, number] | null, level = 3): AuditFinding => ({
  kind: "missing", level, sku, name: `Product ${sku}`, expected: "1 facing", found: "none", box: null, loss_per_day: loss, loss_ci: ci,
});
const report = (findings: AuditFinding[]) => ({
  job_id: "audit1", capture_id: "capture1", setup_id: "setup1", rack_id: "rack1", face: "N", currency: "USD",
  compliance: 0.5, levels: [], findings, impact: null, visitors_per_day: 100, revenue_delta_per_day: -1000,
  revenue_delta_ci: [-1200, -800], panel_size: 100, notes: [], seconds: 1,
}) satisfies AuditReport;

describe("restocking decisions", () => {
  it("applies the margin to recoverable revenue and subtracts overhead once", () => {
    const { actions, error } = planRestocking(report([finding("A", 1000, [800, 1200])]), assumptions);
    expect(error).toBeNull();
    expect(actions[0]).toMatchObject({ revenueOverHorizon: 2000, netContribution: 400, netInterval: [300, 500],
      paybackTradingDays: 0.4, evidence: "positive_lower_bound" });
  });

  it("deduplicates a SKU missing on several levels instead of adding its effect", () => {
    const { actions } = planRestocking(report([finding("A", 1000, [800, 1200]), finding("A", 1000, [800, 1200], 1)]), assumptions);
    expect(actions).toHaveLength(1);
    expect(actions[0]?.levels).toEqual([3, 1]);
    expect(actions[0]?.netContribution).toBe(400);
  });

  it("prioritizes positive lower bounds and preserves uncertainty and unestimated items", () => {
    const { actions } = planRestocking(report([
      finding("unknown", null, null), finding("uncertain", 5000, [-100, 10000]),
      finding("negative", -100, [-200, -20]), finding("positive", 1000, [800, 1200]),
      finding("no_ci", 3000, null),
    ]), assumptions);
    expect(actions.map((a) => a.sku)).toEqual(["positive", "uncertain", "no_ci", "negative", "unknown"]);
    expect(actions.find((a) => a.sku === "negative")?.netContribution).toBe(-150);
    expect(actions.find((a) => a.sku === "negative")?.paybackTradingDays).toBeNull();
    expect(actions[actions.length - 1]?.netContribution).toBeNull();
  });

  it("can overturn a positive revenue estimate when handling costs exceed contribution", () => {
    const plan = planRestocking(report([finding("A", 1000, [800, 1200])]), { ...assumptions, overheadMinor: 1000 });
    expect(plan.actions[0]).toMatchObject({ netContribution: -500, netInterval: [-600, -400], evidence: "nonpositive_interval" });
    const zeroMargin = planRestocking(report([finding("A", 1000, [800, 1200])]), { ...assumptions, contributionMarginPercent: 0 });
    expect(zeroMargin.actions[0]).toMatchObject({ netContribution: -100, paybackTradingDays: null });
  });

  it.each([
    { tradingDays: 0 }, { tradingDays: Infinity }, { contributionMarginPercent: -1 },
    { contributionMarginPercent: 101 }, { overheadMinor: 0.5 }, { overheadMinor: NaN }, { overheadMinor: -1 },
  ])("rejects unusable planning assumptions: %s", (bad) => {
    expect(planRestocking(report([]), { ...assumptions, ...bad }).error).not.toBeNull();
  });

  it("exports source IDs and assumptions with safe spreadsheet names and blank unknown effects", () => {
    const audit = report([{ ...finding("A", null, null), name: '=HYPERLINK("test")' }]);
    const csv = restockCsv(audit, planRestocking(audit, assumptions).actions, assumptions);
    expect(csv).toContain('"audit1","capture1","setup1","rack1","N","USD"');
    expect(csv).toContain('"\'=HYPERLINK(""test"")"');
    expect(csv).toContain(',2,25,100,,,,,,,"not_estimated"');
  });
});
