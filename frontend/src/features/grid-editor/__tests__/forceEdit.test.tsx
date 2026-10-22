// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLocale } from "@/shared/i18n/i18n";
import { FloorConfigurationPanel } from "../FloorConfigurationPanel";
import type { EditorRack, SetupDetailWithBlocked, Store } from "../types";

const save = vi.hoisted(() => vi.fn());
vi.mock("../gridEditorApi", () => ({ saveSetup: save, loadSetup: vi.fn() }));
vi.mock("@/shared/queries/useProject", () => ({ useProject: () => ({ data: { metadata: { name: "Floor" } } }) }));
vi.mock("../RackPreview", () => ({ RackPreview: () => null }));
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn(); });
  save.mockResolvedValue({ ok: true });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); });

const cola = { sku: "cola", name: "Cola", price: 199, promo: "" };
const shelf: EditorRack = { id: "shelf", type: "shelf", shape: [[1]], position: [1, 1], rotation: 0, levels: 4,
  dwell_min: 2, dwell_max: 30, rack_name: "Drinks", rack_desc: "", rack_decoration_desc: "", locked_faces: [],
  slots: [{ block: 0, face: "S", level: 1, items: [cola, cola, cola] }], design_variant: "a" };
const store: Store = { id: "store", name: "Floor", type: "cafe", grid_size: [8, 8], weekly_schedule: [], racks: [shelf] };
const setup: SetupDetailWithBlocked = { id: "s", name: "Floor", status: "draft", parentId: null, runId: null, memo: "",
  readiness: null, created_at: "2026-10-22", updated_at: "2026-10-22", blocked_faces: [], store };
const itemsOf = (s: Store) => s.racks.flatMap((r) => r.slots.flatMap((slot) => slot.items));

function renderPanel(value: SetupDetailWithBlocked, itemCount = 3) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <FloorConfigurationPanel pid="p" sid="s" setup={value} itemCount={itemCount} />
  </QueryClientProvider>);
}

function openEditorPastConfirm() {
  fireEvent.click(screen.getByTestId("floor-config-edit-link"));
  expect(screen.getByTestId("edit-floor-confirm-dialog").textContent).toContain("Nothing changes until you save");
  fireEvent.click(screen.getByRole("button", { name: "Edit floor configuration" }));
  return screen.getByTestId("grid-editor-dialog");
}

function changeWidth(value: string) {
  const width = screen.getByRole("spinbutton", { name: "Width" });
  fireEvent.change(width, { target: { value } });
  fireEvent.blur(width);
}

it("opens the editor without saving anything, and Escape or Cancel leave the products in place", async () => {
  renderPanel(setup);
  const dialog = openEditorPastConfirm();
  expect(screen.getByTestId("grid-editor-description").textContent)
    .toBe("Saving a changed floor removes every product placed on this layout. Cancel to keep them.");
  fireEvent.keyDown(dialog, { key: "Escape" });
  await waitFor(() => expect(screen.queryByTestId("grid-editor-dialog")).toBeNull());

  openEditorPastConfirm();
  fireEvent.click(screen.getByTestId("grid-cancel-button"));
  await waitFor(() => expect(screen.queryByTestId("grid-editor-dialog")).toBeNull());

  fireEvent.click(screen.getByTestId("floor-config-edit-link"));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(screen.queryByTestId("edit-floor-confirm-dialog")).toBeNull());
  expect(save).not.toHaveBeenCalled();
});

it("removes the products only when a changed floor is saved", async () => {
  renderPanel(setup);
  openEditorPastConfirm();
  changeWidth("10");
  fireEvent.click(screen.getByTestId("grid-save-button"));
  await waitFor(() => expect(screen.queryByTestId("grid-editor-dialog")).toBeNull());
  expect(save).toHaveBeenCalledTimes(2);
  const [cleared, changed] = save.mock.calls.map((call) => (call[2] as { store: Store }).store);
  // The backend only accepts a floor change once the products are gone: clear them on the saved floor first.
  expect(cleared!.grid_size).toEqual([8, 8]);
  expect(itemsOf(cleared!)).toEqual([]);
  expect(changed!.grid_size).toEqual([10, 8]);
  expect(itemsOf(changed!)).toEqual([]);
});

it("puts the products back when the changed floor is refused", async () => {
  save.mockResolvedValueOnce({ ok: true }).mockResolvedValueOnce({ ok: false, status: 422, code: "validation_failed",
    reason: "validation_error", details: {}, message: "store layout has errors." });
  renderPanel(setup);
  openEditorPastConfirm();
  changeWidth("10");
  fireEvent.click(screen.getByTestId("grid-save-button"));
  expect((await screen.findByTestId("grid-save-error")).textContent).toBe("store layout has errors.");
  await waitFor(() => expect(save).toHaveBeenCalledTimes(3));
  expect((save.mock.calls[2]![2] as { store: Store }).store).toEqual(store);
  expect(screen.getByTestId("grid-editor-dialog")).toBeTruthy();
});

it("keeps the products when the floor is saved unchanged", async () => {
  renderPanel(setup);
  openEditorPastConfirm();
  fireEvent.click(screen.getByTestId("grid-save-button"));
  await waitFor(() => expect(screen.queryByTestId("grid-editor-dialog")).toBeNull());
  expect(save).not.toHaveBeenCalled();
});

it("edits a floor without products directly", async () => {
  renderPanel({ ...setup, store: { ...store, racks: [{ ...shelf, slots: [] }] } }, 0);
  fireEvent.click(screen.getByTestId("floor-config-edit-link"));
  expect(screen.queryByTestId("edit-floor-confirm-dialog")).toBeNull();
  expect(screen.getByTestId("grid-editor-description").className).toContain("sr-only");
  changeWidth("9");
  fireEvent.click(screen.getByTestId("grid-save-button"));
  await waitFor(() => expect(save).toHaveBeenCalledOnce());
  expect((save.mock.calls[0]![2] as { store: Store }).store.grid_size).toEqual([9, 8]);
});

it("translates the floor step heading, actions and confirmation", () => {
  useLocale.getState().setLocale("ko");
  const { unmount } = renderPanel(setup);
  expect(screen.getByRole("heading").textContent).toBe("1단계: 매장 배치 구성");
  expect(screen.getByTestId("floor-config-edit-link").textContent).toBe("편집");
  fireEvent.click(screen.getByTestId("floor-config-edit-link"));
  expect(screen.getByRole("button", { name: "매장 배치 편집" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "취소" })).toBeTruthy();
  unmount();
  renderPanel({ ...setup, store: null });
  expect(screen.getByTestId("floor-config-build-button").textContent).toBe("빈 배치부터 시작");
});
