// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DimensionInput } from "../DimensionInput";
import { GridEditor } from "../GridEditor";
import { GridEditorDialog } from "../GridEditorDialog";
import type { EditorRack, SetupDetailWithBlocked } from "../types";

const save = vi.hoisted(() => vi.fn().mockResolvedValue({ ok: true }));
vi.mock("../gridEditorApi", () => ({ saveSetup: save }));
vi.mock("@/shared/queries/useProject", () => ({ useProject: () => ({ data: { metadata: { name: "Large store" } } }) }));
vi.mock("../RackPreview", () => ({ RackPreview: () => null }));
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn(); });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

it("allows clearing and typing 40 without clamping the first digit, then normalizes invalid sizes on blur", () => {
  function Form() {
    const [width, setWidth] = useState(36);
    return <><DimensionInput axis="width" value={width} onChange={setWidth} /><output data-testid="width">{width}</output></>;
  }
  render(<Form />);
  const input = screen.getByRole("spinbutton", { name: "Width" });
  for (const value of ["", "4"]) {
    fireEvent.change(input, { target: { value } });
    expect((input as HTMLInputElement).value).toBe(value);
    expect(screen.getByTestId("width").textContent).toBe("36");
  }
  fireEvent.change(input, { target: { value: "40" } });
  fireEvent.blur(input);
  expect(screen.getByTestId("width").textContent).toBe("40");
  fireEvent.change(input, { target: { value: "80" } });
  fireEvent.blur(input);
  expect((input as HTMLInputElement).value).toBe("40");
  fireEvent.change(input, { target: { value: "" } });
  fireEvent.blur(input);
  expect(screen.getByTestId("width").textContent).toBe("5");
});

it("keeps far cells selectable and selected while zooming a 40 by 40 floor", () => {
  const select = vi.fn();
  render(<GridEditor racks={[]} gridSize={[40, 40]} blockedFaces={[]} selectedCell={[39, 39]} onCellClick={select} />);
  const farCell = screen.getByTestId("grid-cell-39-39");
  fireEvent.click(farCell);
  expect(select).toHaveBeenCalledWith([39, 39]);
  expect(farCell.getAttribute("aria-pressed")).toBe("true");
  const zoomOut = screen.getByLabelText("Zoom out grid") as HTMLButtonElement;
  for (let i = 0; i < 3; i++) fireEvent.click(zoomOut);
  expect(zoomOut.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText("Zoom in grid"));
  expect(farCell.getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText("Selected cell: column 40, row 40")).toBeTruthy();
});

it("prevents shrinking through a dining footprint and saves every fixture once the dimensions fit", async () => {
  const table: EditorRack = { id: "edge", type: "table", shape: [[1, 1], [1, 1]], position: [38, 38], rotation: 0,
    levels: 4, dwell_min: 2, dwell_max: 30, rack_name: "Corner dining", rack_desc: "",
    rack_decoration_desc: "", locked_faces: [], slots: [], design_variant: "a" };
  const setup: SetupDetailWithBlocked = { id: "s", name: "Large store", runId: null, blocked_faces: [],
    status: "draft", parentId: null, memo: "", readiness: null, created_at: "2026-10-21", updated_at: "2026-10-21",
    store: { id: "store", name: "Large store", type: "hypermarket", weekly_schedule: [], grid_size: [40, 40], racks: [table] } };
  const onSaved = vi.fn();
  render(<GridEditorDialog open pid="p" sid="s" initialSetup={setup} onClose={vi.fn()} onSaved={onSaved} />);
  const width = screen.getByRole("spinbutton", { name: "Width" });
  fireEvent.change(width, { target: { value: "39" } });
  fireEvent.blur(width);
  fireEvent.click(screen.getByTestId("grid-save-button"));
  expect(screen.getByRole("alert").textContent).toContain("Corner dining");
  expect(save).not.toHaveBeenCalled();
  fireEvent.change(width, { target: { value: "40" } });
  fireEvent.blur(width);
  expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.click(screen.getByTestId("grid-save-button"));
  await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
  expect(save).toHaveBeenCalledWith("p", "s", { store: { ...setup.store, grid_size: [40, 40], racks: [table] } });
});

it("opens a floor small enough to fit with every row in view, and a deep one at the smallest step", () => {
  window.innerHeight = 900;
  const { unmount } = render(<GridEditor racks={[]} gridSize={[8, 8]} blockedFaces={[]} selectedCell={null} onCellClick={vi.fn()} />);
  // 8 rows of 56 px and their gaps fit 55 % of 900 px; at 64 px the last row was cut off.
  expect(screen.getByTestId("grid-canvas").style.gridAutoRows).toBe("56px");
  expect(screen.getByLabelText("Grid zoom").textContent).toBe("88%");
  unmount();
  render(<GridEditor racks={[]} gridSize={[40, 40]} blockedFaces={[]} selectedCell={null} onCellClick={vi.fn()} />);
  expect(screen.getByTestId("grid-canvas").style.gridAutoRows).toBe("40px");
});
