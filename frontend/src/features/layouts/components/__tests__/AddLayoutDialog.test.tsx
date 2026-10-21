// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AddLayoutDialog } from "../AddLayoutDialog";
import type { Layout } from "../../hooks/useLayouts";
import type { BuildingFloorChoice, TemplateChoice } from "../../templateOptions";
import * as api from "@/shared/api/client";
import { LOCALES } from "@/shared/i18n/messages";
import { translate, useLocale } from "@/shared/i18n/i18n";

const mutation = vi.hoisted(() => ({ isPending: false, isError: false, error: null as Error | null, reset: vi.fn(), mutate: vi.fn() }));
vi.mock("../../hooks/useCreateLayout", () => ({ useCreateLayout: () => mutation }));
vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(), previewFloorPlan: vi.fn() }));
vi.mock("../TemplatePicker", () => ({ TemplatePicker: ({ value }: { value: TemplateChoice }) => <div><output data-testid="template-settings">{JSON.stringify(value)}</output><textarea aria-label="Design brief test" /></div> }));
vi.mock("../BuildingPicker", () => ({ BuildingPicker: ({ floors, onChange }: { floors: BuildingFloorChoice[]; onChange: (floors: BuildingFloorChoice[]) => void }) => <div>
  <output data-testid="building-settings">{JSON.stringify(floors)}</output><button type="button" onClick={() => onChange(floors.map((floor, index) => index === 0 ? { ...floor, choice: { ...floor.choice, sourceSetupId: "raw-child" } } : floor))}>Link first floor</button>
</div> }));
const clients: QueryClient[] = [];
const source: Layout = { id: "raw-child", name: "Source Café", parentId: "raw-root", status: "draft", createdAt: "2026-10-21", generation: { template_id: "book_cafe", seed: 5, currency: "JPY", requirements: "Keep the quiet corner", width: 20 } };
const other: Layout = { id: "raw-root", name: "Other floor", parentId: null, status: "draft", createdAt: "2026-10-20" };
beforeEach(() => {
  useLocale.getState().setLocale("en"); Element.prototype.scrollIntoView = vi.fn();
  mutation.isPending = false; mutation.isError = false; mutation.error = null;
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.previewFloorPlan).mockResolvedValue({ page_number: 1, page_count: 2, rotation: 0, width: 100, height: 50, image: "data:image/png;base64,cHJldmlldw==" });
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); clients.splice(0).forEach(client => client.clear()); vi.clearAllMocks(); vi.unstubAllGlobals(); });
function show(patch = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const props = { open: true, onOpenChange: vi.fn(), projectId: "raw-project", parentSetupId: source.id, layouts: [source, other], ...patch };
  return { ...render(<AddLayoutDialog {...props} />, { wrapper }), props };
}

it("offers a keyboard-focusable button to choose a floor-plan file", () => {
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  const choose = screen.getByRole("button", { name: "Choose a plan image" }); const input = screen.getByLabelText("Choose floor plan file");
  const click = vi.spyOn(input, "click").mockImplementation(() => {}); choose.focus(); fireEvent.click(choose);
  expect(document.activeElement).toBe(choose); expect(click).toHaveBeenCalledOnce();
});
it("blocks a removed import source without discarding the user's layout name or silently choosing another source", () => {
  const { props, rerender } = show(); fireEvent.change(screen.getByLabelText("Layout name"), { target: { value: "My alternative" } });
  rerender(<AddLayoutDialog {...props} layouts={[other]} />);
  expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText("Layout name") as HTMLInputElement).value).toBe("My alternative");
  fireEvent.submit(screen.getByTestId("add-layout-submit").closest("form")!); expect(mutation.mutate).not.toHaveBeenCalled();
});
it("defaults to an owned source when the initial parent ID belongs to another project", () => {
  show({ parentSetupId: "foreign-layout" }); fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ projectId: "raw-project", source: { kind: "import", parentSetupId: source.id } }), expect.any(Object));
});
it("does not submit template options with a deleted source link", () => {
  const { props, rerender } = show(); fireEvent.click(screen.getByLabelText("Generate a store from a template"));
  fireEvent.click(screen.getByRole("button", { name: "Reuse options from Source Café" }));
  rerender(<AddLayoutDialog {...props} layouts={[other]} parentSetupId={other.id} />);
  expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(true);
  expect(JSON.parse(screen.getByTestId("template-settings").textContent!)).toMatchObject({ sourceSetupId: source.id, requirements: "Keep the quiet corner", width: 20 });
  expect(mutation.mutate).not.toHaveBeenCalled();
});
it("preserves the selected file when switching approaches, and clears it explicitly with focus recovery", async () => {
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  const file = new File(["%PDF-"], "우리商店.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [file] } }); await screen.findByAltText("Floor plan page 1, rotated 0 degrees clockwise");
  fireEvent.click(screen.getByLabelText("Build from scratch")); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  expect(screen.getByText(file.name)).toBeTruthy(); fireEvent.click(screen.getByRole("button", { name: "Remove selected file" }));
  expect(screen.queryByText(file.name)).toBeNull(); expect(document.activeElement).toBe(screen.getByRole("button", { name: "Choose a plan image" }));
  await waitFor(() => expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(true));
});
it("ignores a late preview after the selected file has been removed", async () => {
  let resolve!: (value: api.FloorPlanPreview) => void;
  vi.mocked(api.previewFloorPlan).mockReturnValue(new Promise(done => { resolve = done; }));
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [new File(["%PDF-"], "plan.pdf")] } });
  fireEvent.click(screen.getByRole("button", { name: "Remove selected file" }));
  await act(async () => resolve({ page_number: 1, page_count: 1, rotation: 0, width: 1, height: 1, image: "data:image/png;base64,cHJldmlldw==" }));
  expect(screen.queryByRole("img")).toBeNull(); expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(true);
});

it.each(LOCALES)("localizes creation and submits owned source IDs and the typed name unchanged in $code", ({ code }) => {
  useLocale.getState().setLocale(code); show(); expect(screen.getByRole("dialog", { name: translate(code, "addLayoutTitle") })).toBeTruthy();
  fireEvent.change(screen.getByLabelText(translate(code, "layoutNameLabel")), { target: { value: "우리商店 Café alternative" } });
  fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ name: "우리商店 Café alternative", source: { kind: "import", parentSetupId: source.id } }), expect.any(Object));
});
it.each(LOCALES)("previews a file, selects offline reading and sends raw reader values in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); show(); fireEvent.click(screen.getByLabelText(translate(code, "layoutFromFloorPlan")));
  const file = new File(["%PDF-"], "우리商店.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText(translate(code, "chooseFloorPlanFile")), { target: { files: [file] } });
  await screen.findByAltText(translate(code, "floorPlanPreviewAlt", { page: 1, rotation: 0 }));
  const offline = screen.getByRole("button", { name: translate(code, "geometryPlanReader") }); fireEvent.click(offline); expect(offline.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ source: { kind: "plan", file, reader: "classic", pageNumber: 1, rotation: 0 } }), expect.any(Object));
});
it.each(LOCALES)("unlinks a missing saved source while preserving reusable options in $code", ({ code }) => {
  useLocale.getState().setLocale(code); const { props, rerender } = show();
  fireEvent.click(screen.getByLabelText(translate(code, "generateLayoutFromTemplate")));
  fireEvent.click(screen.getByRole("button", { name: translate(code, "reuseLayoutOptions", { name: source.name }) }));
  rerender(<AddLayoutDialog {...props} layouts={[other]} parentSetupId={other.id} />);
  expect(screen.getByRole("alert").textContent).toContain(translate(code, "savedSourceUnavailable"));
  fireEvent.click(screen.getByRole("button", { name: translate(code, "unlinkSavedSources") }));
  const options = JSON.parse(screen.getByTestId("template-settings").textContent!);
  expect(options).toMatchObject({ templateId: "book_cafe", width: 20, currency: "JPY", requirements: "Keep the quiet corner", seed: 5 }); expect(options).not.toHaveProperty("sourceSetupId");
  fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ source: expect.objectContaining({ kind: "template", sourceSetupId: undefined, width: 20 }) }), expect.any(Object));
});
it("keeps an already selected file when the native chooser is canceled", async () => {
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  const input = screen.getByLabelText("Choose floor plan file"), file = new File(["%PDF-"], "saved.pdf");
  fireEvent.change(input, { target: { files: [file] } }); await screen.findByRole("img");
  fireEvent.change(input, { target: { files: [] } }); expect(screen.getByText(file.name)).toBeTruthy();
  expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(false);
});
it("blocks invalid page values without requesting previews and recovers after correction", async () => {
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [new File(["%PDF-"], "plan.pdf")] } }); await screen.findByRole("img");
  const calls = vi.mocked(api.previewFloorPlan).mock.calls.length;
  for (const value of ["0", "-1", "1.5", ""]) { fireEvent.change(screen.getByLabelText("Floor plan page"), { target: { value } }); expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(true); }
  expect(api.previewFloorPlan).toHaveBeenCalledTimes(calls); fireEvent.change(screen.getByLabelText("Floor plan page"), { target: { value: "1" } });
  await waitFor(() => expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(false));
});
it("changes display language without overwriting the name, file or selected approach", async () => {
  show(); fireEvent.change(screen.getByLabelText("Layout name"), { target: { value: "Keep my name" } }); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  const file = new File(["%PDF-"], "keep.pdf"); fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [file] } }); await screen.findByRole("img");
  act(() => useLocale.getState().setLocale("ja")); expect((screen.getByLabelText(translate("ja", "layoutNameLabel")) as HTMLInputElement).value).toBe("Keep my name");
  expect(screen.getByText(file.name)).toBeTruthy(); expect((screen.getByLabelText(translate("ja", "layoutFromFloorPlan")) as HTMLInputElement).checked).toBe(true);
});
it("locks creation inputs, the file chooser, removal and reader controls while creation is pending", async () => {
  const { props, rerender } = show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [new File(["%PDF-"], "plan.pdf")] } }); await screen.findByRole("img");
  mutation.isPending = true; rerender(<AddLayoutDialog {...props} />);
  for (const name of ["Choose a plan image", "Remove selected file", "Vision model, geometry fallback", "Geometry only (offline)"]) expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText("Layout name") as HTMLInputElement).matches(":disabled")).toBe(true);
  expect((screen.getByLabelText("Floor plan page") as HTMLInputElement).matches(":disabled")).toBe(true);
});

it("allows an explicit replacement for a removed import source and keeps the typed name", () => {
  const { props, rerender } = show(); fireEvent.change(screen.getByLabelText("Layout name"), { target: { value: "Keep this name" } });
  rerender(<AddLayoutDialog {...props} layouts={[other]} />);
  fireEvent.keyDown(screen.getByRole("combobox", { name: "Source layout" }), { key: "ArrowDown" });
  fireEvent.click(screen.getByRole("option", { name: other.name })); fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ name: "Keep this name", source: { kind: "import", parentSetupId: other.id } }), expect.any(Object));
});
it("reloads a failed preview without choosing the file again or starting creation", async () => {
  vi.mocked(api.previewFloorPlan).mockRejectedValueOnce(new Error("Preview temporarily unavailable"));
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF")); const file = new File(["%PDF-"], "plan.pdf");
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [file] } }); await screen.findByText(/Preview temporarily unavailable/);
  fireEvent.click(screen.getByRole("button", { name: "Try again" })); await screen.findByRole("img");
  expect(api.previewFloorPlan).toHaveBeenCalledTimes(2); expect(api.previewFloorPlan).toHaveBeenLastCalledWith("raw-project", file, expect.objectContaining({ pageNumber: 1, rotation: 0 })); expect(mutation.mutate).not.toHaveBeenCalled();
  expect(screen.getByText(file.name)).toBeTruthy(); expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(false);
});
it("ignores an old file preview after replacement and submits only the replacement file", async () => {
  let resolve!: (value: api.FloorPlanPreview) => void; vi.mocked(api.previewFloorPlan).mockReturnValueOnce(new Promise(done => { resolve = done; }));
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF")); const input = screen.getByLabelText("Choose floor plan file");
  fireEvent.change(input, { target: { files: [new File(["old"], "old.pdf")] } }); const replacement = new File(["new"], "new.pdf");
  fireEvent.change(input, { target: { files: [replacement] } }); await screen.findByRole("img");
  await act(async () => resolve({ page_number: 99, page_count: 99, rotation: 270, width: 1, height: 1, image: "data:image/png;base64,b2xk" }));
  expect(screen.getByRole("img").getAttribute("alt")).toBe("Floor plan page 1, rotated 0 degrees clockwise"); expect(screen.queryByText("old.pdf")).toBeNull();
  fireEvent.click(screen.getByTestId("add-layout-submit")); expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ source: expect.objectContaining({ file: replacement, pageNumber: 1, rotation: 0 }) }), expect.any(Object));
});

it("blocks a missing building-floor source and unlinks it without changing the floor choices", () => {
  const { props, rerender } = show(); fireEvent.click(screen.getByLabelText("Multi-floor store")); fireEvent.click(screen.getByRole("button", { name: "Link first floor" }));
  const before = JSON.parse(screen.getByTestId("building-settings").textContent!);
  rerender(<AddLayoutDialog {...props} layouts={[other]} parentSetupId={other.id} />); expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Remove source links" })); const after = JSON.parse(screen.getByTestId("building-settings").textContent!);
  expect(after[0].label).toBe(before[0].label); expect(after[0].choice.templateId).toBe(before[0].choice.templateId); expect(after[0].choice).not.toHaveProperty("sourceSetupId"); expect(after.slice(1)).toEqual(before.slice(1));
  fireEvent.click(screen.getByTestId("add-layout-submit")); expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ source: expect.objectContaining({ kind: "building" }) }), expect.any(Object));
});
it("rejects a whitespace-only name and preserves the selected source when corrected", () => {
  show(); fireEvent.change(screen.getByLabelText("Layout name"), { target: { value: "  \n  " } }); expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Layout name"), { target: { value: "  우리商店  " } }); fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ name: "우리商店", source: { kind: "import", parentSetupId: source.id } }), expect.any(Object));
});
it("restores localized defaults and clears the file when reopened", async () => {
  const { props, rerender } = show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [new File(["plan"], "old.pdf")] } }); await screen.findByRole("img");
  rerender(<AddLayoutDialog {...props} open={false} />); act(() => useLocale.getState().setLocale("fr")); rerender(<AddLayoutDialog {...props} open />);
  expect((screen.getByLabelText(translate("fr", "layoutNameLabel")) as HTMLInputElement).value).toBe(translate("fr", "layoutDefaultName", { number: 3 }));
  expect(screen.queryByRole("img")).toBeNull(); expect(screen.queryByText("old.pdf")).toBeNull();
});
it("ignores a late preview after the creation dialog unmounts", async () => {
  let resolve!: (value: api.FloorPlanPreview) => void; vi.mocked(api.previewFloorPlan).mockReturnValue(new Promise(done => { resolve = done; }));
  const { unmount } = show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [new File(["plan"], "late.pdf")] } }); unmount();
  await act(async () => resolve({ page_number: 1, page_count: 1, rotation: 0, width: 1, height: 1, image: "data:image/png;base64,cHJldmlldw==" })); expect(mutation.mutate).not.toHaveBeenCalled();
});

it("allows native Enter activation for the file chooser and line breaks in a design brief", () => {
  show(); fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
  expect(fireEvent.keyDown(screen.getByRole("button", { name: "Choose a plan image" }), { key: "Enter" })).toBe(true);
  fireEvent.click(screen.getByLabelText("Generate a store from a template"));
  expect(fireEvent.keyDown(screen.getByLabelText("Design brief test"), { key: "Enter" })).toBe(true); expect(mutation.mutate).not.toHaveBeenCalled();
});
it("does not create a layout when Enter is used on an approach radio or page field", async () => {
  show(); const plan = screen.getByLabelText("From a floor plan — sketch, CAD export or PDF");
  expect(fireEvent.keyDown(plan, { key: "Enter" })).toBe(false); fireEvent.click(plan);
  fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [new File(["plan"], "page.pdf")] } }); await screen.findByRole("img");
  expect(fireEvent.keyDown(screen.getByLabelText("Floor plan page"), { key: "Enter" })).toBe(false); expect(mutation.mutate).not.toHaveBeenCalled();
});

it("returns focus to the opener after canceling the controlled dialog", async () => {
  const opener = document.createElement("button"); opener.textContent = "Open layout creation"; document.body.append(opener); opener.focus();
  try {
    const { props, rerender } = show(); await screen.findByRole("dialog", { name: "Add layout" });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" })); rerender(<AddLayoutDialog {...props} open={false} />);
    await waitFor(() => expect(document.activeElement).toBe(opener));
  } finally { opener.remove(); }
});

it.each(LOCALES)("explains creation failures in the selected language and retains the server detail in $code", ({ code }) => {
  useLocale.getState().setLocale(code); mutation.isError = true; mutation.error = new Error("Store could not be copied"); show();
  const alert = screen.getByRole("alert"); expect(alert.textContent).toContain(translate(code, "createLayoutFailed")); expect(alert.textContent).toContain("Store could not be copied");
});

it.each(LOCALES)("starts an empty project with a blank layout in $code", ({ code }) => {
  useLocale.getState().setLocale(code); show({ parentSetupId: "foreign-layout", layouts: [] });
  expect((screen.getByLabelText(translate(code, "buildLayoutFromScratch")) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByTestId("add-layout-submit") as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ projectId: "raw-project", source: { kind: "empty" } }), expect.any(Object));
});
