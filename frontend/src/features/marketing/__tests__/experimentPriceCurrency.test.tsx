// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import * as marketing from "@/shared/api/marketing";
import { ExperimentBuilder } from "../ExperimentBuilder";

vi.mock("@/shared/api/client", async original => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async original => ({
  ...await original<typeof marketing>(), startExperiment: vi.fn(), designExperiment: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [] }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const products = [{ sku: "tea", name: "Tea", price: 199, regularPrice: 0, promo: "", facings: 1, racks: ["Drinks"] }];
const store = { racks: [{ id: "r", type: "shelf", rack_name: "Drinks", levels: 4, slots: [{}] }] } as never;
const job: marketing.JobStatus = { job_id: "exp_1", kind: "experiment", name: "", status: "pending", stage: "",
  progress: 0, error: "", created_at: "", finished_at: "" };
function mount(sourceCurrency: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const initial = { setup_id: "s", currency: sourceCurrency, variants: [
    { name: "Imported price", changes: [{ kind: "price" as const, sku: "tea", price: 3000 }] },
  ], focus_skus: ["tea"], engine: "rule" as const, panel: 20 };
  render(<QueryClientProvider client={client}>
    <ExperimentBuilder projectId="p" setupId="s" products={products} store={store} currency="USD"
      initial={initial} onStarted={vi.fn()} />
  </QueryClientProvider>);
}
const runButton = () => screen.getAllByRole("button").find(button => /^Run /.test(button.textContent ?? "")) as HTMLButtonElement;

it("blocks a foreign-currency draft without displaying its 3,000 won as $30", () => {
  mount("KRW");
  expect(screen.getByRole("alert").textContent).toMatch(/KRW.*USD/);
  expect(screen.queryByLabelText("New price")).toBeNull();
  expect(runButton().disabled).toBe(true);
  fireEvent.click(runButton());
  expect(marketing.startExperiment).not.toHaveBeenCalled();
});

it("preserves the currency and exact integer when the target matches", async () => {
  vi.mocked(marketing.startExperiment).mockResolvedValue(job);
  mount("usd");
  expect((screen.getByLabelText("New price") as HTMLInputElement).value).toBe("30.00");
  fireEvent.click(runButton());
  await waitFor(() => expect(marketing.startExperiment).toHaveBeenCalled());
  expect(vi.mocked(marketing.startExperiment).mock.calls[0]![1]).toMatchObject({ currency: "USD",
    variants: [{ changes: [{ price: 3000 }] }] });
});

it("lets a newly generated test replace the mismatched draft in the current currency", async () => {
  vi.mocked(marketing.designExperiment).mockResolvedValue({ name: "New test", engine: "rule", rationale: "Try a new price.",
    focus_skus: ["tea"], warnings: [], variants: [{ name: "Local price", changes: [{ kind: "price", sku: "tea", price: 250 }] }] });
  vi.mocked(marketing.startExperiment).mockResolvedValue(job);
  mount("KRW");
  fireEvent.change(screen.getByLabelText("Question for the test"), { target: { value: "Test a new local price of $2.50." } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the test" }));
  expect(await screen.findByDisplayValue("Local price")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.click(runButton());
  await waitFor(() => expect(marketing.startExperiment).toHaveBeenCalled());
  expect(vi.mocked(marketing.startExperiment).mock.calls[0]![1]).toMatchObject({ currency: "USD",
    variants: [{ changes: [{ price: 250 }] }] });
});

it("says a typed new price is not an amount, and points the field to that message", () => {
  mount("USD");
  const price = screen.getByLabelText("New price");
  fireEvent.change(price, { target: { value: "abc" } });
  const message = screen.getByText("Not an amount");
  expect(message.getAttribute("role")).toBe("alert");
  expect(price.getAttribute("aria-describedby")).toBe(message.id);
  expect(runButton().disabled).toBe(true);
  fireEvent.change(price, { target: { value: "2.50" } });
  expect(screen.queryByText("Not an amount")).toBeNull();
});
