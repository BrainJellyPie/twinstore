// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
const formats: api.StoreTemplate[] = [
  { id: "urban_cvs", name: "City store", description: "Groceries", store_type: "convenience", grid: [12, 10], racks: 10, skus: 40, open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0 },
  { id: "community_pharmacy", name: "Community pharmacy", description: "Wellness", store_type: "pharmacy", grid: [14, 12], racks: 12, skus: 50, open_hours: [9, 21], default_style: "spine", default_design: "minimal", default_dining_tables: 0 },
  { id: "specialty_cafe", name: "Specialty café", description: "Coffee", store_type: "cafe", grid: [18, 14], racks: 20, skus: 40, open_hours: [7, 22], default_style: "perimeter", default_design: "warm", default_dining_tables: 6 },
];
const formatName = (key: MessageKey) => (name: string) => name.startsWith(translate(useLocale.getState().locale, key));
const selected = vi.fn();
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  useLocale.getState().setLocale("en"); vi.mocked(api.getStoreTemplates).mockResolvedValue(formats);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Preview", type: "convenience", grid_size: [12, 10], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });
function Picker() {
  const [value, onChange] = useState<TemplateChoice>({ ...DEFAULT_TEMPLATE_CHOICE, width: 24, currency: "JPY", requirements: "Keep the entrance clear" });
  return <TemplatePicker value={value} onChange={onChange} onTemplateSelected={selected} defaultCustomizationOpen={false} showOperatingHours={false} />;
}
function show({ form = false }: { form?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  const submit = vi.fn();
  return { ...render(<QueryClientProvider client={client}>{form
    ? <form onSubmit={(event) => { event.preventDefault(); submit(); }}><Picker /></form>
    : <Picker />}</QueryClientProvider>), client, submit };
}

it.each(LOCALES)("exposes one selected radio and preserves overrides when selecting in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); show();
  const city = await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") });
  expect(screen.getByRole("radiogroup", { name: translate(code, "storeFormats") })).toBeTruthy();
  expect(city.getAttribute("aria-checked")).toBe("true");
  const pharmacy = screen.getByRole("radio", { name: formatName("tpl_community_pharmacy") }); fireEvent.click(pharmacy);
  expect(pharmacy.getAttribute("aria-checked")).toBe("true"); expect(city.getAttribute("aria-checked")).toBe("false");
  fireEvent.click(pharmacy); expect(selected).toHaveBeenCalledOnce();
  expect(selected).toHaveBeenCalledWith(expect.objectContaining({ id: "community_pharmacy", store_type: "pharmacy" }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ template_id: "community_pharmacy", width: 24, currency: "JPY" }), expect.any(AbortSignal)));
});

it("selects with both arrow directions and wraps without discarding custom dimensions", async () => {
  show(); const city = await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") });
  const pharmacy = screen.getByRole("radio", { name: formatName("tpl_community_pharmacy") }); const cafe = screen.getByRole("radio", { name: formatName("tpl_specialty_cafe") });
  city.focus();
  for (const [key, target] of [["ArrowRight", pharmacy], ["ArrowDown", cafe], ["ArrowRight", city], ["ArrowLeft", cafe], ["ArrowUp", pharmacy]] as const) {
    fireEvent.keyDown(document.activeElement!, { key });
    await waitFor(() => expect(document.activeElement).toBe(target));
    fireEvent.keyUp(target, { key });
    expect(target.getAttribute("aria-checked")).toBe("true");
    expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("24");
  }
});

it("selects on a fast arrow press even when keyup arrives before deferred focus", async () => {
  show(); const city = await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") }); const pharmacy = screen.getByRole("radio", { name: formatName("tpl_community_pharmacy") });
  city.focus(); fireEvent.keyDown(city, { key: "ArrowRight" }); fireEvent.keyUp(city, { key: "ArrowRight" });
  await waitFor(() => expect(document.activeElement).toBe(pharmacy));
  expect(pharmacy.getAttribute("aria-checked")).toBe("true");
  expect(selected).toHaveBeenCalledOnce();
});

it("advances on consecutive fast key presses before any deferred focus work", async () => {
  show(); const city = await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") }); const cafe = screen.getByRole("radio", { name: formatName("tpl_specialty_cafe") });
  city.focus();
  for (let i = 0; i < 2; i++) {
    fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" }); fireEvent.keyUp(document.activeElement!, { key: "ArrowRight" });
  }
  await waitFor(() => expect(document.activeElement).toBe(cafe));
  expect(cafe.getAttribute("aria-checked")).toBe("true");
});

it("supports Home/End focus and Enter selection without submitting a form", async () => {
  show(); const city = await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") }); const cafe = screen.getByRole("radio", { name: formatName("tpl_specialty_cafe") });
  city.focus(); fireEvent.keyDown(city, { key: "End" }); await waitFor(() => expect(document.activeElement).toBe(cafe));
  fireEvent.keyDown(cafe, { key: "Enter" }); expect(cafe.getAttribute("aria-checked")).toBe("true");
  fireEvent.keyDown(cafe, { key: "Home" }); await waitFor(() => expect(document.activeElement).toBe(city));
  fireEvent.keyDown(city, { key: "Enter" }); expect(city.getAttribute("aria-checked")).toBe("true");
  expect((screen.getByLabelText("Price currency") as HTMLSelectElement).value).toBe("JPY");
});

it("retains an off-list selection through filters and empty results until an explicit choice", async () => {
  show(); await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") });
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  const search = screen.getByLabelText("Find a store format"); fireEvent.change(search, { target: { value: "pharmacy" } });
  const pharmacy = screen.getByRole("radio", { name: formatName("tpl_community_pharmacy") }); pharmacy.focus();
  expect(pharmacy.getAttribute("aria-checked")).toBe("false"); expect(selected).not.toHaveBeenCalled();
  fireEvent.change(search, { target: { value: "missing" } }); expect(screen.queryByRole("radio")).toBeNull();
  fireEvent.keyDown(search, { key: "Escape" });
  expect(screen.getByRole("radio", { name: formatName("tpl_urban_cvs") }).getAttribute("aria-checked")).toBe("true");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
});

it("keeps the selected, focused template and overrides after a language switch", async () => {
  show(); const pharmacy = await screen.findByRole("radio", { name: formatName("tpl_community_pharmacy") }); fireEvent.click(pharmacy); pharmacy.focus();
  act(() => useLocale.getState().setLocale("ja"));
  expect(document.activeElement).toBe(pharmacy); expect(pharmacy.getAttribute("aria-checked")).toBe("true");
  expect(screen.getByRole("radiogroup", { name: translate("ja", "storeFormats") })).toBeTruthy();
  expect((screen.getByLabelText(translate("ja", "widthCells")) as HTMLInputElement).value).toBe("24");
});

it("keeps invalid custom dimensions until corrected after a keyboard choice", async () => {
  show(); const city = await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "99" } });
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  city.focus(); fireEvent.keyDown(city, { key: "ArrowRight" });
  const pharmacy = screen.getByRole("radio", { name: formatName("tpl_community_pharmacy") });
  await waitFor(() => expect(pharmacy.getAttribute("aria-checked")).toBe("true")); fireEvent.keyUp(pharmacy, { key: "ArrowRight" });
  expect((screen.getByLabelText("Width (8–40 cells)") as HTMLInputElement).value).toBe("99");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "24" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ template_id: "community_pharmacy", width: 24 }), expect.any(AbortSignal)));
});

it("does not replace a selection when the catalog removes it or becomes empty", async () => {
  const { client } = show(); await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") });
  act(() => client.setQueryData(["store-templates"], formats.slice(1)));
  await waitFor(() => expect(screen.queryByRole("radio", { name: formatName("tpl_urban_cvs") })).toBeNull());
  expect(screen.getAllByRole("radio").every(radio => radio.getAttribute("aria-checked") === "false")).toBe(true);
  expect(selected).not.toHaveBeenCalled();
  act(() => client.setQueryData(["store-templates"], []));
  await waitFor(() => expect(screen.queryByRole("radio")).toBeNull());
  act(() => client.setQueryData(["store-templates"], formats));
  expect((await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") })).getAttribute("aria-checked")).toBe("true");
  expect(selected).not.toHaveBeenCalled();
});

it("waits for late formats without selecting another template", async () => {
  let resolve!: (formats: api.StoreTemplate[]) => void;
  vi.mocked(api.getStoreTemplates).mockReturnValueOnce(new Promise(done => { resolve = done; }));
  show(); expect(screen.queryByRole("radio")).toBeNull();
  await act(async () => resolve(formats));
  expect((await screen.findByRole("radio", { name: formatName("tpl_urban_cvs") })).getAttribute("aria-checked")).toBe("true");
  expect(selected).not.toHaveBeenCalled();
});

it("selects with Enter inside a form without submitting, including repeated selection", async () => {
  const { submit } = show({ form: true });
  const pharmacy = await screen.findByRole("radio", { name: formatName("tpl_community_pharmacy") }); pharmacy.focus();
  fireEvent.keyDown(pharmacy, { key: "Enter" }); fireEvent.keyDown(pharmacy, { key: "Enter" });
  expect(pharmacy.getAttribute("aria-checked")).toBe("true");
  expect(selected).toHaveBeenCalledOnce(); expect(submit).not.toHaveBeenCalled();
});

it.each([{ isComposing: true }, { keyCode: 229 }])("does not select a format on an IME Enter event %j", async (flags) => {
  show({ form: true }); const pharmacy = await screen.findByRole("radio", { name: formatName("tpl_community_pharmacy") }); pharmacy.focus();
  fireEvent.keyDown(pharmacy, { key: "Enter", ...flags });
  expect(pharmacy.getAttribute("aria-checked")).toBe("false"); expect(selected).not.toHaveBeenCalled();
  fireEvent.keyDown(pharmacy, { key: "Enter" });
  expect(pharmacy.getAttribute("aria-checked")).toBe("true"); expect(selected).toHaveBeenCalledOnce();
});
