// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { GridEditorDialog } from "../GridEditorDialog";
import type { EditorRack, SetupDetailWithBlocked } from "../types";

const save = vi.hoisted(() => vi.fn());
vi.mock("../gridEditorApi", () => ({ saveSetup: save }));
vi.mock("@/shared/queries/useProject", () => ({ useProject: () => ({ data: { metadata: { name: "Unsaved" } } }) }));
vi.mock("../RackPreview", () => ({ RackPreview: () => null }));
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn(); });
  save.mockResolvedValue({ ok: true });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

const shelf: EditorRack = { id: "shelf", type: "shelf", shape: [[1]], position: [1, 1], rotation: 0, levels: 4,
  dwell_min: 2, dwell_max: 30, rack_name: "Snacks", rack_desc: "", rack_decoration_desc: "", locked_faces: [],
  slots: [], design_variant: "a" };
function setup(racks: EditorRack[]): SetupDetailWithBlocked {
  return { id: "s", name: "Unsaved", status: "draft", parentId: null, runId: null, memo: "", readiness: null,
    created_at: "2026-10-22", updated_at: "2026-10-22", blocked_faces: [],
    store: { id: "store", name: "Unsaved", type: "cafe", grid_size: [8, 8], weekly_schedule: [], racks } };
}
function changeWidth(value: string) {
  const width = screen.getByRole("spinbutton", { name: "Width" });
  fireEvent.change(width, { target: { value } });
  fireEvent.blur(width);
}

it("closes at once when nothing changed, including after an edit is undone", () => {
  const onClose = vi.fn();
  render(<GridEditorDialog open pid="p" sid="s" initialSetup={setup([shelf])} onClose={onClose} onSaved={vi.fn()} />);
  changeWidth("9");
  changeWidth("8");
  fireEvent.click(screen.getByTestId("grid-cancel-button"));
  expect(screen.queryByTestId("grid-discard-confirm")).toBeNull();
  expect(onClose).toHaveBeenCalledOnce();
});

it("keeps unsaved edits on Escape and asks before Cancel or the close button discard them", async () => {
  const onClose = vi.fn();
  render(<GridEditorDialog open pid="p" sid="s" initialSetup={setup([shelf])} onClose={onClose} onSaved={vi.fn()} />);
  changeWidth("10");
  fireEvent.keyDown(screen.getByTestId("grid-editor-dialog"), { key: "Escape" });
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.queryByTestId("grid-discard-confirm")).toBeNull();

  fireEvent.click(screen.getByTestId("grid-cancel-button"));
  expect(screen.getByTestId("grid-discard-confirm").textContent).toContain("Discard unsaved changes?");
  fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
  await waitFor(() => expect(screen.queryByTestId("grid-discard-confirm")).toBeNull());
  expect(onClose).not.toHaveBeenCalled();
  expect((screen.getByRole("spinbutton", { name: "Width" }) as HTMLInputElement).value).toBe("10");

  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  fireEvent.click(await screen.findByRole("button", { name: "Discard changes" }));
  expect(onClose).toHaveBeenCalledOnce();
});

it("shows a thrown save error in the dialog and lets the user retry", async () => {
  const onSaved = vi.fn();
  save.mockRejectedValueOnce(new TypeError("Failed to fetch"));
  render(<GridEditorDialog open pid="p" sid="s" initialSetup={setup([shelf])} onClose={vi.fn()} onSaved={onSaved} />);
  fireEvent.click(screen.getByTestId("grid-save-button"));
  expect((await screen.findByTestId("grid-save-error")).textContent).toBe("Failed to fetch");
  const button = screen.getByTestId("grid-save-button") as HTMLButtonElement;
  expect(button.disabled).toBe(false);
  fireEvent.click(button);
  await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
});

it("runs Reset and recreate once while pending and shows a thrown error", async () => {
  const legacy: EditorRack = { ...shelf, id: "wide", shape: [[1, 1]] };
  let reject: (error: Error) => void = () => {};
  save.mockImplementationOnce(() => new Promise((_, fail) => { reject = fail; }));
  render(<GridEditorDialog open pid="p" sid="s" initialSetup={setup([legacy])} onClose={vi.fn()} onSaved={vi.fn()} />);
  const reset = screen.getByTestId("legacy-reset") as HTMLButtonElement;
  fireEvent.click(reset);
  fireEvent.click(reset);
  expect(save).toHaveBeenCalledOnce();
  expect(reset.disabled).toBe(true);
  reject(new Error("Server unavailable"));
  expect((await screen.findByTestId("legacy-detect-error")).textContent).toBe("Server unavailable");
  expect((screen.getByTestId("legacy-reset") as HTMLButtonElement).disabled).toBe(false);
});
