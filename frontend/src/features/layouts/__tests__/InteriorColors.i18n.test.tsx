// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";
import { DESIGN_LABELS } from "../optionLabels";
import { TemplatePicker } from "../components/TemplatePicker";
import { InteriorColorControls } from "../components/InteriorColorControls";
import { DEFAULT_TEMPLATE_CHOICE, templateRequest, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
let client: QueryClient;
const apply = vi.fn();
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
const initial: TemplateChoice = { ...DEFAULT_TEMPLATE_CHOICE, design_theme: "coastal", design_colors: { wall: "#000000", floor: "#ffffff" }, seed: -7, requirements: "  原文 café 🛒  " };
beforeEach(() => {
  useLocale.getState().setLocale("en");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.getStoreTemplates).mockResolvedValue([{ id: "urban_cvs", name: "Original", description: "Original", store_type: "convenience", grid: [12, 10], racks: 0, skus: 0, open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0 }]);
  vi.mocked(api.previewStoreTemplate).mockImplementation(async request => ({ id: "preview", name: "Original", type: "store", grid_size: [12, 10], racks: [], weekly_schedule: [], design_theme: request.design_theme ?? "classic", design_colors: request.design_colors }));
});
afterEach(() => { cleanup(); client.clear(); vi.resetAllMocks(); useLocale.getState().setLocale("en"); });
function Form() {
  const [value, onChange] = useState(initial);
  return <><TemplatePicker value={value} onChange={onChange} onApplyDesignToAll={apply} /><output data-testid="raw-design">{JSON.stringify(value)}</output></>;
}
const color = (key: MessageKey) => screen.getByLabelText(t(key)) as HTMLInputElement;
const choice = (): TemplateChoice => JSON.parse(screen.getByTestId("raw-design").textContent!);
it.each(LOCALES)("edits and resets a design in $code without translating color codes or saved choices", async ({ code }) => {
  useLocale.getState().setLocale(code);
  render(<QueryClientProvider client={client}><Form /></QueryClientProvider>);
  await screen.findByRole("img", { name: t("planPreviewImage") });
  const design = screen.getByLabelText(t("layInteriorDesignRealistic")) as HTMLSelectElement;
  expect([...design.options].map(option => option.value)).toEqual(["", ...Object.keys(DESIGN_LABELS)]);
  for (const key of Object.values(DESIGN_LABELS)) expect(screen.getByRole("option", { name: t(key) })).toBeTruthy();
  fireEvent.click(screen.getByText(t("layCustomColorsCount", { count: 2 })));
  expect(color("layColor_wall").value).toBe("#000000");
  fireEvent.change(design, { target: { value: "botanical" } });
  expect(color("layColor_counter").value).toBe("#c3c9ad");
  expect(color("layColor_wall").value).toBe("#000000");
  fireEvent.change(color("layColor_accent"), { target: { value: "#ff00ff" } });
  fireEvent.click(screen.getByRole("button", { name: t("layApplyDesignAllFloors") }));
  expect(apply).toHaveBeenLastCalledWith("botanical", { wall: "#000000", floor: "#ffffff", accent: "#ff00ff" });
  const { requirements: _brief, ...request } = templateRequest(choice());
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(request, expect.any(AbortSignal)));
  const before = JSON.stringify(choice()), calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  act(() => useLocale.getState().setLocale(code === "fr" ? "ja" : "fr"));
  expect(JSON.stringify(choice())).toBe(before);
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  expect(color("layColor_accent").value).toBe("#ff00ff");
  expect(screen.getByText(t("layCustomColorsCount", { count: 3 })).closest("details")?.open).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("layResetWall") }));
  expect(color("layColor_wall").value).toBe("#e4eadf");
  expect(color("layColor_floor").value).toBe("#ffffff");
  expect(screen.getByRole("button", { name: t("layResetWall") }).matches(":disabled")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("layResetAllColors") }));
  expect(choice().design_colors).toBeNull();
  expect(color("layColor_accent").value).toBe("#c8b884");
  expect(color("layColor_floor").value).toBe("#dfe4d4");
  expect(choice().requirements).toBe(initial.requirements);
  expect(choice().seed).toBe(-7);
  expect(screen.getByRole("button", { name: t("layResetAllColors") }).matches(":disabled")).toBe(true);
});

it("retranslates a pending preview failure and retries the same design without changing the draft", async () => {
  const { ApiError } = await import("@/shared/api/errors");
  let reject!: (error: Error) => void;
  vi.mocked(api.previewStoreTemplate).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  render(<QueryClientProvider client={client}><Form /></QueryClientProvider>);
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenCalledTimes(1));
  act(() => useLocale.getState().setLocale("ja"));
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(1);
  await act(async () => reject(new ApiError("Original provider detail <markup>", 422)));
  await screen.findByText(t("requestInvalid"));
  fireEvent.click(screen.getByText(t("requestDetails")));
  expect(screen.getByText("Original provider detail <markup>")).toBeTruthy();
  expect(choice()).toEqual(initial);
  act(() => useLocale.getState().setLocale("fr"));
  expect(screen.getByText(t("requestInvalid"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("tryAgain") }));
  await screen.findByRole("img", { name: t("planPreviewImage") });
  expect(vi.mocked(api.previewStoreTemplate).mock.calls[1]![0]).toEqual(vi.mocked(api.previewStoreTemplate).mock.calls[0]![0]);
  expect(choice()).toEqual(initial);
  expect(screen.queryByText(t("requestInvalid"))).toBeNull();
});

it.each([
  ["en", "Custom interior colors · Changes: 1", "Custom interior colors · Changes: 4"],
  ["es", "Colores personalizados · Cambios: 1", "Colores personalizados · Cambios: 4"],
  ["fr", "Couleurs personnalisées · Modifications : 1", "Couleurs personnalisées · Modifications : 4"],
] as const)("keeps one-color and maximum-color summaries grammatical in %s", (code, one, four) => {
  useLocale.getState().setLocale(code);
  const change = vi.fn();
  const view = render(<InteriorColorControls design="coastal" colors={{ wall: "#000000" }} onChange={change} />);
  expect(screen.getByText(one)).toBeTruthy();
  fireEvent.click(screen.getByText(one));
  expect(screen.getByRole("button", { name: t("layResetFloor") }).matches(":disabled")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("layResetWall") }));
  expect(change).toHaveBeenLastCalledWith({ wall: null });
  view.rerender(<InteriorColorControls design="coastal" colors={null} onChange={change} />);
  expect(screen.getByText(t("layCustomColors"))).toBeTruthy();
  expect(screen.getByRole("button", { name: t("layResetAllColors") }).matches(":disabled")).toBe(true);
  view.rerender(<InteriorColorControls design="coastal" colors={{ wall: "#000000", floor: "#ffffff", accent: "#000001", counter: "#fffffe" }} onChange={change} />);
  expect(screen.getByText(four)).toBeTruthy();
  expect(color("layColor_wall").value).toBe("#000000");
  expect(color("layColor_floor").value).toBe("#ffffff");
});

it("ignores an obsolete design response after changing the design and language", async () => {
  let resolveOld!: (store: Awaited<ReturnType<typeof api.previewStoreTemplate>>) => void;
  vi.mocked(api.previewStoreTemplate).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve; }));
  render(<QueryClientProvider client={client}><Form /></QueryClientProvider>);
  await screen.findByLabelText(t("layInteriorDesignRealistic"));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText(t("layInteriorDesignRealistic")), { target: { value: "retro" } });
  act(() => useLocale.getState().setLocale("zh"));
  await screen.findByRole("img", { name: t("planPreviewImage") });
  expect(vi.mocked(api.previewStoreTemplate).mock.calls[0]![1]?.aborted).toBe(true);
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(2);
  await act(async () => resolveOld({ id: "obsolete", name: "Obsolete", type: "store", grid_size: [3, 3], racks: [], weekly_schedule: [], design_theme: "coastal" }));
  expect(screen.getByRole("img", { name: t("planPreviewImage") }).getAttribute("viewBox")).toBe("-0.2 -0.2 12.4 10.4");
  expect(choice().design_theme).toBe("retro");
  expect(choice().design_colors).toEqual(initial.design_colors);
  expect(choice().requirements).toBe(initial.requirements);
  expect(screen.queryByRole("alert")).toBeNull();
});
