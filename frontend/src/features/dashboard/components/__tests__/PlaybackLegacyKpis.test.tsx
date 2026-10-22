// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import type { RunSummary } from "@/shared/api/client";
import type { Store } from "@/shared/types/domain";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { DashboardPanel } from "../DashboardPanel";

const store: Store = { id: "store", name: "Floor", type: "convenience", grid_size: [8, 8], weekly_schedule: [], racks: [] };
const legacy: RunSummary = { total_customers: 10, total_revenue: 5000, top_products: [], by_purpose: {}, by_identity: {}, by_age: {}, by_gender: {} };
const current: RunSummary = { ...legacy, currency: "USD", buyers: 5, conversion_rate: 0.5, impulse_revenue_share: 0.2 };

beforeEach(() => {
  useSimulationMetricsStore.getState().setMetrics({ entered: 10, paidCount: 10, revenue: 5000, impulseRevenue: 0 });
});
afterEach(() => { cleanup(); useSimulationMetricsStore.getState().reset(); });

// The live tiles come first; a current run's RunKpis repeats some labels below them.
function tile(label: string): string {
  return screen.getAllByText(label)[0]!.parentElement!.textContent!.replace(label, "");
}

function show(summary: RunSummary) {
  render(<DashboardPanel mode="playback" customers={null} minTime={28800} maxTime={72000} store={store} summary={summary} />);
}

it("shows no live conversion or impulse share for a run made before those KPIs", () => {
  show(legacy);
  expect(screen.getByText(/made by an older version/)).toBeTruthy();
  expect(tile("Converted")).toBe("—");
  expect(tile("Impulse share")).toBe("—");
  expect(tile("Avg. basket")).toBe("$5.00");
});

it("keeps the live conversion and impulse share for a current run", () => {
  show(current);
  expect(tile("Converted")).toBe("100%");
  expect(tile("Impulse share")).toBe("0%");
});

it("says the rack and item lists fill in as the day plays, and only reports no sales once it is over", () => {
  show(current);
  expect(screen.getByText("Racks fill in as shoppers pay during the day.")).toBeTruthy();
  expect(screen.getByText("Items fill in as shoppers pay during the day.")).toBeTruthy();
  expect(screen.queryByText(/No (rack|sales) data/)).toBeNull();
  act(() => useSimulationMetricsStore.getState().setMetrics({ finished: true }));
  expect(screen.getByText("No rack sales in this run.")).toBeTruthy();
  expect(screen.getByText("No sales in this run.")).toBeTruthy();
});
