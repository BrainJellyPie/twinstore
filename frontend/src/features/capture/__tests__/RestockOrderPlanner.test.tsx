// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { AuditReport } from "@/shared/api/client";
import { exportRestockOrder, previewRestockOrder, type RestockOrderPlan } from "@/shared/api/restockOrder";
import { RestockOrderPlanner } from "../RestockOrderPlanner";

vi.mock("@/shared/api/restockOrder", () => ({ previewRestockOrder: vi.fn(), exportRestockOrder: vi.fn() }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks(); vi.unstubAllGlobals(); });
let qc: QueryClient;
beforeEach(() => { qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } }); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
const report: AuditReport = {
  job_id: "aud_test", capture_id: "cap_test", setup_id: "setup_test", rack_id: "rack", face: "N", currency: "USD", compliance: 0.5,
  levels: [], findings: [1, 2].map((level) => ({ kind: "missing", level, sku: "tea", name: "Tea", expected: "present", found: "missing", box: null, loss_per_day: 9999, loss_ci: null })),
  impact: null, visitors_per_day: 100, revenue_delta_per_day: null, revenue_delta_ci: null, panel_size: 0, notes: [], seconds: 0,
};
const item = { sku: "tea", required_units: 10, stockroom_units: 1, pack_size: 6, pack_cost_minor: 300, max_packs: 5, priority: 1 };
const plan: RestockOrderPlan = {
  audit_id: "aud_test", capture_id: "cap_test", setup_id: "setup_test", rack_id: "rack", face: "N", currency: "USD",
  budget_minor: 1000, delivery_fee_minor: 100, delivery_charged_minor: 100, goods_cost_minor: 600, total_cost_minor: 700,
  remaining_budget_minor: 300, omitted_skus: [], unidentified_findings: 0,
  actions: [{ item, name: "Tea", levels: [1, 2], stockroom_used: 1, packs_needed: 2, packs_ordered: 2, units_ordered: 12,
    surplus_units: 3, unfilled_units: 0, cost_minor: 600, supplier_limited: false, budget_limited: false }], notes: ["Offline test fixture."],
};
function fill() {
  for (const [label, value] of [["Purchase budget (USD minor units)", "1000"], ["One delivery fee (USD minor units)", "100"],
    ["Required shelf units · tea", "10"], ["Available stockroom units · tea", "1"], ["Units per pack · tea", "6"],
    ["Cost per pack (minor units) · tea", "300"], ["Supplier available packs · tea", "5"]]) {
    fireEvent.change(screen.getByLabelText(label!), { target: { value } });
  }
}
function calculate() { fireEvent.click(screen.getByRole("button", { name: "Calculate restocking quantities" })); }

it("requires verified counts instead of deriving units from missing levels or simulated losses", async () => {
  vi.mocked(previewRestockOrder).mockResolvedValue(plan);
  render(<RestockOrderPlanner projectId="p" report={report} />, { wrapper });
  const button = screen.getByRole("button", { name: "Calculate restocking quantities" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(screen.getAllByLabelText("Required shelf units · tea")).toHaveLength(1);
  expect((screen.getByLabelText("Required shelf units · tea") as HTMLInputElement).value).toBe("");
  fill(); calculate();
  await screen.findByText("Planned spend: $7.00");
  expect(previewRestockOrder).toHaveBeenCalledWith("p", "cap_test", "aud_test", {
    currency: "USD", budget_minor: 1000, delivery_fee_minor: 100, items: [item],
  });
  expect(screen.getByText("Levels 1, 2")).toBeTruthy();
  expect(screen.getByText("2 / 12")).toBeTruthy();
});

it("invalidates the old result and export as soon as an input changes", async () => {
  vi.mocked(previewRestockOrder).mockResolvedValue(plan);
  render(<RestockOrderPlanner projectId="p" report={report} />, { wrapper });
  fill(); calculate(); await screen.findByText("Planned spend: $7.00");
  fireEvent.change(screen.getByLabelText("Available stockroom units · tea"), { target: { value: "" } });
  expect(screen.queryByText("Planned spend: $7.00")).toBeNull();
  expect(screen.queryByRole("button", { name: "Export quantity plan CSV" })).toBeNull();
  expect((screen.getByRole("button", { name: "Calculate restocking quantities" }) as HTMLButtonElement).disabled).toBe(true);
  expect(exportRestockOrder).not.toHaveBeenCalled();
});

it("distinguishes zero from blank, rejects fractions, and supports excluding a SKU", () => {
  render(<RestockOrderPlanner projectId="p" report={report} />, { wrapper });
  fill(); const button = screen.getByRole("button", { name: "Calculate restocking quantities" }) as HTMLButtonElement;
  fireEvent.change(screen.getByLabelText("Available stockroom units · tea"), { target: { value: "0" } });
  expect(button.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Required shelf units · tea"), { target: { value: "1.5" } });
  expect(button.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Required shelf units · tea"), { target: { value: "0" } });
  expect(button.disabled).toBe(false);
  fireEvent.click(screen.getByLabelText("Include tea"));
  expect(button.disabled).toBe(true);
});

it("blocks editing during calculation and recovers from request failures", async () => {
  let reject!: (error: Error) => void;
  vi.mocked(previewRestockOrder).mockReturnValue(new Promise((_, fail) => { reject = fail; }));
  render(<RestockOrderPlanner projectId="p" report={report} />, { wrapper });
  fill(); calculate(); await screen.findByText(/Calculating stockroom/);
  expect((screen.getByLabelText("Purchase budget (USD minor units)") as HTMLInputElement).disabled).toBe(true);
  expect(screen.getByLabelText("Required shelf units · tea").closest("fieldset")?.disabled).toBe(true);
  reject(new Error("The audit is no longer available"));
  expect((await screen.findByRole("alert")).textContent).toContain("no longer available");
  expect((screen.getByLabelText("Purchase budget (USD minor units)") as HTMLInputElement).disabled).toBe(false);
  expect(screen.queryByRole("button", { name: "Export quantity plan CSV" })).toBeNull();
});

it("exports the exact successful input snapshot and reports download failures", async () => {
  vi.mocked(previewRestockOrder).mockResolvedValue(plan);
  vi.mocked(exportRestockOrder).mockRejectedValue(new Error("Export source unavailable"));
  render(<RestockOrderPlanner projectId="p" report={report} />, { wrapper });
  fill(); calculate(); await screen.findByText("Planned spend: $7.00");
  fireEvent.click(screen.getByRole("button", { name: "Export quantity plan CSV" }));
  await waitFor(() => expect(exportRestockOrder).toHaveBeenCalledWith("p", "cap_test", "aud_test", {
    currency: "USD", budget_minor: 1000, delivery_fee_minor: 100, items: [item],
  }));
  expect((await screen.findByRole("alert")).textContent).toContain("Export source unavailable");
});

it("downloads the returned CSV as a worksheet without issuing a purchase", async () => {
  const csv = new Blob(["audit_id,sku\naud_test,tea\n"], { type: "text/csv" });
  const create = vi.fn(() => "blob:restock-plan"), revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  vi.mocked(previewRestockOrder).mockResolvedValue(plan);
  vi.mocked(exportRestockOrder).mockResolvedValue(csv);
  render(<RestockOrderPlanner projectId="p" report={report} />, { wrapper });
  fill(); calculate(); await screen.findByText("Planned spend: $7.00");
  fireEvent.click(screen.getByRole("button", { name: "Export quantity plan CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(create).toHaveBeenCalledWith(csv);
  const link = click.mock.instances[0] as HTMLAnchorElement;
  expect(link.download).toBe("aud_test-restock-order.csv");
  expect(link.href).toBe("blob:restock-plan");
  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:restock-plan"));
});
