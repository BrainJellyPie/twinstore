// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { OperationsLab } from "../OperationsLab";

vi.mock("@/shared/api/client", () => ({ replayOperations: vi.fn(), planOperations: vi.fn() }));

const config: api.OperationsReport["config"] = {
  stock_per_facing: 8, stock_overrides: {}, till_schedule: {}, restock_every_min: 60, substitute_share: 0.45,
  open_counters: 2, checkout_base_sec: 25, checkout_item_sec: 3, patience_sec: 240, patience_sd: 0.5, target_wait_sec: 120,
};
const hours: api.QueueHour[] = [
  { hour: "17", arrivals: 30, avg_wait_sec: 40, max_wait_sec: 90, abandoned: 0, counters_needed: 1 },
  { hour: "18", arrivals: 50, avg_wait_sec: 260, max_wait_sec: 420, abandoned: 6, counters_needed: 3 },
];
const report = { config, hours } as unknown as api.OperationsReport;
const outcome = (revenue: number, net: number): api.OperationsOutcome => ({
  revenue, lost_revenue: 1200, abandoned_revenue: 800, abandoned: 3, avg_wait_sec: 95, p90_wait_sec: 200,
  till_hours: 28, restocks: 6, stock_units: 900, labor_cost: 42000, restock_cost: 3000, holding_cost: 900, net,
});

beforeEach(() => {
  vi.mocked(api.replayOperations).mockResolvedValue({ planned_revenue: 100000, outcome: outcome(90000, 44100), report: report });
  vi.mocked(api.planOperations).mockResolvedValue({
    current_config: config, current: outcome(90000, 44100),
    config: { ...config, stock_per_facing: 6, restock_every_min: null, till_schedule: { "18": 3 }, stock_overrides: { cola: 24 } },
    best: outcome(97000, 52000), replays: 214, raised_skus: ["cola"],
  });
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); });

function show(props: Partial<Parameters<typeof OperationsLab>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><OperationsLab projectId="p" runId="r" report={report} currency="USD_CENTS" {...props} /></QueryClientProvider>);
  const lab = screen.getByTestId("operations-lab") as HTMLDetailsElement;
  lab.open = true;
  return within(lab);
}

it("replays the run under the edited plan and says how much of the planned spend it keeps", async () => {
  const lab = show();
  expect((lab.getByLabelText("Units of each product per shelf level") as HTMLInputElement).value).toBe("8");
  expect((lab.getByLabelText("Tills open") as HTMLInputElement).value).toBe("2");
  fireEvent.change(lab.getByLabelText("Tills at 18:00"), { target: { value: "4" } });
  fireEvent.change(lab.getByLabelText("One till staffed for an hour"), { target: { value: "15.50" } });
  fireEvent.click(lab.getByRole("button", { name: "Replay" }));
  await waitFor(() => expect(api.replayOperations).toHaveBeenCalledWith("p", "r", {
    operations: expect.objectContaining({ stock_per_facing: 8, restock_every_min: 60, open_counters: 2, patience_sec: 240,
      till_schedule: { "18": 4 }, stock_overrides: {}, substitute_share: 0.45 }),
    costs: { till_hour: 1550, restock_round: 0, stock_unit_day: 0 },
  }));
  expect(await lab.findByText("Shoppers meant to spend $1,000.00; this plan keeps $900.00 (90%).")).toBeTruthy();
  expect(lab.getByRole("columnheader", { name: "Replay" })).toBeTruthy();
  expect(lab.getByRole("rowheader", { name: "Left after costs" })).toBeTruthy();
});

it("finds a plan, explains it and puts it in the form", async () => {
  const lab = show();
  fireEvent.click(lab.getByRole("button", { name: "Find the best plan" }));
  expect(await lab.findByText("The plan leaves $79.00 more after costs.")).toBeTruthy();
  expect(lab.getByText("Units per shelf level: 6 · Refill: only overnight · Products given more stock: 1 · Plans tried: 214")).toBeTruthy();
  expect(lab.getByText("Tills by hour: 18:00 3")).toBeTruthy();
  expect(lab.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Try other stock and staffing", "Now", "Plan"]);
  fireEvent.click(lab.getByRole("button", { name: "Use this plan" }));
  expect((lab.getByLabelText("Units of each product per shelf level") as HTMLInputElement).value).toBe("6");
  expect((lab.getByLabelText("Refill shelves every (minutes)") as HTMLInputElement).value).toBe("");
  expect((lab.getByLabelText("Tills at 18:00") as HTMLInputElement).value).toBe("3");
  fireEvent.click(lab.getByRole("button", { name: "Replay" }));
  await waitFor(() => expect(api.replayOperations).toHaveBeenCalledWith("p", "r", expect.objectContaining({
    operations: expect.objectContaining({ stock_per_facing: 6, restock_every_min: null, till_schedule: { "18": 3 }, stock_overrides: { cola: 24 } }),
  })));
});

it("says when the plan search stopped at its time limit", async () => {
  vi.mocked(api.planOperations).mockResolvedValue({
    current_config: config, current: outcome(90000, 44100), config, best: outcome(90000, 44100), replays: 40,
    raised_skus: [], complete: false,
  });
  const lab = show();
  fireEvent.click(lab.getByRole("button", { name: "Find the best plan" }));
  expect(await lab.findByText("The search stopped at its time limit; this is the best plan it found.")).toBeTruthy();
  expect(lab.getByText("No plan tried leaves more after costs than the current one.")).toBeTruthy();
});

it("refuses a cost that is not an amount of money", () => {
  const lab = show();
  fireEvent.change(lab.getByLabelText("One round of refilling the shelves"), { target: { value: "-3" } });
  expect(lab.getByRole("alert").textContent).toBe("Enter costs as amounts of zero or more.");
  expect((lab.getByRole("button", { name: "Replay" }) as HTMLButtonElement).disabled).toBe(true);
  expect((lab.getByRole("button", { name: "Find the best plan" }) as HTMLButtonElement).disabled).toBe(true);
});

it("starts a run whose shoppers had the store alone from the default store", async () => {
  const lab = show({ report: null, currency: "KRW" });
  expect(lab.getByText(/every shopper had the store to themselves/)).toBeTruthy();
  expect(lab.queryByLabelText("Tills at 18:00")).toBeNull();
  fireEvent.change(lab.getByLabelText("One unit kept on the shelves for a day"), { target: { value: "5" } });
  fireEvent.click(lab.getByRole("button", { name: "Replay" }));
  await waitFor(() => expect(api.replayOperations).toHaveBeenCalledWith("p", "r", {
    operations: { stock_per_facing: 12, restock_every_min: 120, open_counters: null, patience_sec: 300, till_schedule: {}, stock_overrides: {} },
    costs: { till_hour: 0, restock_round: 0, stock_unit_day: 5 },
  }));
  // The replayed hours can then be staffed one by one.
  expect(await lab.findByLabelText("Tills at 17:00")).toBeTruthy();
});

it.each(LOCALES)("reads in $code", ({ code }) => {
  useLocale.getState().setLocale(code);
  const lab = show();
  for (const key of ["labReplay", "labFindPlan", "labTillHourCost", "labRestockCost", "labUnitDayCost"] as const) {
    expect(lab.getAllByText(translate(code, key)).length).toBeGreaterThan(0);
  }
});
