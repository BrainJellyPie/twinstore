// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/rackCopy";
import { ApiError } from "@/shared/api/errors";
import { RackCopy } from "../RackCopy";
import { rackCopyReason } from "../rackCopyLabels";
import { LOCALES, type Locale, type MessageKey } from "@/shared/i18n/messages";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { useSimulationStore } from "@/stores/simulationStore";

vi.mock("@/shared/api/rackCopy", () => ({ getRackCopyOptions: vi.fn(), previewRackCopy: vi.fn(), saveRackCopy: vi.fn() }));
const source = { id: "棚_茶", name: "Café 🍵", type: "fridge", placements: 2, reason: null };
const target = { ...source, id: "destination", name: "Empty" };
const options: api.RackCopyOptions = { source_sha256: "a".repeat(64), currency: "USD", source_rack_id: null, sources: [source], targets: [] };
const report: api.RackCopyPreview = { source_name: source.name, slots: [{ block: 0, face: "W", level: 4,
  items: [{ sku: "茶", name: "Tea", price: 231, regular_price: 299, promo: "Local", image_url: "/tea.png" },
    { sku: "0", name: "Sample", price: 0, regular_price: 0, promo: "", image_url: null }] }], targets: [target], placements_added: 2 };
let qc: QueryClient;
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  useLocale.getState().setLocale("en");
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getRackCopyOptions).mockImplementation(async (_p, _s, id) => ({ ...options, source_rack_id: id || null,
    targets: id ? [target, { ...source, reason: "This is the source rack", reason_code: "source_rack" }] : [] }));
  vi.mocked(api.previewRackCopy).mockResolvedValue(report);
  vi.mocked(api.saveRackCopy).mockResolvedValue({ setup_id: "setup_copied", placements_added: 2 });
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); useSimulationStore.getState().reset(); useLocale.getState().setLocale("en"); });
async function open(locale: Locale = "en") {
  useLocale.getState().setLocale(locale);
  render(<QueryClientProvider client={qc}><RackCopy pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: t("copyTitle") }));
  await screen.findByRole("option", { name: /Café 🍵/ });
  fireEvent.change(screen.getByRole("combobox", { name: t("copyFrom") }), { target: { value: source.id } });
  await screen.findByRole("checkbox", { name: t("copyToRack", { id: target.id }) });
}
async function preview() {
  fireEvent.click(screen.getByRole("checkbox", { name: t("copyToRack", { id: target.id }) }));
  fireEvent.click(screen.getByRole("button", { name: t("copyPreview") }));
  await screen.findByRole("button", { name: t("copySave") });
}
it.each(LOCALES)("completes the full copy flow in $label without translating stored identities", async ({ code }) => {
  await open(code);
  expect(screen.getByText(t("copyHelp"))).toBeTruthy();
  expect(screen.getByText(t("copyReasonSource"))).toBeTruthy();
  expect(screen.getByRole("checkbox", { name: t("copyToRack", { id: source.id }) }).matches(":disabled")).toBe(true);
  await preview();
  const section = screen.getByRole("region", { name: t("copyPreviewTitle") });
  expect(section.textContent).toContain(t("copySection", { block: 1, face: t("fixtureWest"), level: 4 }));
  expect(section.textContent).toContain("Tea · 茶"); expect(section.textContent).toContain("Local");
  expect(section.textContent).toContain(t("copyImageRetained")); expect(section.textContent).toContain(t("photosNone"));
  expect(section.textContent).not.toContain("{count}");
  fireEvent.click(screen.getByRole("button", { name: t("copySave") }));
  fireEvent.click(await screen.findByRole("button", { name: t("copyOpen") }));
  expect(useSimulationStore.getState().selectedSetupId).toBe("setup_copied");
  expect(vi.mocked(api.saveRackCopy).mock.calls[0]![2]).toEqual({ source_sha256: options.source_sha256, currency: "USD",
    source_rack_id: "棚_茶", target_rack_ids: ["destination"], request_id: expect.stringMatching(/^[a-f0-9]{32}$/) });
});
it("retains a localized accent-insensitive search and hidden selections through a language switch", async () => {
  await open("fr");
  fireEvent.change(screen.getByLabelText(t("copySearch")), { target: { value: "  refrigerateur  " } });
  fireEvent.click(screen.getByRole("checkbox", { name: t("copyToRack", { id: target.id }) }));
  act(() => useLocale.getState().setLocale("ja"));
  expect((screen.getByLabelText(t("copySearch")) as HTMLInputElement).value).toBe("  refrigerateur  ");
  expect((screen.getByRole("checkbox", { name: t("copyToRack", { id: target.id }) }) as HTMLInputElement).checked).toBe(true);
  fireEvent.change(screen.getByLabelText(t("copySearch")), { target: { value: "no result" } });
  expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: t("copyPreview") }));
  await screen.findByRole("button", { name: t("copySave") });
  expect(vi.mocked(api.previewRackCopy).mock.calls[0]![2].target_rack_ids).toEqual(["destination"]);
});
it("changes language during preview and uncertain save without changing the snapshot or retry identity", async () => {
  let finishPreview!: (value: api.RackCopyPreview) => void;
  let rejectSave!: (error: Error) => void;
  vi.mocked(api.previewRackCopy).mockReturnValueOnce(new Promise(resolve => { finishPreview = resolve; }));
  vi.mocked(api.saveRackCopy).mockReturnValueOnce(new Promise((_resolve, reject) => { rejectSave = reject; }));
  await open();
  fireEvent.click(screen.getByRole("checkbox", { name: t("copyToRack", { id: target.id }) }));
  fireEvent.click(screen.getByRole("button", { name: t("copyPreview") }));
  await waitFor(() => expect(api.previewRackCopy).toHaveBeenCalledTimes(1));
  act(() => useLocale.getState().setLocale("ko"));
  expect(screen.getByRole("combobox", { name: t("copyFrom") }).matches(":disabled")).toBe(true);
  await act(async () => finishPreview(report));
  fireEvent.click(await screen.findByRole("button", { name: t("copySave") }));
  await waitFor(() => expect(api.saveRackCopy).toHaveBeenCalledTimes(1));
  act(() => useLocale.getState().setLocale("fr"));
  expect(screen.getByRole("button", { name: t("copySaving") }).matches(":disabled")).toBe(true);
  await act(async () => rejectSave(new ApiError("Layout changed", 409)));
  await screen.findByText(t("requestConflict"));
  expect(screen.getByText(t("copyUncertain"))).toBeTruthy();
  act(() => useLocale.getState().setLocale("zh"));
  expect(screen.getByText(t("requestConflict"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("copyRetrySave") }));
  await screen.findByRole("button", { name: t("copyOpen") });
  expect(vi.mocked(api.saveRackCopy).mock.calls[1]![2]).toEqual(vi.mocked(api.saveRackCopy).mock.calls[0]![2]);
});
it.each(LOCALES)("handles empty sources and loading errors in $label", async ({ code }) => {
  vi.mocked(api.getRackCopyOptions).mockRejectedValueOnce(new ApiError("No layout", 404)).mockResolvedValueOnce({ ...options, sources: [] });
  useLocale.getState().setLocale(code);
  render(<QueryClientProvider client={qc}><RackCopy pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: t("copyTitle") }));
  await screen.findByText(t("requestMissing"));
  fireEvent.click(screen.getByRole("button", { name: t("copyRetry") }));
  await screen.findByText(t("copyNoSource"));
  expect(screen.getByRole("button", { name: t("copyPreview") }).matches(":disabled")).toBe(true);
  expect(api.previewRackCopy).not.toHaveBeenCalled(); expect(api.saveRackCopy).not.toHaveBeenCalled();
});
it("translates stable and legacy reasons but preserves unknown future diagnostics", () => {
  for (const { code } of LOCALES) {
    expect(rackCopyReason({ ...target, reason: "Already contains products; kept unchanged" }, code)).toBe(translate(code, "copyReasonOccupied"));
    expect(rackCopyReason({ ...target, reason: "new backend wording", reason_code: "source_inaccessible" }, code)).toBe(translate(code, "copyReasonBlockedSource"));
    expect(rackCopyReason({ ...target, reason: "future reason", reason_code: "__proto__" }, code)).toBe("future reason");
    expect(rackCopyReason(target, code)).toBeNull();
  }
});
