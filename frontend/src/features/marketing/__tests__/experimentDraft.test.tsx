// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { designExperiment, startExperiment } from "@/shared/api/marketing";
import { ExperimentBuilder } from "../ExperimentBuilder";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), designExperiment: vi.fn(), startExperiment: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [] }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const products = [{ sku: "A1", name: "Cola 500 ml", price: 199, regularPrice: 0, promo: "", facings: 2, racks: ["Drinks 1"] }];
const store = { racks: [{ id: "r1", type: "shelf", rack_name: "Drinks 1", levels: 4, slots: [{}] }] } as never;

it("drafts the variants from a question and runs them as drafted", async () => {
  vi.mocked(designExperiment).mockResolvedValue({
    name: "Sign or cut", engine: "rule", rationale: "Compare a sign with a cut.", focus_skus: ["A1"],
    warnings: ['Eye level: no shelf "Nowhere" in this layout; that move was left out.'],
    variants: [
      { name: "1+1 sign", changes: [{ kind: "promo", sku: "A1", promo: "1+1" }] },
      { name: "20 % off", changes: [{ kind: "discount", sku: "A1", percent: -20 }] },
    ],
  });
  vi.mocked(startExperiment).mockResolvedValue({ job_id: "exp_1", kind: "experiment", name: "", status: "pending", stage: "", progress: 0, error: "", created_at: "", finished_at: "" });
  const started = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}>
    <ExperimentBuilder projectId="p" setupId="s1" products={products} store={store} currency="USD" onStarted={started} />
  </QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Question for the test"), { target: { value: "Does a 1+1 sign beat a 20 % cut?" } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the test" }));
  expect(await screen.findByText(/Compare a sign with a cut\. Check the variants below before running\./)).toBeTruthy();
  expect(designExperiment).toHaveBeenCalledWith("p", { question: "Does a 1+1 sign beat a 20 % cut?", setup_id: "s1" });
  expect(screen.getByText(/no shelf "Nowhere"/)).toBeTruthy();
  expect((screen.getByDisplayValue("1+1 sign") as HTMLInputElement)).toBeTruthy();
  expect((screen.getByDisplayValue("20 % off") as HTMLInputElement)).toBeTruthy();
  const run = screen.getAllByRole("button").find((b) => /^Run /.test(b.textContent ?? "") || /Start/.test(b.textContent ?? ""));
  expect(run).toBeTruthy();
  fireEvent.click(run!);
  await waitFor(() => expect(startExperiment).toHaveBeenCalled());
  const req = vi.mocked(startExperiment).mock.calls[0]![1];
  expect(req.name).toBe("Sign or cut");
  expect(req.variants.map((v) => v.name)).toEqual(["1+1 sign", "20 % off"]);
  expect(req.variants[0]!.changes[0]).toEqual({ kind: "promo", sku: "A1", promo: "1+1" });
});

it("drafts from a request routed by the command palette, once per request", async () => {
  vi.mocked(designExperiment).mockResolvedValue({ name: "Sign", engine: "rule", rationale: "One sign.", focus_skus: ["A1"], warnings: [],
    variants: [{ name: "1+1 sign", changes: [{ kind: "promo", sku: "A1", promo: "1+1" }] }] });
  const props = { projectId: "p", setupId: "s1", products, store, currency: "USD", onStarted: vi.fn() };
  const client = new QueryClient();
  const view = render(<QueryClientProvider client={client}>
    <ExperimentBuilder {...props} prefill={{ id: 7, text: "Would a 1+1 sign sell more cola?" }} />
  </QueryClientProvider>);
  expect(await screen.findByDisplayValue("1+1 sign")).toBeTruthy();
  expect((screen.getByLabelText("Question for the test") as HTMLTextAreaElement).value).toBe("Would a 1+1 sign sell more cola?");
  view.rerender(<QueryClientProvider client={client}>
    <ExperimentBuilder {...props} prefill={{ id: 7, text: "Would a 1+1 sign sell more cola?" }} />
  </QueryClientProvider>);
  expect(designExperiment).toHaveBeenCalledTimes(1);
});

it("a drafted test that picks vision shoppers starts from a vision-sized panel, as choosing them by hand does", async () => {
  vi.mocked(designExperiment).mockResolvedValue({ name: "Pack", engine: "vlm", rationale: "Shoppers must see the pack.", focus_skus: ["A1"],
    warnings: [], variants: [{ name: "Sign", changes: [{ kind: "promo", sku: "A1", promo: "1+1" }] }] });
  vi.mocked(startExperiment).mockResolvedValue({ job_id: "exp_1", kind: "experiment", name: "", status: "pending", stage: "", progress: 0, error: "", created_at: "", finished_at: "" });
  render(<QueryClientProvider client={new QueryClient()}>
    <ExperimentBuilder projectId="p" setupId="s1" products={products} store={store} currency="USD" onStarted={vi.fn()} />
  </QueryClientProvider>);
  expect(screen.getByText("600 simulated trips.", { exact: false })).toBeTruthy();   // 300 rule shoppers × 2 arms
  fireEvent.change(screen.getByLabelText("Question for the test"), { target: { value: "Does the new pack sell more?" } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the test" }));
  expect(await screen.findByText(/160 simulated trips through the model/)).toBeTruthy();   // 80 vision shoppers × 2 arms
  const run = screen.getAllByRole("button").find((b) => /^Run /.test(b.textContent ?? "") || /Start/.test(b.textContent ?? ""));
  fireEvent.click(run!);
  await waitFor(() => expect(startExperiment).toHaveBeenCalled());
  expect(vi.mocked(startExperiment).mock.calls[0]![1]).toMatchObject({ engine: "vlm", panel: 80 });
});
