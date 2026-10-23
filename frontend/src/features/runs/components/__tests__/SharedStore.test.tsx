// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { RunLauncherDialog } from "../RunLauncherDialog";
import { choiceFromConfig, DEFAULT_SHARED_STORE, sharedStoreOptions } from "../../sharedStore";
import { OperationsReportView, OperationsSection } from "../OperationsSection";

vi.mock("@/shared/api/client", () => ({
  getEngines: vi.fn(), getTown: vi.fn(), getModels: vi.fn(), startRun: vi.fn(), estimateRun: vi.fn(),
  getModelSetup: vi.fn(), getRunOperations: vi.fn(), getLayoutOperations: vi.fn(),
}));
vi.mock("../ScenarioEditor", () => ({ ScenarioEditor: () => <div>Situation editor</div> }));

const engines: api.EngineInfo[] = [
  { engine_type: "rule_based", label: "Rules", description: "", uses_llm: false, model: "", default: true },
];
const quick: api.RunEstimate = { customers: 100, days: 1, per_day: 100, engine: "rule_based", model: "", local: false, model_calls: 0, minutes: 1, cost_usd: null, warn: false };

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getEngines).mockResolvedValue(engines);
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.estimateRun).mockResolvedValue(quick);
  vi.mocked(api.getModelSetup).mockRejectedValue(new Error("Not needed"));
  vi.mocked(api.startRun).mockResolvedValue({ project_id: "p", run_id: "r", setup_id: "s" });
  vi.mocked(api.getLayoutOperations).mockResolvedValue({ operations: null });
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}
function showDialog() {
  render(<QueryClientProvider client={client()}><RunLauncherDialog open onOpenChange={vi.fn()} projectId="p" setupId="s" personaCount={100} defaultEngine="rule_based" /></QueryClientProvider>);
}
async function submitNow() { await act(async () => { fireEvent.submit(document.querySelector("form")!); }); }
async function submit() {
  await waitFor(() => expect(screen.queryByText(translate(useLocale.getState().locale, "opsLayoutLoading"))).toBeNull());
  await submitNow();
}

describe("the run option", () => {
  it("shares the store by default, refilling every two hours with every till open", () => {
    expect(sharedStoreOptions(DEFAULT_SHARED_STORE)).toEqual({
      stock_per_facing: 12, restock_every_min: 120, open_counters: null, patience_sec: 300, crowd_limit: 4,
      backroom_per_product: null, daily_delivery: true, crew: null,
    });
  });

  it("reads blank refill and tills as overnight and every till, and turning it off sends nothing", () => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, restock: " ", tills: "", patience: "1.5", crowd: "" }))
      .toEqual({ stock_per_facing: 12, restock_every_min: null, open_counters: null, patience_sec: 90, crowd_limit: null,
        backroom_per_product: null, daily_delivery: true, crew: null });
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, enabled: false, stock: "nonsense" })).toBeUndefined();
  });

  it.each([
    { stock: "0" }, { stock: "1.5" }, { stock: "" }, { stock: "10001" }, { restock: "4" }, { restock: "1441" },
    { tills: "0" }, { tills: "51" }, { tills: "2.5" }, { patience: "0.1" }, { patience: "121" }, { patience: "" },
    { patience: "NaN" }, { patience: "Infinity" },
    { crowd: "1" }, { crowd: "51" }, { crowd: "3.5" }, { backroom: "-1" }, { backroom: "1000001" }, { backroom: "2.5" },
  ])("refuses %o", (patch) => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, ...patch })).toBe("invalid");
  });

  it.each([
    { stock: "1" }, { stock: "10000" }, { restock: "5" }, { restock: "1440" }, { tills: "1" }, { tills: "50" },
    { patience: String(10 / 60) }, { patience: "0.4" }, { patience: "120" }, { crowd: "2" }, { crowd: "50" }, { backroom: "0" }, { backroom: "1000000" },
  ])("accepts the boundary %o", (patch) => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, ...patch })).not.toBe("invalid");
  });

  it.each([[10, 0.125], [10.5, 0.005], [31, 0.333], [31.25, 0.555], [7200, 0.95], [300, 0]])(
    "round trips saved patience %s seconds and refill point %s", (patience, refill) => {
      const parsed = sharedStoreOptions(choiceFromConfig({ patience_sec: patience, refill_at: refill, crew: 2 }));
      expect(parsed).not.toBe("invalid");
      expect(parsed).toBeDefined();
      if (!parsed || parsed === "invalid") throw new Error("valid saved settings were rejected");
      expect(parsed.patience_sec).toBeCloseTo(patience, 10);
      expect(parsed.refill_at).toBeCloseTo(refill, 10);
    },
  );
});

describe("the run dialog", () => {
  it.each([false, true])("waits for the layout settings before starting (saved=%s)", async saved => {
    let finish!: (value: { operations: api.OperationsReport["config"] | null }) => void;
    vi.mocked(api.getLayoutOperations).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    showDialog();
    await submitNow();
    expect(api.startRun).not.toHaveBeenCalled();
    await act(async () => { finish({ operations: saved ? { ...report.config, stock_per_facing: 7,
      stock_overrides: { cola: 0 }, till_schedule: { "18": 0 } } : null }); });
    await waitFor(() => expect((screen.getByLabelText("Units of each product per shelf level") as HTMLInputElement).value).toBe(saved ? "7" : "12"));
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({
      operations: expect.objectContaining(saved ? { stock_per_facing: 7, stock_overrides: { cola: 0 }, till_schedule: { "18": 0 } }
        : { stock_per_facing: 12 }),
    })));
  });

  it("retries unreadable layout settings before starting with the saved plan", async () => {
    vi.mocked(api.getLayoutOperations).mockRejectedValueOnce(new Error("Connection interrupted"))
      .mockResolvedValue({ operations: { ...report.config, stock_per_facing: 7 } });
    showDialog();
    await waitFor(() => expect(api.getLayoutOperations).toHaveBeenCalledTimes(1));
    await submit();
    expect(api.startRun).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    await screen.findByText("Starting from this layout's saved operations.");
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({
      operations: expect.objectContaining({ stock_per_facing: 7 }),
    })));
  });

  it("starts a run whose shoppers share the store", async () => {
    showDialog();
    expect((screen.getByLabelText("Shoppers share the store") as HTMLInputElement).checked).toBe(true);
    fireEvent.change(screen.getByLabelText("Tills open"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Units of each product per shelf level"), { target: { value: "4" } });
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({
      operations: { stock_per_facing: 4, restock_every_min: 120, open_counters: 2, patience_sec: 300, crowd_limit: 4,
        backroom_per_product: null, daily_delivery: true, crew: null, crew_schedule: {}, crew_shifts: [] },
    })));
  });

  it("starts the old way with the option off, whatever the layout saved", async () => {
    showDialog();
    fireEvent.click(screen.getByLabelText("Shoppers share the store"));
    expect(screen.queryByLabelText("Tills open")).toBeNull();
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ operations: undefined, shared_store: false })));
  });

  it("starts from the layout's saved operations and keeps the settings the dialog has no field for", async () => {
    vi.mocked(api.getLayoutOperations).mockResolvedValue({ operations: { ...report.config, stock_per_facing: 6,
      till_schedule: { "18": 3 }, stock_overrides: { cola: 24 } } });
    showDialog();
    expect(await screen.findByText("Starting from this layout's saved operations.")).toBeTruthy();
    expect((screen.getByLabelText("Units of each product per shelf level") as HTMLInputElement).value).toBe("6");
    fireEvent.change(screen.getByLabelText("Tills open"), { target: { value: "2" } });
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({
      shared_store: undefined,
      operations: expect.objectContaining({ stock_per_facing: 6, open_counters: 2, till_schedule: { "18": 3 }, stock_overrides: { cola: 24 } }),
    })));
  });

  it("blocks the run until an impossible setting is corrected", async () => {
    showDialog();
    fireEvent.change(screen.getByLabelText("Tills open"), { target: { value: "0" } });
    expect(screen.getByRole("alert").textContent).toContain("Check the store settings");
    await submit();
    expect(api.startRun).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Tills open"), { target: { value: "" } });
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalled());
  });

  it.each(LOCALES)("names every control in $code", ({ code }) => {
    useLocale.getState().setLocale(code);
    showDialog();
    for (const key of ["opsShareTitle", "opsStockPerFacing", "opsRestockEvery", "opsTillsOpen", "opsPatience", "opsCrowd", "opsBackroom"] as const) {
      expect(screen.getByLabelText(translate(code, key))).toBeTruthy();
    }
  });
});

const report: api.OperationsReport = {
  config: {
    stock_per_facing: 12, stock_overrides: {}, till_schedule: {}, restock_every_min: 120, substitute_share: 0.45, open_counters: null,
    checkout_base_sec: 25, checkout_item_sec: 3, patience_sec: 300, patience_sd: 0.5, target_wait_sec: 120, crowd_limit: 4, crowd_skip: 0.35, backroom_per_product: null, backroom_overrides: {}, daily_delivery: true,
  },
  days: 1, counters: 1, counters_in_layout: 2, stockout_faces: 9, shoppers_hit: 14,
  lost_units: 23, lost_revenue: 4560, substituted_units: 11, substituted_revenue: 2200, restocks: 3,
  queued: 80, avg_wait_sec: 140, p90_wait_sec: 300, max_wait_sec: 420, abandoned: 6, abandoned_units: 15,
  abandoned_revenue: 3100, counter_utilization: 0.83, counters_needed: 3,
  hours: [
    { hour: "17", arrivals: 30, avg_wait_sec: 40, max_wait_sec: 90, abandoned: 0, counters_needed: 1 },
    { hour: "18", arrivals: 50, avg_wait_sec: 260, max_wait_sec: 420, abandoned: 6, counters_needed: 3 },
  ],
  stockouts: Array.from({ length: 10 }, (_, i) => ({
    sku: `sku${i}`, name: `Product ${i}`, rack_id: `r${i}`, rack_name: `Shelf ${i}`, stock: 12, sold_units: 12,
    lost_units: i === 0 ? 5 : 0, lost_revenue: i === 0 ? 1000 : 0, substituted_units: i === 0 ? 2 : 0,
    shoppers_missed: 3, first_out: "18:05:10", minutes_out: 47.5,
  })),
};

describe("the results", () => {
  it.each([1, 5])("uses observed waiting time when the default capacity is %s", counters => {
    render(<OperationsReportView report={{ ...report, counters, counters_needed: 1, hours: [
      { hour: "10", arrivals: 4, avg_wait_sec: 180, max_wait_sec: 240, abandoned: 0, counters_needed: 1, counters_open: 1 },
    ] }} />);
    expect(screen.queryByText(/kept every hour's average wait under/)).toBeNull();
    expect(screen.getByText("At 10:00, average wait was 3 min, above the 2 min target. Review checkout staffing and refill work.")).toBeTruthy();
  });

  it("reports the largest observed delay even when another hour needs more theoretical tills", () => {
    render(<OperationsReportView report={{ ...report, counters: 5, counters_needed: 8, hours: [
      { hour: "10", arrivals: 80, avg_wait_sec: 90, max_wait_sec: 180, abandoned: 10, counters_needed: 8, counters_open: 5 },
      { hour: "11", arrivals: 3, avg_wait_sec: 300, max_wait_sec: 400, abandoned: 0, counters_needed: 1, counters_open: 1 },
    ] }} />);
    expect(screen.getByText("At 11:00, average wait was 5 min, above the 2 min target. Review checkout staffing and refill work.")).toBeTruthy();
  });

  it.each([0, 119.9, 120])("reports a met target from observed wait %s even when more tills are recommended", wait => {
    render(<OperationsReportView report={{ ...report, counters: 1, counters_needed: 8, hours: [
      { hour: "10", arrivals: 80, avg_wait_sec: wait, max_wait_sec: 180, abandoned: 30, counters_needed: 8, counters_open: 1 },
    ] }} />);
    expect(screen.getByText("Every recorded hour's average wait stayed within 2 min.")).toBeTruthy();
  });

  it("say what sharing the store cost and how many tills the busiest hour needed", () => {
    render(<OperationsReportView report={report} currency="USD_CENTS" />);
    expect(screen.getByText("Store operations")).toBeTruthy();
    expect(screen.getByText("$45.60")).toBeTruthy();
    expect(screen.getByText("Units: 11")).toBeTruthy();
    expect(screen.getByText("2.3 min")).toBeTruthy();
    expect(screen.getByText("At 18:00, average wait was 4.3 min, above the 2 min target. Review checkout staffing and refill work.")).toBeTruthy();
    expect(screen.getAllByText("Out at 18:05 · empty 47.5 min")).toHaveLength(8);
    expect(screen.getByText("Lost: 5 · $10.00")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(9);
    expect(screen.getByText("Other products that ran out: 2")).toBeTruthy();
    expect(screen.getAllByRole("row")).toHaveLength(3);
  });

  it("say the tills were enough when they were", () => {
    render(<OperationsReportView report={{ ...report, counters: 3, counters_needed: 3, stockouts: [],
      hours: report.hours.map(hour => ({ ...hour, avg_wait_sec: 60 })) }} />);
    expect(screen.getByText("Every recorded hour's average wait stayed within 2 min.")).toBeTruthy();
    expect(screen.getByText("No product ran out.")).toBeTruthy();
  });

  it("explain a layout without tills", () => {
    render(<OperationsReportView report={{ ...report, counters: 0, counters_in_layout: 0, hours: [] }} />);
    expect(screen.getByText("This layout has no tills, so nobody waited in line.")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it.each([0, 120])("shows a small excess over %s seconds without rounding it into the target", target => {
    render(<OperationsReportView report={{ ...report, config: { ...report.config, target_wait_sec: target },
      hours: [{ ...report.hours[0]!, avg_wait_sec: target + 0.1 }] }} />);
    expect(screen.getByText(new RegExp(`average wait was ${target + 0.1} s, above`))).toBeTruthy();
  });

  it.each([0, 1, 3, undefined])("compares needed capacity with that hour's open tills (%s), including legacy fallback", open => {
    render(<OperationsReportView report={{ ...report, counters: 3,
      hours: [{ ...report.hours[0]!, counters_needed: 2, counters_open: open }] }} />);
    const row = screen.getAllByRole("row")[1]!;
    expect(within(row).getByText("2").classList.contains("text-destructive")).toBe((open ?? 3) < 2);
  });

  it.each(LOCALES)("read in $code", ({ code }) => {
    useLocale.getState().setLocale(code);
    render(<OperationsReportView report={report} currency="USD_CENTS" />);
    expect(screen.getByText(translate(code, "opsTitle"))).toBeTruthy();
    expect(screen.getByText(translate(code, "opsHoursTitle"))).toBeTruthy();
    expect(screen.getByText(translate(code, "opsCapacityHint"))).toBeTruthy();
    expect(screen.getByText(translate(code, "opsStockoutsTitle"))).toBeTruthy();
  });

  it("are left out for a run whose shoppers each had the store alone", async () => {
    vi.mocked(api.getRunOperations).mockRejectedValue(new ApiError("not shared", 404));
    const { container } = render(<QueryClientProvider client={client()}><OperationsSection projectId="p" runId="r" /></QueryClientProvider>);
    await waitFor(() => expect(api.getRunOperations).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("load for a shared-store run", async () => {
    vi.mocked(api.getRunOperations).mockResolvedValue(report);
    render(<QueryClientProvider client={client()}><OperationsSection projectId="p" runId="r" currency="USD_CENTS" /></QueryClientProvider>);
    expect(await screen.findByText("Store operations")).toBeTruthy();
  });
});


describe("the backroom", () => {
  it("is endless unless given a number, and its delivery can be turned off", async () => {
    showDialog();
    expect(screen.queryByLabelText("Delivery every morning")).toBeNull();
    fireEvent.change(screen.getByLabelText("Backroom units per product"), { target: { value: "30" } });
    fireEvent.click(screen.getByLabelText("Delivery every morning"));
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({
      operations: expect.objectContaining({ backroom_per_product: 30, daily_delivery: false }),
    })));
  });

  it("shows refills that came up short and when each backroom ran dry", () => {
    render(<OperationsReportView currency="USD_CENTS" report={{ ...report, backroom_units: 900, refill_short_units: 17, deliveries: 2,
      backroom: [{ sku: "cola", name: "Cola", level: 10, refilled: 10, short_units: 12, dry_day: 6, dry_at: "16:30:00" }] }} />);
    expect(screen.getByText("Refills short (backroom empty)")).toBeTruthy();
    expect(screen.getByText("Backroom at opening: 900 · Deliveries: 2")).toBeTruthy();
    expect(screen.getByText("Cola: backroom empty on Saturday at 16:30 · short: 12")).toBeTruthy();
  });
});

describe("the crew", () => {
  it("is off unless given a number; with one, a shelf is refilled at a share of full", () => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, crew: "2", refillAt: "25" }))
      .toEqual(expect.objectContaining({ crew: 2, refill_at: 0.25 }));
    expect(sharedStoreOptions(DEFAULT_SHARED_STORE)).not.toHaveProperty("refill_at");
    // The refill point only counts with a crew.
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, refillAt: "nonsense" })).not.toBe("invalid");
  });

  it.each([{ crew: "0" }, { crew: "101" }, { crew: "1.5" }, { crew: "2", refillAt: "96" }, { crew: "2", refillAt: "" },
    { crew: "2", refillAt: "-5" }])("refuses %o", (patch) => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, ...patch })).toBe("invalid");
  });

  it("replaces refill rounds and tills in the run dialog", async () => {
    showDialog();
    fireEvent.change(screen.getByLabelText("Crew on duty (tills and shelves)"), { target: { value: "3" } });
    expect(screen.queryByLabelText("Refill shelves every (minutes)")).toBeNull();
    expect(screen.queryByLabelText("Tills open")).toBeNull();
    fireEvent.change(screen.getByLabelText("Refill a shelf once down to (% of full)"), { target: { value: "0" } });
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({
      operations: expect.objectContaining({ crew: 3, refill_at: 0 }),
    })));
  });

  const crewReport: api.OperationsReport = {
    ...report, config: { ...report.config, crew: 2, crew_schedule: { "18": 3 }, refill_at: 0.5 },
    crew_hours: 29, crew_till_hours: 4.2, crew_refill_hours: 6.75, face_refills: 41, refill_wait_min: 12.5,
    refills_unfinished: 3, hours: report.hours.map((h) => ({ ...h, crew_on_duty: h.hour === "18" ? 3 : 2 })),
  };

  it("shows who did what, how long shelves waited and what was left at closing", () => {
    render(<OperationsReportView report={crewReport} currency="USD_CENTS" />);
    expect(screen.getByText("Crew on duty: 2 · Units per shelf level: 12 · Refill at: 50% of full")).toBeTruthy();
    expect(screen.getByText("Staff hours")).toBeTruthy();
    expect(screen.getByText("At the tills: 4.2 h · refilling: 6.8 h")).toBeTruthy();
    expect(screen.getByText("Average wait for a refill: 12.5 min")).toBeTruthy();
    expect(screen.getByText("Shelves still waiting for a refill at closing: 3")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Crew" })).toBeTruthy();
    expect(screen.getAllByRole("row")[2]?.textContent).toContain("3");
  });

  it.each(LOCALES)("reads in $code", ({ code }) => {
    useLocale.getState().setLocale(code);
    render(<OperationsReportView report={crewReport} currency="USD_CENTS" />);
    for (const key of ["opsCrewHours", "opsFaceRefills", "opsCrewCol"] as const) {
      expect(screen.getByText(translate(code, key))).toBeTruthy();
    }
  });
});

describe("a layout's crew", () => {
  it("comes along hour by hour, and clearing the crew drops its hours", async () => {
    vi.mocked(api.getLayoutOperations).mockResolvedValue({ operations: { ...report.config, crew: 2, crew_schedule: { "18": 4 }, refill_at: 0.25 } });
    showDialog();
    expect(await screen.findByText("Starting from this layout's saved operations.")).toBeTruthy();
    expect((screen.getByLabelText("Crew on duty (tills and shelves)") as HTMLInputElement).value).toBe("2");
    expect((screen.getByLabelText("Refill a shelf once down to (% of full)") as HTMLInputElement).value).toBe("25");
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenLastCalledWith("p", "s", expect.objectContaining({
      operations: expect.objectContaining({ crew: 2, refill_at: 0.25, crew_schedule: { "18": 4 } }),
    })));
  });

  it("is dropped with its hours when the crew is cleared", async () => {
    vi.mocked(api.getLayoutOperations).mockResolvedValue({ operations: { ...report.config, crew: 2, crew_schedule: { "18": 4 } } });
    showDialog();
    await screen.findByText("Starting from this layout's saved operations.");
    fireEvent.change(screen.getByLabelText("Crew on duty (tills and shelves)"), { target: { value: "" } });
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenLastCalledWith("p", "s", expect.objectContaining({
      operations: expect.objectContaining({ crew: null, crew_schedule: {} }),
    })));
  });
});


describe("empty backroom reporting", () => {
  it.each(LOCALES.flatMap(({ code }) => ["all", "override", "no-shortfall"].map(source => ({ code, source }))))(
    "shows zero opening stock in $code ($source)", ({ code, source }) => {
      useLocale.getState().setLocale(code);
      render(<OperationsReportView currency="USD_CENTS" report={{ ...report,
        config: { ...report.config, backroom_per_product: source === "override" ? null : 0,
          backroom_overrides: source === "override" ? { cola: 0 } : {} },
        backroom_units: 0, refill_short_units: source === "no-shortfall" ? 0 : 17, deliveries: 0,
        backroom: source === "no-shortfall" ? [] : [{ sku: "cola", name: "Cola", level: 0, refilled: 0,
          short_units: 17, dry_day: 6, dry_at: "16:30:00" }],
      }} />);
      expect(screen.getByText(translate(code, "opsRefillShort"))).toBeTruthy();
      expect(screen.getByText(translate(code, "opsBackroomSetup", { units: "0", deliveries: "0" }))).toBeTruthy();
    });
});

describe("the crew's day", () => {
  const task = (member: number, kind: "till" | "refill", start: number, end: number, day = 1): api.CrewTask =>
    ({ day, member, kind, rack_id: kind === "till" ? "C0" : "A", face: "E", sku: "chips", name: kind === "till" ? "" : "Chips", start, end });
  const crewed: api.OperationsReport = { ...report, config: { ...report.config, crew: 2, crew_schedule: {}, refill_at: 0.5 },
    crew_hours: 28, crew_till_hours: 1, crew_refill_hours: 1, face_refills: 1, refill_wait_min: 1, refills_unfinished: 0,
    crew_tasks: [task(0, "till", 36000, 36060), task(1, "refill", 36010, 36070), task(0, "till", 40000, 40030, 2)] };

  it("shows each staff member's time at the tills and refilling, for the day being played", () => {
    render(<OperationsReportView report={crewed} currency="USD_CENTS" />);
    expect(screen.getByRole("figure", { name: "The crew's day: Monday" })).toBeTruthy();
    const second = screen.getByTestId("crew-row-1");
    expect(second.querySelector("[title='10:00 Refilling Chips']")).toBeTruthy();
    expect(screen.getByTestId("crew-row-0").querySelector("[title='10:00 At the tills']")).toBeTruthy();
    expect(screen.getAllByText("At the tills").length).toBeGreaterThan(0);
  });

  it("is left out without crew tasks", () => {
    render(<OperationsReportView report={{ ...crewed, crew_tasks: [] }} currency="USD_CENTS" />);
    expect(screen.queryByRole("figure")).toBeNull();
  });
});

describe("a roster", () => {
  it("is named in the results, shift by shift", () => {
    render(<OperationsReportView currency="USD_CENTS" report={{ ...report, config: { ...report.config, crew: 1, crew_schedule: {}, refill_at: 0.5,
      crew_shifts: [{ start: 8, end: 16, days: [], staff: 1 }, { start: 16, end: 22, days: [6, 7], staff: 2 }] },
      crew_hours: 30, crew_till_hours: 2, crew_refill_hours: 3, face_refills: 10, refill_wait_min: 2, refills_unfinished: 0 }} />);
    expect(screen.getByText("Shifts: 2 · Units per shelf level: 12 · Refill at: 50% of full")).toBeTruthy();
    expect(screen.getByText("Shifts: Every day 08:00–16:00 ×1 · Sat, Sun 16:00–22:00 ×2")).toBeTruthy();
  });
});
