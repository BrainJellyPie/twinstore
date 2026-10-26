// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import * as marketing from "@/shared/api/marketing";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import type { Store } from "@/shared/types/domain";
import { formatMoney } from "@/shared/utils/money";
import { ExperimentBuilder } from "../ExperimentBuilder";

vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("@/shared/api/marketing", async original => ({ ...await original<typeof import("@/shared/api/marketing")>(), designExperiment: vi.fn(), startExperiment: vi.fn() }));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [] }) }));
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.splice(0).forEach(client => client.clear());
  vi.clearAllMocks();
  useLocale.getState().setLocale("en");
});
const store = { id: "s", name: "Shop", racks: [{ id: "r", type: "shelf", rack_name: "Tea", rack_desc: "", levels: 4, slots: [] }] } as unknown as Store;
const products = [{ sku: "tea", name: "Tea", price: 400, regularPrice: 500, promo: "", facings: 1, racks: ["Tea"] }];
const extra: marketing.VariantChange = { kind: "discount", sku: "tea", percent: -10, discount_basis: "current" };

function mount(changes?: marketing.VariantChange[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  vi.mocked(marketing.startExperiment).mockResolvedValue({ job_id: "job", kind: "experiment", name: "", status: "pending", stage: "", progress: 0, error: "", created_at: "", finished_at: "" });
  render(<QueryClientProvider client={client}><ExperimentBuilder projectId="p" setupId="s" products={products} store={store} currency="USD"
    initial={changes ? { setup_id: "s", variants: [{ name: "Tea offer", changes }], focus_skus: ["tea"], engine: "rule", panel: 300 } : undefined}
    onStarted={() => {}} /></QueryClientProvider>);
}

it.each(LOCALES)("shows and submits an extra discount in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  mount([extra]);
  expect((screen.getByRole("combobox", { name: translate(code, "mkDiscountBasis") }) as HTMLSelectElement).value).toBe("current");
  expect(screen.getByRole("option", { name: translate(code, "mkDiscountCurrent") })).toBeTruthy();
  expect(screen.getByText(translate(code, "mkDescExtraDiscount", { name: "Tea", percent: 10 }))).toBeTruthy();
  expect(screen.getByText(formatMoney(360, "USD"), { normalizer: text => text })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "mkRunAb") }));
  await waitFor(() => expect(marketing.startExperiment).toHaveBeenCalledOnce());
  expect(vi.mocked(marketing.startExperiment).mock.calls[0]![1].variants[0]!.changes).toEqual([extra]);
});

it("keeps the old regular-price default and lets the user choose and edit an additional discount", async () => {
  mount([{ kind: "discount", sku: "tea", percent: -10 }]);
  const basis = screen.getByRole("combobox", { name: "Discount basis" });
  expect((basis as HTMLSelectElement).value).toBe("regular");
  expect(screen.getByText(formatMoney(450, "USD"))).toBeTruthy();
  fireEvent.change(basis, { target: { value: "current" } });
  expect(screen.getByText(formatMoney(360, "USD"))).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Percent"), { target: { value: "-20" } });
  expect(screen.getByText(formatMoney(320, "USD"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Run A/B test" }));
  await waitFor(() => expect(marketing.startExperiment).toHaveBeenCalledOnce());
  expect(vi.mocked(marketing.startExperiment).mock.calls[0]![1].variants[0]!.changes).toEqual([{ ...extra, percent: -20 }]);
});

it("keeps the model's current-price basis when accepting and running a draft", async () => {
  vi.mocked(marketing.designExperiment).mockResolvedValue({ name: "Extra tea discount", rationale: "Compare additional savings", warnings: [], variants: [{ name: "Extra", changes: [extra] }], focus_skus: ["tea"], engine: "rule" });
  mount();
  const question = screen.getByLabelText(/Question for/);
  fireEvent.change(question, { target: { value: "Take another ten percent off the current Tea price" } });
  fireEvent.keyDown(question, { key: "Enter" });
  await screen.findByText(/Compare additional savings/);
  expect(screen.getByText(formatMoney(360, "USD"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Run A/B test" }));
  await waitFor(() => expect(marketing.startExperiment).toHaveBeenCalledOnce());
  expect(vi.mocked(marketing.startExperiment).mock.calls[0]![1].variants[0]!.changes).toEqual([extra]);
});
