// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { FloorPlanPreview } from "../components/FloorPlanPreview";
import type { Store } from "@/shared/types/domain";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";

const base = { levels: 4, dwell_min: 0, dwell_max: 0, rack_name: "", rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [], rotation: 0 as const };
const store: Store = { id: "floor_茶", name: "Tea & <Books> 🛒", type: "cafe", grid_size: [8, 6], weekly_schedule: [
  { day: 1, is_open: true, open_hour: 0, close_hour: 24 },
  { day: 2, is_open: false, open_hour: 7, close_hour: 20 },
], racks: [
  { ...base, id: "in", type: "entrance", position: [0, 5], shape: [[1]] },
  { ...base, id: "out", type: "exit", position: [0, 5], shape: [[1]], rack_name: "門 & <exit>" },
  { ...base, id: "shelf", type: "shelf", position: [2, 2], shape: [[1]] },
  { ...base, id: "table", type: "table", position: [4, 2], shape: [[1, 1], [1, 1]] },
] };
const areas = [{ label: "Area <script> & 🛒 {name}", x: 3, y: 4, width: 2, height: 1 }];
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); });
async function xml(blob: Blob) {
  const text = await new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
  return new DOMParser().parseFromString(text, "image/svg+xml");
}
it.each(LOCALES)("localizes preview, controls, gate labels and the exported SVG in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  const before = JSON.stringify(store);
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:test-plan");
  const revokeObjectURL = vi.fn(); vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<FloorPlanPreview store={store} areas={areas} />);
  const preview = screen.getByRole("img", { name: t("planPreviewImage") });
  expect(preview.querySelector('[data-gate-kind="shared"] title')?.textContent).toContain(t("planSharedGate"));
  expect(preview.querySelector('[data-gate-kind="shared"] title')?.textContent).toContain("門 & <exit>");
  expect([...preview.querySelectorAll('[data-gate-kind="shared"] text')].map(node => node.textContent)).toEqual([t("planIn"), t("planOut")]);
  fireEvent.click(screen.getByRole("button", { name: t("planExpand") }));
  expect(screen.getByRole("dialog", { name: t("planDetails") })).toBeTruthy();
  expect(screen.getByRole("button", { name: t("planZoomOut") }).matches(":disabled")).toBe(true);
  for (let n = 0; n < 6; n++) fireEvent.click(screen.getByRole("button", { name: t("planZoomIn") }));
  expect(screen.getByRole("button", { name: t("planZoomIn") }).matches(":disabled")).toBe(true);
  expect(screen.getByText(new Intl.NumberFormat(code, { style: "percent" }).format(4), { normalizer: value => value })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("planDownload") }));
  const parsed = await xml(createObjectURL.mock.calls[0]![0]);
  expect(parsed.querySelector("parsererror,script,image,foreignObject")).toBeNull();
  expect(parsed.documentElement.getAttribute("viewBox")).toBe("-1.2 -1.2 9.4 7.4");
  expect(parsed.documentElement.getAttribute("width")).toBe("1600");
  expect(parsed.documentElement.getAttribute("style")).toBeNull();
  expect(parsed.querySelector("title")?.textContent).toBe(t("planExportTitle", { name: store.name, width: 8, height: 6 }));
  expect(parsed.querySelector("desc")?.textContent).toContain(areas[0]!.label);
  expect(parsed.querySelector("desc")?.textContent).toContain(t("planAreaExport", { index: 1, label: areas[0]!.label, width: 2, height: 1, column: 4, row: 5 }));
  expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe("twinstore-8x6-floor-plan.svg");
  expect(JSON.stringify(store)).toBe(before);
  await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:test-plan"));
});
it("uses the current language when exporting after switching without resetting zoom", async () => {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:current-plan");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<FloorPlanPreview store={{ ...store, racks: [], weekly_schedule: [] }} areas={[]} />);
  fireEvent.click(screen.getByRole("button", { name: t("planExpand") }));
  fireEvent.click(screen.getByRole("button", { name: t("planZoomIn") }));
  act(() => useLocale.getState().setLocale("fr"));
  expect(screen.getByText(new Intl.NumberFormat("fr", { style: "percent" }).format(1.5), { normalizer: value => value })).toBeTruthy();
  expect(screen.getByText(t("planCounts", { displays: 0, tables: 0, seats: 0, counters: 0 }))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("planDownload") }));
  const parsed = await xml(createObjectURL.mock.calls[0]![0]);
  expect(parsed.documentElement.getAttribute("aria-label")).toBe(t("planDetailedImage"));
  expect(parsed.querySelector("desc")?.textContent).toContain("Horaires");
  expect(parsed.querySelector("desc")?.textContent).not.toContain("Operating hours");
  await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:current-plan"));
  fireEvent.click(screen.getByRole("button", { name: t("planFit") }));
  expect(screen.getByText(new Intl.NumberFormat("fr", { style: "percent" }).format(1), { normalizer: value => value })).toBeTruthy();
});


it("renders the largest supported grid with boundary gates, missing hours and no reserved areas", () => {
  useLocale.getState().setLocale("ja");
  const racks: Store["racks"] = [
    { ...store.racks[0]!, position: [0, 0] },
    { ...store.racks[1]!, position: [255, 255], rack_name: "" },
  ];
  render(<FloorPlanPreview store={{ ...store, grid_size: [256, 256], racks, weekly_schedule: [] }} areas={[]} />);
  fireEvent.click(screen.getByRole("button", { name: t("planExpand") }));
  const image = screen.getByRole("img", { name: t("planDetailedImage") });
  expect(image.getAttribute("viewBox")).toBe("-1.2 -1.2 257.4 257.4");
  expect(image.querySelector('[data-gate-kind="exit"] title')?.textContent).toBe(t("planGate", { kind: t("planExit"), names: t("planExit"), column: 256, row: 256 }));
  expect(image.querySelectorAll("text")).toHaveLength(514);
  expect(screen.queryByRole("list", { name: t("planAreas") })).toBeNull();
  expect(screen.getByText(t("planHours", { hours: t("hoursNotSet") }))).toBeTruthy();
});
