// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { RunLauncherDialog } from "../RunLauncherDialog";
import { DEFAULT_SHARED_STORE, sharedStoreOptions } from "../../sharedStore";
import { OperationsReportView, OperationsSection } from "../OperationsSection";

vi.mock("@/shared/api/client", () => ({
  getEngines: vi.fn(), getTown: vi.fn(), getModels: vi.fn(), startRun: vi.fn(), estimateRun: vi.fn(),
  getModelSetup: vi.fn(), getRunOperations: vi.fn(),
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
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}
function showDialog() {
  render(<QueryClientProvider client={client()}><RunLauncherDialog open onOpenChange={vi.fn()} projectId="p" setupId="s" personaCount={100} defaultEngine="rule_based" /></QueryClientProvider>);
}
async function submit() { await act(async () => { fireEvent.submit(document.querySelector("form")!); }); }

describe("the run option", () => {
  it("shares the store by default, refilling every two hours with every till open", () => {
    expect(sharedStoreOptions(DEFAULT_SHARED_STORE)).toEqual({
      stock_per_facing: 12, restock_every_min: 120, open_counters: null, patience_sec: 300,
    });
  });

  it("reads blank refill and tills as overnight and every till, and turning it off sends nothing", () => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, restock: " ", tills: "", patience: "1.5" }))
      .toEqual({ stock_per_facing: 12, restock_every_min: null, open_counters: null, patience_sec: 90 });
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, enabled: false, stock: "nonsense" })).toBeUndefined();
  });

  it.each([
    { stock: "0" }, { stock: "1.5" }, { stock: "" }, { stock: "10001" }, { restock: "4" }, { restock: "1441" },
    { tills: "0" }, { tills: "51" }, { tills: "2.5" }, { patience: "0.4" }, { patience: "121" }, { patience: "" },
  ])("refuses %o", (patch) => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, ...patch })).toBe("invalid");
  });

  it.each([
    { stock: "1" }, { stock: "10000" }, { restock: "5" }, { restock: "1440" }, { tills: "1" }, { tills: "50" },
    { patience: "0.5" }, { patience: "120" },
  ])("accepts the boundary %o", (patch) => {
    expect(sharedStoreOptions({ ...DEFAULT_SHARED_STORE, ...patch })).not.toBe("invalid");
  });
});

describe("the run dialog", () => {
  it("starts a run whose shoppers share the store", async () => {
    showDialog();
    expect((screen.getByLabelText("Shoppers share the store") as HTMLInputElement).checked).toBe(true);
    fireEvent.change(screen.getByLabelText("Tills open"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Units of each product per shelf level"), { target: { value: "4" } });
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({
      operations: { stock_per_facing: 4, restock_every_min: 120, open_counters: 2, patience_sec: 300 },
    })));
  });

  it("starts the old way with the option off", async () => {
    showDialog();
    fireEvent.click(screen.getByLabelText("Shoppers share the store"));
    expect(screen.queryByLabelText("Tills open")).toBeNull();
    await submit();
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ operations: undefined })));
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
    for (const key of ["opsShareTitle", "opsStockPerFacing", "opsRestockEvery", "opsTillsOpen", "opsPatience"] as const) {
      expect(screen.getByLabelText(translate(code, key))).toBeTruthy();
    }
  });
});

const report: api.OperationsReport = {
  config: {
    stock_per_facing: 12, stock_overrides: {}, till_schedule: {}, restock_every_min: 120, substitute_share: 0.45, open_counters: null,
    checkout_base_sec: 25, checkout_item_sec: 3, patience_sec: 300, patience_sd: 0.5, target_wait_sec: 120,
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
  it("say what sharing the store cost and how many tills the busiest hour needed", () => {
    render(<OperationsReportView report={report} currency="USD_CENTS" />);
    expect(screen.getByText("Store operations")).toBeTruthy();
    expect(screen.getByText("$45.60")).toBeTruthy();
    expect(screen.getByText("Units: 11")).toBeTruthy();
    expect(screen.getByText("2.3 min")).toBeTruthy();
    expect(screen.getByText("Busiest hour 18:00: open tills 3 (now 1) to keep the average wait under 2 min.")).toBeTruthy();
    expect(screen.getAllByText("Out at 18:05 · empty 47.5 min")).toHaveLength(8);
    expect(screen.getByText("Lost: 5 · $10.00")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(9);
    expect(screen.getByText("Other products that ran out: 2")).toBeTruthy();
    expect(screen.getAllByRole("row")).toHaveLength(3);
  });

  it("say the tills were enough when they were", () => {
    render(<OperationsReportView report={{ ...report, counters: 3, counters_needed: 3, stockouts: [] }} />);
    expect(screen.getByText("Tills open (3) kept every hour's average wait under 2 min.")).toBeTruthy();
    expect(screen.getByText("No product ran out.")).toBeTruthy();
  });

  it("explain a layout without tills", () => {
    render(<OperationsReportView report={{ ...report, counters: 0, counters_in_layout: 0, hours: [] }} />);
    expect(screen.getByText("This layout has no tills, so nobody waited in line.")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it.each(LOCALES)("read in $code", ({ code }) => {
    useLocale.getState().setLocale(code);
    render(<OperationsReportView report={report} currency="USD_CENTS" />);
    expect(screen.getByText(translate(code, "opsTitle"))).toBeTruthy();
    expect(screen.getByText(translate(code, "opsHoursTitle"))).toBeTruthy();
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
