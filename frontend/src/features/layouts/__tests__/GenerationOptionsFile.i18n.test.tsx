// @vitest-environment jsdom
import { useState } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";
import { GenerationOptionsFile } from "../components/GenerationOptionsFile";
import { DEFAULT_TEMPLATE_CHOICE, type TemplateChoice } from "../templateOptions";
vi.mock("@/shared/api/client", () => ({ validateLayoutPreset: vi.fn(), validateBuildingPreset: vi.fn() }));
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
const original = { ...DEFAULT_TEMPLATE_CHOICE, sourceSetupId: "old-source", requirements: "原文 & café 🛒", seed: -7 };
const preset: api.LayoutPreset = { format: "twinstore-layout-options", version: 1, layout: { template_id: "specialty_cafe", seed: Number.MIN_SAFE_INTEGER, currency: "JPY", requirements: "Keep 原文 {seed}", weekly_hours: Array.from({ length: 7 }, (_, index) => ({ day: index + 1, is_open: true, open_hour: 0, close_hour: 24 })) } };
beforeEach(() => { useLocale.getState().setLocale("en"); vi.mocked(api.validateLayoutPreset).mockResolvedValue(preset); });
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.restoreAllMocks(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); });
function Form() {
  const [value, onChange] = useState<TemplateChoice>(original);
  return <><GenerationOptionsFile kind="layout" canExport value={value} onChange={onChange} /><output data-testid="choice">{JSON.stringify(value)}</output></>;
}
function upload(source: string) {
  const file = Object.assign(new File([source], "設定 🛒.json", { type: "application/json" }), { text: async () => source });
  fireEvent.change(screen.getByLabelText(t("optionsLayoutFile")), { target: { files: [file] } });
}
async function read(blob: Blob) {
  return new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
}
it.each(LOCALES)("imports and exports portable settings in $code with unchanged JSON identities and Unicode text", async ({ code }) => {
  useLocale.getState().setLocale(code);
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:options"); const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<Form />);
  expect(screen.getByText(t("optionsLayoutHint"))).toBeTruthy();
  upload("\uFEFF" + JSON.stringify(preset));
  await waitFor(() => expect(JSON.parse(screen.getByTestId("choice").textContent!).templateId).toBe("specialty_cafe"));
  expect(api.validateLayoutPreset).toHaveBeenCalledWith(preset, expect.any(AbortSignal));
  fireEvent.click(screen.getByRole("button", { name: t("optionsExport") }));
  const exported = JSON.parse(await read(createObjectURL.mock.calls[0]![0]));
  expect(exported).toMatchObject(preset);
  expect(exported.layout).not.toHaveProperty("source_setup_id");
  expect(exported.layout).not.toHaveProperty("name");
  expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe("twinstore-specialty_cafe-options.json");
  await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:options"));
});
it("retranslates file errors and a pending server failure without resetting the current options", async () => {
  render(<Form />); const before = screen.getByTestId("choice").textContent;
  upload("{no JSON}"); await screen.findByText(t("optionsInvalidJson"));
  act(() => useLocale.getState().setLocale("ko"));
  expect(screen.getByText(t("optionsInvalidJson"))).toBeTruthy();
  upload("한".repeat(22000)); await screen.findByText(t("optionsTooLarge", { limit: 64 }));
  expect(api.validateLayoutPreset).not.toHaveBeenCalled();
  let reject!: (error: Error) => void;
  vi.mocked(api.validateLayoutPreset).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  upload("{}"); await waitFor(() => expect(api.validateLayoutPreset).toHaveBeenCalledOnce());
  act(() => useLocale.getState().setLocale("fr"));
  expect(screen.getByRole("button", { name: t("optionsChecking") }).matches(":disabled")).toBe(true);
  reject(new ApiError("Original diagnostic: invalid floor", 422));
  await screen.findByText(t("requestInvalid"));
  expect(screen.getByText("Original diagnostic: invalid floor")).toBeTruthy();
  expect(screen.getByTestId("choice").textContent).toBe(before);
  upload("{}" + " ".repeat(64 * 1024 - 2));
  await waitFor(() => expect(JSON.parse(screen.getByTestId("choice").textContent!).templateId).toBe("specialty_cafe"));
  expect(api.validateLayoutPreset).toHaveBeenCalledTimes(2);
});
