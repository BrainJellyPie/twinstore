// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { OperationsLab } from "../OperationsLab";

vi.mock("@/shared/api/client", () => ({ replayOperations: vi.fn(), planOperations: vi.fn(), saveLayoutOperations: vi.fn() }));

const config: api.OperationsReport["config"] = {
  stock_per_facing: 8, stock_overrides: {}, till_schedule: {}, restock_every_min: 60, substitute_share: 0.45,
  open_counters: 2, checkout_base_sec: 25, checkout_item_sec: 3, patience_sec: 240, patience_sd: 0.5, target_wait_sec: 120, crowd_limit: 4, crowd_skip: 0.35, backroom_per_product: null, backroom_overrides: {}, daily_delivery: true,
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

const weeks = (shoppers: number[], net: number): api.WeeksReport => ({
  memory: { weeks: shoppers.length, leave_per_missing_unit: 0.03, leave_after_line: 0.25, leave_per_wait_minute: 0.01, weekly_churn: 0.01 },
  weeks: shoppers.map((n, i) => ({ week: i + 1, shoppers: n, revenue: n * 100, lost_revenue: 0, abandoned: 0, avg_wait_sec: 0,
    net: n * 50, left_for_stock: i === 0 ? 3 : 0, left_for_tills: i === 0 ? 1 : 0, left_anyway: 1, ideal_shoppers: 100 - i, ideal_revenue: (100 - i) * 100 })),
  shoppers_first: shoppers[0] ?? 0, shoppers_last: shoppers[shoppers.length - 1] ?? 0, revenue: 29000, net, ideal_revenue: 29700, lost_to_memory: 650,
});

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.replayOperations).mockResolvedValue({ planned_revenue: 100000, outcome: outcome(90000, 44100), report: report });
  vi.mocked(api.planOperations).mockResolvedValue({
    current_config: config, current: outcome(90000, 44100),
    config: { ...config, stock_per_facing: 6, restock_every_min: null, till_schedule: { "18": 3 }, stock_overrides: { cola: 24 } },
    best: outcome(97000, 52000), replays: 214, raised_skus: ["cola"],
  });
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

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

it("follows the weeks after with shoppers who remember", async () => {
  vi.mocked(api.replayOperations).mockResolvedValue({ planned_revenue: 100000, outcome: outcome(90000, 44100), report, weeks: weeks([100, 95, 94], 14500) });
  const lab = show();
  expect(lab.queryByLabelText("Weeks")).toBeNull();
  fireEvent.click(lab.getByLabelText("Shoppers remember: follow the weeks after"));
  fireEvent.change(lab.getByLabelText("Weeks"), { target: { value: "3" } });
  fireEvent.change(lab.getByLabelText("Stay away per unit found gone (%)"), { target: { value: "10" } });
  fireEvent.click(lab.getByRole("button", { name: "Replay" }));
  await waitFor(() => expect(api.replayOperations).toHaveBeenCalledWith("p", "r", expect.objectContaining({
    memory: { weeks: 3, leave_per_missing_unit: 0.1, leave_after_line: 0.25, leave_per_wait_minute: 0.01, weekly_churn: 0.01 },
  })));
  expect(await lab.findByText("Over 3 weeks: revenue $290.00 (ideal store: $297.00); shoppers who stayed away after a visit cost $6.50. Shoppers in week 1: 100; in week 3: 94.")).toBeTruthy();
  expect(lab.getByRole("rowheader", { name: "Week 2" })).toBeTruthy();
  expect(lab.getByRole("rowheader", { name: "Left after costs, all weeks" })).toBeTruthy();
  fireEvent.change(lab.getByLabelText("Weeks"), { target: { value: "1" } });
  expect(lab.getByRole("alert").textContent).toBe("Weeks are 2–52 and chances 0–100 %.");
  expect((lab.getByRole("button", { name: "Replay" }) as HTMLButtonElement).disabled).toBe(true);
});

it("judges a plan by its money over the weeks when shoppers remember", async () => {
  vi.mocked(api.planOperations).mockResolvedValue({
    current_config: config, current: outcome(90000, 44100), config: { ...config, stock_per_facing: 16 },
    best: outcome(90000, 40000), replays: 80, raised_skus: [], complete: true,
    current_weeks: weeks([100, 90, 80], 12000), best_weeks: weeks([100, 98, 97], 15000),
  });
  const lab = show();
  fireEvent.click(lab.getByLabelText("Shoppers remember: follow the weeks after"));
  fireEvent.click(lab.getByRole("button", { name: "Find the best plan" }));
  // Less on the first day, more over the weeks: the weeks decide.
  expect(await lab.findByText("The plan leaves $30.00 more after costs.")).toBeTruthy();
  expect(lab.getAllByRole("rowheader", { name: "Week 3" })).toHaveLength(1);
});

it("saves the edited plan as how the run's layout is run", async () => {
  vi.mocked(api.saveLayoutOperations).mockImplementation(async (_p, _s, operations) => ({ operations: operations as api.OperationsReport["config"] }));
  const lab = show({ setupId: "s1" });
  fireEvent.change(lab.getByLabelText("Units of each product per shelf level"), { target: { value: "20" } });
  fireEvent.click(lab.getByRole("button", { name: "Save for this layout" }));
  await waitFor(() => expect(api.saveLayoutOperations).toHaveBeenCalledWith("p", "s1", expect.objectContaining({ stock_per_facing: 20, open_counters: 2 })));
  expect(await lab.findByRole("status")).toBeTruthy();
  expect(lab.getByRole("status").textContent).toContain("now share the store run this way");
});

it("offers no saving without the run's layout", () => {
  const lab = show();
  expect(lab.queryByRole("button", { name: "Save for this layout" })).toBeNull();
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
    operations: { stock_per_facing: 12, restock_every_min: 120, open_counters: null, patience_sec: 300, crowd_limit: 4,
      backroom_per_product: null, daily_delivery: true, crew: null, till_schedule: {}, stock_overrides: {}, crew_schedule: {}, crew_shifts: [] },
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

it("staffs a crew hour by hour, costs a staff hour and plans the crew", async () => {
  const crewed = { config: { ...config, crew: 2, crew_schedule: { "17": 1 }, refill_at: 0.5 }, hours } as unknown as api.OperationsReport;
  vi.mocked(api.replayOperations).mockResolvedValue({ planned_revenue: 100000, outcome: { ...outcome(90000, 44100), crew_hours: 30 }, report: crewed });
  vi.mocked(api.planOperations).mockResolvedValue({
    current_config: crewed.config, current: { ...outcome(90000, 44100), crew_hours: 30 },
    config: { ...crewed.config, crew: 2, crew_schedule: { "18": 3 }, refill_at: 0.25 },
    best: { ...outcome(95000, 50000), crew_hours: 31 }, replays: 120, raised_skus: [],
  });
  const lab = show({ report: crewed });
  expect((lab.getByLabelText("Crew on duty (tills and shelves)") as HTMLInputElement).value).toBe("2");
  expect(lab.queryByLabelText("Tills open")).toBeNull();
  expect((lab.getByLabelText("Crew at 17:00") as HTMLInputElement).value).toBe("1");
  fireEvent.change(lab.getByLabelText("Crew at 18:00"), { target: { value: "3" } });
  fireEvent.change(lab.getByLabelText("One staff member for an hour"), { target: { value: "12" } });
  fireEvent.click(lab.getByRole("button", { name: "Replay" }));
  await waitFor(() => expect(api.replayOperations).toHaveBeenCalledWith("p", "r", expect.objectContaining({
    operations: expect.objectContaining({ crew: 2, refill_at: 0.5, crew_schedule: { "17": 1, "18": 3 } }),
    costs: { till_hour: 1200, restock_round: 0, stock_unit_day: 0 },
  })));
  expect(await lab.findByRole("rowheader", { name: "Staff hours" })).toBeTruthy();
  expect(lab.queryByRole("rowheader", { name: "Till hours" })).toBeNull();
  expect(lab.getByRole("rowheader", { name: "Shelves refilled" })).toBeTruthy();
  expect(lab.queryByRole("rowheader", { name: "Shelf refills" })).toBeNull();
  fireEvent.click(lab.getByRole("button", { name: "Find the best plan" }));
  expect(await lab.findByText("Crew on duty: 2 · Crew by hour: 18:00 3")).toBeTruthy();
  expect(lab.getByText(/Refill: at 25% of full/)).toBeTruthy();
  fireEvent.click(lab.getByRole("button", { name: "Use this plan" }));
  expect((lab.getByLabelText("Crew at 18:00") as HTMLInputElement).value).toBe("3");
  expect((lab.getByLabelText("Crew at 17:00") as HTMLInputElement).value).toBe("");
  // Clearing the crew goes back to tills on their own: no crew hours are sent.
  fireEvent.change(lab.getByLabelText("Crew on duty (tills and shelves)"), { target: { value: "" } });
  fireEvent.click(lab.getByRole("button", { name: "Replay" }));
  await waitFor(() => expect(api.replayOperations).toHaveBeenLastCalledWith("p", "r", expect.objectContaining({
    operations: expect.objectContaining({ crew: null, crew_schedule: {} }),
  })));
});

it("edits a roster of shifts by weekday and plans one", async () => {
  const crewed = { config: { ...config, crew: 2, crew_schedule: {}, refill_at: 0.5,
    crew_shifts: [{ start: 8, end: 16, days: [], staff: 1 }] }, hours } as unknown as api.OperationsReport;
  vi.mocked(api.planOperations).mockResolvedValue({
    current_config: crewed.config, current: { ...outcome(90000, 44100), crew_hours: 30 },
    config: { ...crewed.config, crew_shifts: [{ start: 8, end: 16, days: [], staff: 1 }, { start: 12, end: 20, days: [6, 7], staff: 2 }] },
    best: { ...outcome(95000, 50000), crew_hours: 31 }, replays: 120, raised_skus: [],
  });
  const lab = show({ report: crewed });
  // With shifts, the shifts decide who is on duty: no crew-by-hour fields.
  expect(lab.queryByLabelText("Crew at 17:00")).toBeNull();
  const first = lab.getByRole("group", { name: "Shift 1" });
  expect((within(first).getByLabelText("From") as HTMLInputElement).value).toBe("8");
  fireEvent.click(lab.getByRole("button", { name: "Add a shift" }));
  const second = lab.getByRole("group", { name: "Shift 2" });
  fireEvent.change(within(second).getByLabelText("From"), { target: { value: "16" } });
  fireEvent.change(within(second).getByLabelText("To"), { target: { value: "22" } });
  fireEvent.click(within(second).getByRole("button", { name: "Sat" }));
  expect(within(second).getByRole("button", { name: "Sat" }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(lab.getByRole("button", { name: "Replay" }));
  await waitFor(() => expect(api.replayOperations).toHaveBeenCalledWith("p", "r", expect.objectContaining({
    operations: expect.objectContaining({ crew_shifts: [{ start: 8, end: 16, days: [], staff: 1 }, { start: 16, end: 22, days: [6], staff: 1 }] }),
  })));
  // An impossible shift blocks replaying.
  fireEvent.change(within(second).getByLabelText("To"), { target: { value: "15" } });
  expect(lab.getByRole("alert").textContent).toContain("Check the shifts");
  expect((lab.getByRole("button", { name: "Replay" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(lab.getByRole("button", { name: "Remove shift 2" }));
  fireEvent.click(lab.getByLabelText("Plan a roster of shifts"));
  fireEvent.change(lab.getByLabelText("Longest shift (hours)"), { target: { value: "6" } });
  fireEvent.click(lab.getByRole("button", { name: "Find the best plan" }));
  await waitFor(() => expect(api.planOperations).toHaveBeenCalledWith("p", "r", expect.objectContaining({ roster: { min_hours: 4, max_hours: 6 } })));
  expect(await lab.findByText("Shifts: Every day 08:00–16:00 ×1 · Sat, Sun 12:00–20:00 ×2")).toBeTruthy();
  fireEvent.click(lab.getByRole("button", { name: "Use this plan" }));
  expect(lab.getByRole("group", { name: "Shift 2" })).toBeTruthy();
});


it.each(LOCALES.flatMap(({ code }) => ["replay", "plan", "mixed"].map(mode => ({ code, mode }))))(
  "keeps zero-hour crew results visible in $code ($mode)", async ({ code, mode }) => {
    useLocale.getState().setLocale(code);
    const crewConfig = { ...config, crew: 2, crew_schedule: { "17": 0, "18": 0 } };
    const crewReport = { ...report, config: crewConfig, crew_hours: 0, face_refills: 0 };
    const zero = { ...outcome(0, 0), crew_hours: 0, face_refills: 0, till_hours: 0, restocks: 0 };
    vi.mocked(api.replayOperations).mockResolvedValue({ planned_revenue: 100000, outcome: zero, report: crewReport });
    vi.mocked(api.planOperations).mockResolvedValue({
      current_config: mode === "mixed" ? config : crewConfig, current: zero,
      config: crewConfig, best: zero, replays: 1, raised_skus: [],
    });
    const lab = show({ report: crewReport });
    fireEvent.click(lab.getByRole("button", { name: translate(code, mode === "replay" ? "labReplay" : "labFindPlan") }));
    await lab.findByRole("columnheader", { name: translate(code, mode === "replay" ? "labReplayCol" : "labPlanCol") });
    expect(lab.getByRole("rowheader", { name: translate(code, "opsCrewHours") })).toBeTruthy();
    expect(lab.getByRole("rowheader", { name: translate(code, "opsFaceRefills") })).toBeTruthy();
    expect(Boolean(lab.queryByRole("rowheader", { name: translate(code, "labTillHours") }))).toBe(mode === "mixed");
    expect(Boolean(lab.queryByRole("rowheader", { name: translate(code, "labRefills") }))).toBe(mode === "mixed");
  });
