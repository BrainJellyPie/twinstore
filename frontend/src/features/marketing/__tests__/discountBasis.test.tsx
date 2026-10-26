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

function mount(changes?: marketing.VariantChange[], prices = { price: 400, regularPrice: 500 }, currency = "USD") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  vi.mocked(marketing.startExperiment).mockResolvedValue({ job_id: "job", kind: "experiment", name: "", status: "pending", stage: "", progress: 0, error: "", created_at: "", finished_at: "" });
  render(<QueryClientProvider client={client}><ExperimentBuilder projectId="p" setupId="s" products={products.map(product => ({ ...product, ...prices }))} store={store} currency={currency}
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

for (const currency of ["USD", "KRW", "JPY"]) {
  it.each([
    { price: 81, regularPrice: 101, basis: "regular", percent: -50, expected: 50 },
    { price: 81, regularPrice: 101, basis: "current", percent: -50, expected: 40 },
    { price: 83, regularPrice: 103, basis: "regular", percent: -50, expected: 52 },
    { price: 83, regularPrice: 103, basis: "current", percent: -50, expected: 42 },
    { price: 81, regularPrice: 101, basis: "current", percent: -37.5, expected: 51 },
    { price: 81, regularPrice: 101, basis: "regular", percent: -100, expected: 0 },
    { price: 0, regularPrice: 101, basis: "current", percent: -50, expected: 0 },
    { price: 1, regularPrice: 0, basis: "regular", percent: -50, expected: 0 },
  ] as const)(`previews the applied ${currency} price $expected for $basis $price/$regularPrice at $percent%`, ({ price, regularPrice, basis, percent, expected }) => {
    mount([{ kind: "discount", sku: "tea", percent, discount_basis: basis }], { price, regularPrice }, currency);
    expect(screen.getByText(formatMoney(expected, currency), { selector: "b" })).toBeTruthy();
  });
}

it.each([
  { kind: "discount", percent: "-100.01" },
  { kind: "discount", percent: "0" },
  { kind: "discount", percent: "10" },
  { kind: "category_price", percent: "-100.01" },
  { kind: "category_price", percent: "300.01" },
] as const)("blocks out-of-range $kind percentage $percent until corrected", async ({ kind, percent }) => {
  mount([{ kind, sku: "tea", category: "Tea", percent: -10 }]);
  const field = screen.getByLabelText("Percent");
  fireEvent.change(field, { target: { value: percent } });
  expect(field.getAttribute("aria-invalid")).toBe("true");
  const run = screen.getByRole("button", { name: "Run A/B test" }) as HTMLButtonElement;
  expect(run.disabled).toBe(true);
  fireEvent.click(run);
  expect(marketing.startExperiment).not.toHaveBeenCalled();
  fireEvent.change(field, { target: { value: "-0.5" } });
  expect(field.getAttribute("aria-invalid")).toBe("false");
  expect(run.disabled).toBe(false);
  fireEvent.click(run);
  await waitFor(() => expect(marketing.startExperiment).toHaveBeenCalledOnce());
  expect(vi.mocked(marketing.startExperiment).mock.calls[0]![1].variants[0]!.changes[0]!.percent).toBe(-0.5);
});

it.each([
  { kind: "discount", percent: -100 },
  { kind: "discount", percent: -0.5 },
  { kind: "category_price", percent: -100 },
  { kind: "category_price", percent: 0 },
  { kind: "category_price", percent: 300 },
] as const)("allows the valid $kind boundary $percent", async ({ kind, percent }) => {
  mount([{ kind, sku: "tea", category: "Tea", percent }]);
  const field = screen.getByLabelText("Percent") as HTMLInputElement;
  expect(field.validity.valid).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Run A/B test" }));
  await waitFor(() => expect(marketing.startExperiment).toHaveBeenCalledOnce());
  expect(vi.mocked(marketing.startExperiment).mock.calls[0]![1].variants[0]!.changes[0]!.percent).toBe(percent);
});

for (const kind of ["discount", "category_price"] as const) {
  it.each(LOCALES)(`explains an invalid ${kind} percentage in $code`, ({ code }) => {
    useLocale.getState().setLocale(code);
    mount([{ kind, sku: "tea", category: "Tea", percent: -101 }]);
    const input = screen.getByLabelText(translate(code, "mkPercent"));
    const hint = document.getElementById(input.getAttribute("aria-describedby")!);
    expect(hint?.textContent).toBe(translate(code, kind === "discount" ? "mkDiscountPercentRange" : "mkCategoryPercentRange"));
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect((screen.getByRole("button", { name: translate(code, "mkRunAb") }) as HTMLButtonElement).disabled).toBe(true);
  });
}

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
