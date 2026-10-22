// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES, messages } from "@/shared/i18n/messages";
import { templateName } from "@/shared/i18n/storeLabels";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
let client: QueryClient;
const format = (id: "urban_cvs" | "community_pharmacy"): api.StoreTemplate => ({
  id, name: id === "urban_cvs" ? "City store" : "Community pharmacy", description: messages[`tplDesc_${id}`][0],
  store_type: id === "urban_cvs" ? "convenience" : "pharmacy", grid: [12, 10], racks: 0, skus: 0,
  open_hours: [9, 18], default_style: "aisles", default_design: "classic", default_dining_tables: 0,
});
function Picker() {
  const [value, onChange] = useState(DEFAULT_TEMPLATE_CHOICE);
  return <><TemplatePicker value={value} onChange={onChange} budgetCurrency="USD" /><output data-testid="choice">{JSON.stringify(value)}</output></>;
}
function mount() { return render(<QueryClientProvider client={client}><Picker /></QueryClientProvider>); }
beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getStoreTemplates).mockResolvedValue([format("urban_cvs"), format("community_pharmacy")]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Original <Shop> 茶", type: "convenience", grid_size: [12, 10], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); client.clear(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

it.each(LOCALES)("shows and searches built-in descriptions without changing the chosen format or request in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); mount();
  await screen.findByText(translate(code, "tplDesc_urban_cvs"));
  const searchWords = { en: "prescription", ko: "처방약", zh: "处方药", ja: "処方薬", es: "receta", fr: "ordonnance" };
  fireEvent.change(screen.getByLabelText(translate(code, "findStoreFormat")), { target: { value: searchWords[code] } });
  const choices = within(screen.getByRole("radiogroup", { name: translate(code, "storeFormats") }));
  expect(choices.getAllByRole("radio")).toHaveLength(1);
  fireEvent.click(choices.getByRole("radio", { name: new RegExp(`^${templateName("community_pharmacy", "Community pharmacy", code)}`) }));
  expect(screen.getByText(translate(code, "tplDesc_community_pharmacy"))).toBeTruthy();
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ template_id: "community_pharmacy", currency: "USD" }), expect.any(AbortSignal)));
  const choice = screen.getByTestId("choice").textContent;
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  act(() => useLocale.getState().setLocale(code === "fr" ? "ja" : "fr"));
  const nextLocale = code === "fr" ? "ja" : "fr";
  expect(screen.getByText(translate(nextLocale, "tplDesc_community_pharmacy"))).toBeTruthy();
  expect(screen.getByLabelText(translate(nextLocale, "findStoreFormat")).getAttribute("value")).toBe(searchWords[code]);
  expect(within(screen.getByRole("radiogroup", { name: translate(nextLocale, "storeFormats") })).getAllByRole("radio")).toHaveLength(1);
  expect(screen.getByTestId("choice").textContent).toBe(choice);
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
});

it("keeps the selected language when a delayed catalog resolves and preserves changed server text", async () => {
  let resolve!: (formats: api.StoreTemplate[]) => void;
  vi.mocked(api.getStoreTemplates).mockReturnValueOnce(new Promise(done => { resolve = done; }));
  mount();
  act(() => useLocale.getState().setLocale("ja"));
  const description = "Updated <description> 茶 🛒 {count} — 0–24";
  await act(async () => resolve([{ ...format("urban_cvs"), description }]));
  expect(await screen.findByText(description)).toBeTruthy();
  expect(screen.queryByText(translate("ja", "tplDesc_urban_cvs"))).toBeNull();
  expect(document.querySelector("description")).toBeNull();
  fireEvent.change(screen.getByLabelText(translate("ja", "findStoreFormat")), { target: { value: "茶" } });
  expect(within(screen.getByRole("radiogroup", { name: translate("ja", "storeFormats") })).getAllByRole("radio")).toHaveLength(1);
});

it("does not advertise outdated translated details for a changed catalog entry", async () => {
  useLocale.getState().setLocale("ko");
  vi.mocked(api.getStoreTemplates).mockResolvedValue([{ ...format("urban_cvs"), description: "Revised assortment" }]);
  mount(); await screen.findByText("Revised assortment");
  fireEvent.change(screen.getByLabelText(translate("ko", "findStoreFormat")), { target: { value: "간편식" } });
  expect(within(screen.getByRole("radiogroup", { name: translate("ko", "storeFormats") })).queryAllByRole("radio")).toHaveLength(0);
  expect(screen.getByText("Revised assortment")).toBeTruthy();
});
