// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";
import { weekdayLong } from "@/shared/i18n/timeFormat";
import { starterCategoryLabel } from "@/shared/i18n/catalogCategories";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, templateRequest, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn(), validateLayoutPreset: vi.fn() }));
let client: QueryClient;
const applyHours = vi.fn(), applyAssortment = vi.fn();
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
beforeEach(() => {
  useLocale.getState().setLocale("en");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.getStoreTemplates).mockResolvedValue([{ id: "urban_cvs", name: "Original format", description: "Original description", store_type: "convenience", grid: [12, 10], racks: 2, skus: 24,
    open_hours: [7, 22], closed_days: [7], default_style: "aisles", default_design: "classic", default_dining_tables: 0,
    categories: [{ id: "water_sports", label: "생수 / 음료" }, { id: "home_lighting", label: "Home Lighting" }, { id: "future_category", label: "原文 🛒 {category}" }] }]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Original preview", type: "convenience", grid_size: [12, 10], racks: [], weekly_schedule: [] });
});
afterEach(() => { cleanup(); client.clear(); vi.resetAllMocks(); useLocale.getState().setLocale("en"); });
function Form({ initial = DEFAULT_TEMPLATE_CHOICE }: { initial?: TemplateChoice }) {
  const [value, onChange] = useState(initial);
  return <><TemplatePicker value={value} onChange={onChange} onApplyHoursToAll={applyHours} onApplyAssortmentToAll={applyAssortment} />
    <output data-testid="raw-choice">{JSON.stringify(value)}</output></>;
}
async function mount(initial?: TemplateChoice) {
  render(<QueryClientProvider client={client}><Form initial={initial} /></QueryClientProvider>);
  await screen.findByRole("img", { name: t("planPreviewImage") });
}
const choice = (): TemplateChoice => JSON.parse(screen.getByTestId("raw-choice").textContent!);
const input = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const change = (name: string, value: string) => fireEvent.change(input(name), { target: { value } });

it.each(LOCALES)("sets hours, exclusions, limits and a reproducible seed in $code without translating request values", async ({ code }) => {
  useLocale.getState().setLocale(code); await mount();
  fireEvent.click(screen.getByText(t("templateHoursSummary", { count: 6 })));
  fireEvent.click(screen.getByRole("checkbox", { name: t("templateHoursIndividual") }));
  const monday = weekdayLong(1, code), sunday = weekdayLong(7, code);
  change(t("templateDayOpening", { day: monday }), "0");
  change(t("templateDayClosing", { day: monday }), "24");
  expect(input(t("templateDayOpening", { day: sunday })).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("templateHoursApply") }));
  expect(applyHours.mock.lastCall?.[0].weekly_hours[0]).toEqual({ day: 1, is_open: true, open_hour: 0, close_hour: 24 });
  expect(applyHours.mock.lastCall?.[0].weekly_hours[6].is_open).toBe(false);
  fireEvent.click(screen.getByText(t("templateCategoriesSummary", { included: 3, total: 3 })));
  change(t("templateProductsPerCategory"), "4");
  const water = starterCategoryLabel("water_sports", "생수 / 음료", code);
  change(t("templateProductsFor", { category: water }), "2");
  const light = starterCategoryLabel("home_lighting", "Home Lighting", code);
  fireEvent.click(screen.getByRole("checkbox", { name: light }));
  expect(input(t("templateProductsFor", { category: light })).disabled).toBe(true);
  expect(screen.getByRole("checkbox", { name: "原文 🛒 {category}" })).toBeTruthy();
  change(t("templateSeed"), "-7");
  fireEvent.click(screen.getByRole("button", { name: t("templateShuffleSeed", { seed: "-7" }) }));
  fireEvent.click(screen.getByRole("button", { name: t("templateAssortmentApply") }));
  expect(applyAssortment.mock.lastCall?.[0]).toEqual({ excluded_categories: ["home_lighting"], products_per_category: 4, category_product_limits: { water_sports: 2 }, seed: -6 });
  const request = templateRequest(choice());
  expect(request).toMatchObject({ template_id: "urban_cvs", currency: "USD", seed: -6, excluded_categories: ["home_lighting"], products_per_category: 4, category_product_limits: { water_sports: 2 } });
  const { requirements: _brief, ...previewRequest } = request;
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(previewRequest, expect.any(AbortSignal)));
  expect(vi.mocked(api.previewStoreTemplate).mock.lastCall?.[0]).not.toHaveProperty("requirements");
  const before = JSON.stringify(choice()), requests = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  act(() => useLocale.getState().setLocale(code === "fr" ? "ko" : "fr"));
  expect(JSON.stringify(choice())).toBe(before);
  expect(input(t("templateSeed")).value).toBe("-6");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(requests);
});

it("retains an invalid seed draft when the locale changes, then recovers at the safe-integer boundary", async () => {
  await mount();
  change(t("templateSeed"), "9007199254740992");
  expect(input(t("templateSeed")).getAttribute("aria-invalid")).toBe("true");
  act(() => useLocale.getState().setLocale("ja"));
  expect(input(t("templateSeed")).value).toBe("9007199254740992");
  expect(screen.getByText(t("templateSeedInvalid"))).toBeTruthy();
  change(t("templateSeed"), String(Number.MAX_SAFE_INTEGER));
  expect(screen.getByRole("button", { name: t("templateShuffleSeed", { seed: String(Number.MAX_SAFE_INTEGER) }) }).matches(":disabled")).toBe(true);
  change(t("templateSeed"), "-0");
  expect(input(t("templateSeed")).value).toBe("-0");
  act(() => useLocale.getState().setLocale("es"));
  expect(input(t("templateSeed")).value).toBe("-0");
  expect(screen.queryByText(t("templateSeedInvalid"))).toBeNull();
});

it("protects the last open day and category while invalid drafts and limits survive language changes", async () => {
  useLocale.getState().setLocale("ja"); await mount();
  fireEvent.click(screen.getByText(t("templateHoursSummary", { count: 6 })));
  fireEvent.click(screen.getByRole("checkbox", { name: t("templateHoursIndividual") }));
  for (let day = 2; day <= 6; day++) fireEvent.click(screen.getByRole("checkbox", { name: weekdayLong(day, "ja") }));
  expect(screen.getByRole("checkbox", { name: weekdayLong(1, "ja") }).matches(":disabled")).toBe(true);
  const before = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  change(t("templateDayClosing", { day: weekdayLong(1, "ja") }), "");
  expect(screen.getByText(t("templateHoursInvalid"))).toBeTruthy();
  expect(screen.getByRole("button", { name: t("templateHoursApply") }).matches(":disabled")).toBe(true);
  expect(screen.getByRole("button", { name: t("optionsExport") }).matches(":disabled")).toBe(true);
  act(() => useLocale.getState().setLocale("fr"));
  expect(screen.getByText(t("templateHoursInvalid"))).toBeTruthy();
  expect(input(t("templateDayClosing", { day: weekdayLong(1, "fr") })).value).toBe("");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(before);
  change(t("templateDayOpening", { day: weekdayLong(1, "fr") }), "23");
  change(t("templateDayClosing", { day: weekdayLong(1, "fr") }), "23");
  expect(screen.getByText(t("templateHoursInvalid"))).toBeTruthy();
  change(t("templateDayClosing", { day: weekdayLong(1, "fr") }), "24");
  await screen.findByRole("img", { name: t("planPreviewImage") });
  expect(screen.queryByText(t("templateHoursInvalid"))).toBeNull();
  fireEvent.click(screen.getByText(t("templateCategoriesSummary", { included: 3, total: 3 })));
  fireEvent.click(screen.getByRole("checkbox", { name: "原文 🛒 {category}" }));
  fireEvent.click(screen.getByRole("checkbox", { name: starterCategoryLabel("home_lighting", "Home Lighting", "fr") }));
  const water = starterCategoryLabel("water_sports", "생수 / 음료", "fr");
  expect(screen.getByRole("checkbox", { name: water }).matches(":disabled")).toBe(true);
  change(t("templateProductsFor", { category: water }), "16");
  for (const value of ["0", "-1", "1.5", "17"]) {
    change(t("templateProductsPerCategory"), value);
    expect(screen.getByRole("button", { name: t("optionsExport") }).matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: t("templateAssortmentApply") }).matches(":disabled")).toBe(true);
  }
  act(() => useLocale.getState().setLocale("ko"));
  expect(input(t("templateProductsPerCategory")).value).toBe("17");
  change(t("templateProductsPerCategory"), "1");
  expect(choice().category_product_limits).toEqual({ water_sports: 16 });
  fireEvent.click(screen.getByRole("button", { name: t("templateCategoriesRestore") }));
  fireEvent.click(screen.getByRole("button", { name: t("templateProductsShared") }));
  expect(choice().excluded_categories).toEqual([]);
  expect(choice().category_product_limits).toEqual({});
  expect(choice().products_per_category).toBe(1);
});
