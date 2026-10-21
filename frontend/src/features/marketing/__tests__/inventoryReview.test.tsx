// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { InventoryReport } from "@/shared/api/inventoryReview";
import { InventoryReview } from "../InventoryReview";

let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => { qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } }); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
function report(): InventoryReport {
  return { method: "period-inventory-review-v1", period: { start_date: "2026-10-01", end_date: "2026-10-31", currency: "USD" },
    period_days: 31, source_sha256: "abc", notes: ["Offline fixture."],
    rows: [{ inputs: { sku: "tea", opening_units: "10", received_units: "0", sold_units: "4", returned_units: "0", other_in_units: "0",
      other_out_units: "0", closing_units: "6", net_sales_minor: 800, cogs_minor: 400, opening_cost_minor: 1000, closing_cost_minor: 600 },
      expected_closing_units: 6, difference_units: 0, net_sold_units: 4, reconciled: true, gross_profit_minor: 400,
      average_inventory_cost_minor: 800, net_sell_through: 0.4, inventory_turns: 0.5, gmroi: 0.5, flags: [] }],
    totals: { sku_count: 1, reconciled_skus: 1, net_sales_minor: 800, cogs_minor: 400, gross_profit_minor: 400,
      average_inventory_cost_minor: 800, gmroi: 0.5, inventory_turns: 0.5, ratios_withheld: false } };
}
function fill(file = new File(["offline input"], "stock.csv")) {
  fireEvent.change(screen.getByLabelText("Period start (inclusive)"), { target: { value: "2026-10-01" } });
  fireEvent.change(screen.getByLabelText("Period end (inclusive)"), { target: { value: "2026-10-31" } });
  fireEvent.change(screen.getByLabelText("Currency code"), { target: { value: "usd" } });
  fireEvent.change(screen.getByLabelText("Inventory CSV"), { target: { files: [file] } });
}

it("requires an explicit period, currency and file and submits the exact scope", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<InventoryReview projectId="project_test" />, { wrapper });
  const button = screen.getByRole("button", { name: "Review inventory" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); expect(fetchMock).not.toHaveBeenCalled();
  fill(); expect(button.disabled).toBe(false); fireEvent.click(button);
  expect(await screen.findByText(/1 \/ 1 SKUs reconcile/)).toBeTruthy();
  const [url, init] = fetchMock.mock.calls[0]!;
  expect(url).toContain("/project_test/inventory-review/preview");
  const body = init?.body as FormData;
  expect(body.get("currency")).toBe("USD"); expect(body.get("start_date")).toBe("2026-10-01");
  expect(body.get("end_date")).toBe("2026-10-31"); expect((body.get("file") as File).name).toBe("stock.csv");
});

it("clears a reviewed result and export after a scope edit", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<InventoryReview projectId="project_test" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Review inventory" }));
  expect(await screen.findByRole("button", { name: "Export inventory audit CSV" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Period end (inclusive)"), { target: { value: "2026-11-01" } });
  expect(screen.queryByRole("button", { name: "Export inventory audit CSV" })).toBeNull();
  expect(screen.queryByText(/SKUs reconcile/)).toBeNull();
});

it("explains withheld ratios without replacing them with zero", async () => {
  const data = report(); data.rows[0]!.flags = ["stock_mismatch"]; data.rows[0]!.gmroi = null;
  data.totals.gmroi = null; data.totals.inventory_turns = null; data.totals.ratios_withheld = true;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(data)));
  render(<InventoryReview projectId="project_test" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Review inventory" }));
  expect(await screen.findByText("Closing stock does not reconcile")).toBeTruthy();
  expect(screen.getByText(/No rows are silently excluded/)).toBeTruthy();
  expect(screen.getAllByText("Unavailable")).toHaveLength(3);
});

it("explains negative portfolio COGS when its turnover is unavailable", async () => {
  const data = report(); data.totals.cogs_minor = -100; data.totals.inventory_turns = null;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(data)));
  render(<InventoryReview projectId="project_test" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Review inventory" }));
  expect(await screen.findByText(/Portfolio turnover is unavailable because net COGS is negative/)).toBeTruthy();
});

it("bounds period, code and file size and recovers after cancelling a file", () => {
  render(<InventoryReview projectId="project_test" />, { wrapper }); fill();
  const button = screen.getByRole("button", { name: "Review inventory" }) as HTMLButtonElement;
  fireEvent.change(screen.getByLabelText("Period end (inclusive)"), { target: { value: "2026-09-30" } }); expect(button.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Period end (inclusive)"), { target: { value: "2040-10-31" } }); expect(button.disabled).toBe(true);
  fill(new File([new Uint8Array(2 * 1024 * 1024)], "limit.csv")); expect(button.disabled).toBe(false);
  fill(new File([new Uint8Array(2 * 1024 * 1024 + 1)], "large.csv"));
  expect(button.disabled).toBe(true); expect(screen.getByRole("alert").textContent).toContain("2 MB");
  fill(); expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.change(screen.getByLabelText("Currency code"), { target: { value: "US" } }); expect(button.disabled).toBe(true);
  fill(); fireEvent.change(screen.getByLabelText("Inventory CSV"), { target: { files: [] } }); expect(button.disabled).toBe(true);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("locks all scope inputs while pending and surfaces network failures", async () => {
  let reject!: (error: Error) => void;
  fetchMock.mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  render(<InventoryReview projectId="project_test" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Review inventory" }));
  await waitFor(() => expect((screen.getByLabelText("Inventory CSV") as HTMLInputElement).disabled).toBe(true));
  for (const label of ["Period start (inclusive)", "Period end (inclusive)", "Currency code"]) expect((screen.getByLabelText(label) as HTMLInputElement).disabled).toBe(true);
  reject(new Error("Connection lost"));
  expect((await screen.findByRole("alert")).textContent).toContain("Connection lost");
  expect(screen.queryByRole("button", { name: "Export inventory audit CSV" })).toBeNull();
  expect((screen.getByLabelText("Inventory CSV") as HTMLInputElement).disabled).toBe(false);
});

it("discards a late result after the keyed project view changes", async () => {
  let finish!: (response: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<InventoryReview key="project_a" projectId="project_a" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Review inventory" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
  view.rerender(<InventoryReview key="project_b" projectId="project_b" />);
  finish(new Response(JSON.stringify(report())));
  await waitFor(() => expect((screen.getByLabelText("Inventory CSV") as HTMLInputElement).disabled).toBe(false));
  expect(screen.queryByText(/SKUs reconcile/)).toBeNull();
  expect((screen.getByLabelText("Period start (inclusive)") as HTMLInputElement).value).toBe("");
});

it("downloads a template and the exact reviewed source and period, then cleans up URLs", async () => {
  const createURL = vi.fn(() => "blob:inventory"); const revokeURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: revokeURL }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fetchMock.mockResolvedValueOnce(new Response("headers"));
  render(<InventoryReview projectId="project_test" />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Download inventory template" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
  expect((click.mock.contexts[0] as HTMLAnchorElement).download).toBe("inventory-template.csv");
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockResolvedValueOnce(new Response("audit"));
  fill(); fireEvent.click(screen.getByRole("button", { name: "Review inventory" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export inventory audit CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(2));
  const [url, init] = fetchMock.mock.calls[2]!; const body = init?.body as FormData;
  expect(url).toContain("/inventory-review/export.csv"); expect(body.get("start_date")).toBe("2026-10-01");
  expect(body.get("end_date")).toBe("2026-10-31"); expect(body.get("currency")).toBe("USD");
  expect((body.get("file") as File).name).toBe("stock.csv");
  expect((click.mock.contexts[1] as HTMLAnchorElement).download).toBe("inventory-2026-10-01-2026-10-31.csv");
  await waitFor(() => expect(revokeURL).toHaveBeenCalledTimes(2));
});

it("surfaces source deletion on export and clears it on a new file", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())))
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Project not found" }), { status: 404 }));
  render(<InventoryReview projectId="project_test" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Review inventory" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export inventory audit CSV" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Project not found");
  fireEvent.change(screen.getByLabelText("Inventory CSV"), { target: { files: [new File(["new"], "new.csv")] } });
  expect(screen.queryByRole("alert")).toBeNull(); expect(screen.queryByText(/SKUs reconcile/)).toBeNull();
});
