// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import type { Rack, Store } from "@/shared/types/domain";
import { CompareFloorPlans } from "../components/CompareFloorPlans";

vi.mock("@/shared/api/client", () => ({ previewStoreTemplate: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const rack: Rack = { id: "display", type: "shelf", position: [2, 2], shape: [[1]], rotation: 0,
  levels: 1, dwell_min: 0, dwell_max: 0, rack_name: "Products", rack_desc: "", rack_decoration_desc: "", locked_faces: [],
  slots: [{ block: 0, face: "N", level: 1, items: [{ sku: "tea", name: "Tea", price: 100, promo: "" }] }],
};
const baseline: Store = { id: "default", name: "Small café", type: "cafe", grid_size: [12, 10], weekly_schedule: [], racks: [rack] };
const current: Store = { ...baseline, id: "current", grid_size: [24, 18], design_theme: "coastal", racks: [
  rack, { ...rack, id: "duplicate-product" },
  { ...rack, id: "table", type: "table", slots: [], shape: [[1, 1], [1, 1]], position: [6, 6] },
  { ...rack, id: "counter", type: "counter", slots: [], position: [0, 16] },
] };
const areas = [{ label: "Pickup", x: 2, y: 14, width: 3, height: 2 }];
beforeEach(() => { vi.mocked(api.previewStoreTemplate).mockResolvedValue(baseline); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const submit = vi.fn();
  render(<QueryClientProvider client={client}><Dialog defaultOpen><DialogContent>
    <DialogTitle>New layout</DialogTitle><DialogDescription>Choose settings.</DialogDescription>
    <form onSubmit={(event) => { event.preventDefault(); submit(); }}>
      <label>Layout name<input defaultValue="My café" /></label>
      <CompareFloorPlans store={current} areas={areas} templateId="specialty_cafe" currency="JPY" />
    </form>
  </DialogContent></Dialog></QueryClientProvider>);
  return { submit };
}

it("loads only on demand, compares actual counts and uses the same cell scale", async () => {
  const { submit } = mount();
  expect(api.previewStoreTemplate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Compare with default" }));
  const table = await screen.findByRole("table", { name: "Floor plan comparison" });
  expect(api.previewStoreTemplate).toHaveBeenCalledWith({ template_id: "specialty_cafe", seed: 0, currency: "JPY" }, expect.any(AbortSignal));
  for (const [label, values] of [
    ["Floor size (cells)", ["12×10", "24×18"]], ["Product displays", ["1", "2"]],
    ["Unique products", ["1", "1"]], ["Dining tables / seats", ["0 / 0", "1 / 4"]],
    ["Checkout counters", ["0", "1"]], ["Reserved areas", ["0", "1"]],
    ["Interior design", ["Classic retail", "Coastal blue"]],
  ] as const) {
    const row = within(table).getByRole("row", { name: `${label} ${values.join(" ")}` });
    expect(within(row).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(values);
  }
  const plans = screen.getAllByRole("img", { name: "Floor plan preview" });
  expect(plans.map((plan) => plan.getAttribute("viewBox"))).toEqual(["-0.2 -0.2 24.4 18.4", "-0.2 -0.2 24.4 18.4"]);
  expect(within(screen.getByRole("region", { name: "Format default" })).queryByTestId("reserved-area-preview-0")).toBeNull();
  expect(within(screen.getByRole("region", { name: "Your current options" })).getByTestId("reserved-area-preview-0")).toBeTruthy();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Compare floor plans" })).toBeNull());
  expect((screen.getByLabelText("Layout name") as HTMLInputElement).value).toBe("My café");
  expect(submit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Compare with default" }));
  await screen.findByRole("table", { name: "Floor plan comparison" });
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(1);
});

it("expands each plan at its original dimensions and returns to the comparison", async () => {
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Compare with default" }));
  const defaultPlan = await screen.findByRole("region", { name: "Format default" });
  fireEvent.click(within(defaultPlan).getByRole("button", { name: "Expand floor plan" }));
  expect(screen.getByRole("img", { name: "Detailed floor plan" }).getAttribute("viewBox")).toBe("-1.2 -1.2 13.4 11.4");
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Floor plan details" })).toBeNull());
  expect(screen.getByRole("dialog", { name: "Compare floor plans" })).toBeTruthy();
  fireEvent.click(within(screen.getByRole("region", { name: "Your current options" })).getByRole("button", { name: "Expand floor plan" }));
  expect(screen.getByRole("img", { name: "Detailed floor plan" }).getAttribute("viewBox")).toBe("-1.2 -1.2 25.4 19.4");
  expect(screen.getByText("Pickup · 3×2 cells · column 3, row 15")).toBeTruthy();
});

it("shows loading and lets a failed default preview be retried without changing options", async () => {
  let reject: (error: Error) => void = () => {};
  vi.mocked(api.previewStoreTemplate).mockImplementationOnce(() => new Promise<Store>((_resolve, rejectPromise) => { reject = rejectPromise; }));
  const { submit } = mount();
  fireEvent.click(screen.getByRole("button", { name: "Compare with default" }));
  expect(screen.getByRole("status").textContent).toBe("Loading the format default…");
  reject(new Error("Preview request failed"));
  expect((await screen.findByRole("alert")).textContent).toContain("Preview request failed");
  expect(screen.queryByRole("table")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry comparison" }));
  await screen.findByRole("table", { name: "Floor plan comparison" });
  expect(submit).not.toHaveBeenCalled();
});
