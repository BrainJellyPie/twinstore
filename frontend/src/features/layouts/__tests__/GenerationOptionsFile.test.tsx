// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { GenerationOptionsFile } from "../components/GenerationOptionsFile";
import { DEFAULT_TEMPLATE_CHOICE, type BuildingFloorChoice, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ validateLayoutPreset: vi.fn(), validateBuildingPreset: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const value: TemplateChoice = { ...DEFAULT_TEMPLATE_CHOICE, templateId: "community_pharmacy", sourceSetupId: "setup_old",
  width: 24, height: 20, currency: "JPY", style: "cross", seed: 7, aisle_width: 3, max_shelf_run: 2, design_theme: "terracotta", checkout_wall: "right",
  reserved_areas: [{ label: "Consultation", x: 2, y: 2, width: 3, height: 3 }], requirements: "Keep signs readable.", excluded_categories: ["wellness"] };

function upload(source: string) {
  const file = Object.assign(new File([source], "floor-options.json", { type: "application/json" }), { text: async () => source });
  fireEvent.change(screen.getByLabelText("Import layout options file"), { target: { files: [file] } });
}

it("exports portable settings and brief without source links or submitting the form", async () => {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:layout-options");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const submit = vi.fn();
  render(<form onSubmit={submit}><GenerationOptionsFile kind="layout" value={value} onChange={vi.fn()} canExport /></form>);
  fireEvent.click(screen.getByRole("button", { name: "Export options" }));
  expect(submit).not.toHaveBeenCalled();
  expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe("twinstore-community_pharmacy-options.json");
  const blob = createObjectURL.mock.calls[0]?.[0];
  if (!blob) throw new Error("Missing download");
  const source = await new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob);
  });
  const exported = JSON.parse(source) as api.LayoutPreset;
  expect(exported).toMatchObject({ format: "twinstore-layout-options", version: 1, layout: {
    template_id: "community_pharmacy", currency: "JPY", seed: 7, style: "cross", width: 24, height: 20,
    aisle_width: 3, max_shelf_run: 2, design_theme: "terracotta", reserved_areas: value.reserved_areas,
    requirements: "Keep signs readable.", excluded_categories: ["wellness"], checkout_wall: "right",
  } });
  expect(exported.layout).not.toHaveProperty("source_setup_id");
  expect(exported.layout).not.toHaveProperty("name");
  await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:layout-options"));
});

it("applies server-normalized options and clears values inherited from the previous floor", async () => {
  const onChange = vi.fn();
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "specialty_cafe", seed: 3, currency: "KRW", width: 18 } });
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload('\uFEFF{"format":"twinstore-layout-options","version":1,"layout":{"template_id":"specialty_cafe","width":"18"}}');
  await waitFor(() => expect(onChange).toHaveBeenCalledOnce());
  expect(api.validateLayoutPreset).toHaveBeenCalledWith(expect.objectContaining({ layout: { template_id: "specialty_cafe", width: "18" } }), expect.any(AbortSignal));
  const imported = onChange.mock.calls[0]?.[0] as TemplateChoice;
  expect(imported).toMatchObject({ templateId: "specialty_cafe", seed: 3, currency: "KRW", width: 18, reserved_areas: [], style: null, design_theme: null });
  expect(imported.sourceSetupId).toBeUndefined();
  expect(imported.height).toBeUndefined();
  expect(imported.requirements).toBeUndefined();
  expect(imported.excluded_categories).toEqual([]);
});

it("preserves current options on invalid JSON, oversized files and server validation failures", async () => {
  const onChange = vi.fn();
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload("not JSON");
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("not valid JSON"));
  upload(" ".repeat(64 * 1024 + 1));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("smaller than 64 KB"));
  expect(api.validateLayoutPreset).not.toHaveBeenCalled();
  vi.mocked(api.validateLayoutPreset).mockRejectedValue(new Error("Not enough room for 48 dining tables."));
  upload("{}");
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Not enough room"));
  expect(onChange).not.toHaveBeenCalled();
});

it("ignores a late validation response after switching away from the floor", async () => {
  let resolve: ((preset: api.LayoutPreset) => void) | undefined;
  vi.mocked(api.validateLayoutPreset).mockImplementation(() => new Promise((done) => { resolve = done; }));
  const onChange = vi.fn();
  const { unmount } = render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload("{}");
  await waitFor(() => expect(api.validateLayoutPreset).toHaveBeenCalledOnce());
  const signal = vi.mocked(api.validateLayoutPreset).mock.calls[0]?.[1];
  unmount();
  expect(signal?.aborted).toBe(true);
  resolve?.({ format: "twinstore-layout-options", version: 1, layout: { template_id: "urban_cvs", seed: 0, currency: "USD" } });
  await Promise.resolve();
  expect(onChange).not.toHaveBeenCalled();
});

it("exports all floors in order with independent settings and no old source IDs", async () => {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:building-options");
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const floors: BuildingFloorChoice[] = [{ label: "Ground pharmacy", choice: value },
    { label: "Upstairs café", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "specialty_cafe", currency: "KRW", seed: 12, sourceSetupId: "old_cafe", dining_tables: 4 } }];
  render(<GenerationOptionsFile kind="building" value={floors} onChange={vi.fn()} canExport />);
  fireEvent.click(screen.getByRole("button", { name: "Export building options" }));
  expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe("twinstore-building-options.json");
  const blob = createObjectURL.mock.calls[0]?.[0];
  if (!blob) throw new Error("Missing building download");
  const source = await new Promise<string>((resolve) => {
    const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob);
  });
  const exported = JSON.parse(source) as api.BuildingPreset;
  expect(exported.format).toBe("twinstore-building-options");
  expect(exported.floors.map((floor) => floor.label)).toEqual(["Ground pharmacy", "Upstairs café"]);
  expect(exported.floors[0]?.layout).toMatchObject({ width: 24, currency: "JPY", reserved_areas: value.reserved_areas, requirements: value.requirements });
  expect(exported.floors[1]?.layout).toMatchObject({ template_id: "specialty_cafe", currency: "KRW", seed: 12, dining_tables: 4 });
  for (const floor of exported.floors) expect(floor.layout).not.toHaveProperty("source_setup_id");
});

it("replaces the complete floor list only after every imported floor passes validation", async () => {
  const onChange = vi.fn();
  const floors: BuildingFloorChoice[] = [{ label: "Existing ground", choice: value }, { label: "Existing upper", choice: value }];
  const normalized: api.BuildingPreset = { format: "twinstore-building-options", version: 1, floors: [
    { label: "Books", layout: { template_id: "bookstore", seed: 0, currency: "USD" } },
    { label: "Tea", layout: { template_id: "tea_lounge", seed: 4, currency: "JPY", dining_tables: 3 } },
  ] };
  vi.mocked(api.validateBuildingPreset).mockRejectedValueOnce(new Error("Floor 2 (Tea): not enough room"));
  render(<GenerationOptionsFile kind="building" value={floors} onChange={onChange} canExport />);
  const file = Object.assign(new File(["{}"], "building.json"), { text: async () => "{}" });
  fireEvent.change(screen.getByLabelText("Import building options file"), { target: { files: [file] } });
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Floor 2 (Tea)"));
  expect(onChange).not.toHaveBeenCalled();
  vi.mocked(api.validateBuildingPreset).mockResolvedValueOnce(normalized);
  fireEvent.change(screen.getByLabelText("Import building options file"), { target: { files: [file] } });
  await waitFor(() => expect(onChange).toHaveBeenCalledOnce());
  const imported = onChange.mock.calls[0]?.[0] as BuildingFloorChoice[];
  expect(imported.map((floor) => floor.label)).toEqual(["Books", "Tea"]);
  expect(imported[1]?.choice).toMatchObject({ templateId: "tea_lounge", currency: "JPY", dining_tables: 3, reserved_areas: [] });
  expect(imported[0]?.choice.sourceSetupId).toBeUndefined();
  expect(imported[0]?.choice.width).toBeUndefined();
  expect(api.validateLayoutPreset).not.toHaveBeenCalled();
});
