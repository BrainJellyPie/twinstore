// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { GenerationOptionsFile } from "../components/GenerationOptionsFile";
import { DEFAULT_TEMPLATE_CHOICE, type BuildingFloorChoice, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ validateLayoutPreset: vi.fn(), validateBuildingPreset: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const weekly_hours = Array.from({ length: 7 }, (_, index) => ({ day: index + 1, is_open: index < 5, open_hour: index < 5 ? 8 : 10, close_hour: index < 5 ? 20 : 16 }));
const value: TemplateChoice = { ...DEFAULT_TEMPLATE_CHOICE, templateId: "community_pharmacy", sourceSetupId: "setup_old",
  weekly_hours, seating_zone: "near_entrance", table_clearance_x: 4, table_clearance_y: 1, width: 24, height: 20, currency: "JPY", style: "cross", seed: 7, aisle_width: 3, max_shelf_run: 2, design_theme: "terracotta", design_colors: { wall: "#123456", floor: "#abcdef", accent: null }, checkout_wall: "right",
  reserved_areas: [{ label: "Consultation", x: 2, y: 2, width: 3, height: 3 }], requirements: "Keep signs readable.", excluded_categories: ["wellness"], products_per_category: 3, category_product_limits: { pharmacy_care: 1, wellness: 12 }, gate_wall: "right", exit_position: "center", exit_wall: "back" };

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
    weekly_hours, seating_zone: "near_entrance", table_clearance_x: 4, table_clearance_y: 1, template_id: "community_pharmacy", currency: "JPY", seed: 7, style: "cross", width: 24, height: 20,
    aisle_width: 3, max_shelf_run: 2, design_theme: "terracotta", design_colors: { wall: "#123456", floor: "#abcdef", accent: null }, reserved_areas: value.reserved_areas,
    requirements: "Keep signs readable.", excluded_categories: ["wellness"], checkout_wall: "right", products_per_category: 3, category_product_limits: { pharmacy_care: 1, wellness: 12 }, gate_wall: "right", exit_position: "center", exit_wall: "back",
  } });
  expect(exported.layout).not.toHaveProperty("source_setup_id");
  expect(exported.layout).not.toHaveProperty("name");
  await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:layout-options"));
});

it("applies server-normalized options and clears values inherited from the previous floor", async () => {
  const onChange = vi.fn();
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "specialty_cafe", seed: 3, currency: "KRW", width: 18, seating_zone: "away_from_entrance" } });
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload('\uFEFF{"format":"twinstore-layout-options","version":1,"layout":{"template_id":"specialty_cafe","width":"18"}}');
  await waitFor(() => expect(onChange).toHaveBeenCalledOnce());
  expect(api.validateLayoutPreset).toHaveBeenCalledWith(expect.objectContaining({ layout: { template_id: "specialty_cafe", width: "18" } }), expect.any(AbortSignal));
  const imported = onChange.mock.calls[0]?.[0] as TemplateChoice;
  expect(imported).toMatchObject({ templateId: "specialty_cafe", seed: 3, currency: "KRW", width: 18, seating_zone: "away_from_entrance", reserved_areas: [], style: null, design_theme: null });
  expect(imported.sourceSetupId).toBeUndefined();
  expect(imported.height).toBeUndefined();
  expect(imported.requirements).toBeUndefined();
  expect(imported.excluded_categories).toEqual([]);
  expect(imported.products_per_category).toBeNull();
  expect(imported.table_clearance_x).toBeNull();
  expect(imported.table_clearance_y).toBeNull();
  expect(imported.category_product_limits).toEqual({});
  expect(imported.gate_wall).toBe("front");
  expect(imported.exit_wall).toBeNull();
});

it("preserves current options on invalid JSON, oversized files and server validation failures", async () => {
  const onChange = vi.fn();
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload("not JSON");
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("not valid JSON"));
  upload(" ".repeat(64 * 1024 + 1));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("no larger than 64 KB"));
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

it.each([Number.MAX_SAFE_INTEGER + 1, Number.MIN_SAFE_INTEGER - 1])("keeps the current layout when a validated file contains unsafe seed %s", async (seed) => {
  const onChange = vi.fn();
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "specialty_cafe", seed, currency: "USD" } });
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload(JSON.stringify({ format: "twinstore-layout-options", version: 1, layout: { template_id: "specialty_cafe", seed } }));
  await screen.findByText("This options file has a seed outside the supported whole-number range. Current settings were kept.");
  expect(onChange).not.toHaveBeenCalled();
});

it.each([Number.MIN_SAFE_INTEGER, Number.MAX_SAFE_INTEGER])("imports exact boundary seed %s", async (seed) => {
  const onChange = vi.fn();
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "specialty_cafe", seed, currency: "USD" } });
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload(JSON.stringify({ layout: { template_id: "specialty_cafe", seed } }));
  await waitFor(() => expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ seed })));
});

it.each([[0, Number.MAX_SAFE_INTEGER + 1], [1, Number.MAX_SAFE_INTEGER + 1], [0, Number.MIN_SAFE_INTEGER - 1], [1, Number.MIN_SAFE_INTEGER - 1]])("rejects an entire building when floor %s has unsafe seed %s", async (index, seed) => {
  const onChange = vi.fn();
  const normalized: api.BuildingPreset = { format: "twinstore-building-options", version: 1, floors: [
    { label: "Ground", layout: { template_id: "urban_cvs", seed: index === 0 ? seed : 42, currency: "USD" } },
    { label: "Upper", layout: { template_id: "specialty_cafe", seed: index === 1 ? seed : 42, currency: "JPY" } },
  ] };
  vi.mocked(api.validateBuildingPreset).mockResolvedValue(normalized);
  render(<GenerationOptionsFile kind="building" value={[{ label: "Keep downstairs", choice: value }, { label: "Keep upstairs", choice: value }]} onChange={onChange} canExport />);
  const source = JSON.stringify(normalized), file = Object.assign(new File([source], "seeds.json"), { text: async () => source });
  fireEvent.change(screen.getByLabelText("Import building options file"), { target: { files: [file] } });
  await screen.findByText("This options file has a seed outside the supported whole-number range. Current settings were kept.");
  expect(onChange).not.toHaveBeenCalled();
});

it.each(["9007199254740990.1", "9007199254740991.1", "-9007199254740990.1", "-9007199254740991.1",
  "1e-400", "-1e-400", "1.0000000000000001", "90071992547409901e-1"])("rejects rounded seed literal %s before validating or replacing layout options", async (literal) => {
  const onChange = vi.fn();
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "urban_cvs", seed: Number(literal), currency: "USD" } });
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload(`{"layout":{"template_id":"urban_cvs","seed":${literal}}}`);
  await screen.findByRole("alert");
  expect(api.validateLayoutPreset).not.toHaveBeenCalled(); expect(onChange).not.toHaveBeenCalled();
});

it.each([0, 1])("preserves every building floor when floor %s contains a rounded seed", async (index) => {
  const onChange = vi.fn();
  vi.mocked(api.validateBuildingPreset).mockResolvedValue({ format: "twinstore-building-options", version: 1,
    floors: [0, 1].map((i) => ({ label: `Floor ${i}`, layout: { template_id: "urban_cvs", seed: i === index ? 9007199254740990 : 42, currency: "USD" } })) });
  render(<GenerationOptionsFile kind="building" value={[{ label: "Keep ground", choice: value }, { label: "Keep upper", choice: value }]} onChange={onChange} canExport />);
  const source = `{"floors":[${[0, 1].map((i) => `{"label":"Floor ${i}","layout":{"template_id":"urban_cvs","seed":${i === index ? "9007199254740990.1" : "42"}}}`).join(",")}]}`;
  const file = Object.assign(new File([source], "building.json"), { text: async () => source });
  fireEvent.change(screen.getByLabelText("Import building options file"), { target: { files: [file] } });
  await screen.findByRole("alert");
  expect(api.validateBuildingPreset).not.toHaveBeenCalled(); expect(onChange).not.toHaveBeenCalled();
});

it.each([
  ["9007199254740991", 9007199254740991], ["-9007199254740991", -9007199254740991],
  ["90071992547409910e-1", 9007199254740991], ["-90071992547409910e-1", -9007199254740991],
  ["42.000", 42], ["1.2e2", 120], ["1e3", 1000], ["0e-999999", 0], ["-0.0", -0],
])("keeps exact whole-number JSON representation %s compatible", async (literal, seed) => {
  const onChange = vi.fn();
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "urban_cvs", seed: Number(seed), currency: "USD" } });
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  const requirements = JSON.stringify('A note containing "seed":9007199254740990.1 stays text');
  upload(`{"layout":{"template_id":"urban_cvs","seed":${literal},"requirements":${requirements}}}`);
  await waitFor(() => expect(onChange).toHaveBeenCalledOnce());
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ seed })); expect(screen.queryByRole("alert")).toBeNull();
});

it("checks escaped seed property names", async () => {
  const onChange = vi.fn();
  vi.mocked(api.validateLayoutPreset).mockResolvedValue({ format: "twinstore-layout-options", version: 1, layout: { template_id: "urban_cvs", seed: 0, currency: "USD" } });
  render(<GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />);
  upload('{"layout":{"template_id":"urban_cvs","s\\u0065ed":1e-400}}');
  await screen.findByRole("alert"); expect(api.validateLayoutPreset).not.toHaveBeenCalled(); expect(onChange).not.toHaveBeenCalled();
});
