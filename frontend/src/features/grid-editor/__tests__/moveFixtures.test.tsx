// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { GridEditorDialog } from "../GridEditorDialog";
import { useGridEditor } from "../useGridEditor";
import type { EditorRack, SetupDetailWithBlocked } from "../types";

const save = vi.hoisted(() => vi.fn().mockResolvedValue({ ok: true }));
vi.mock("../gridEditorApi", () => ({ saveSetup: save }));
vi.mock("@/shared/queries/useProject", () => ({ useProject: () => ({ data: { metadata: { name: "Movement" } } }) }));
vi.mock("../RackPreview", () => ({ RackPreview: () => null }));
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn(); });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

const table: EditorRack = { id: "table", type: "table", shape: [[1, 1], [1, 1]], position: [2, 2], rotation: 0,
  levels: 4, dwell_min: 2, dwell_max: 30, rack_name: "Reading table", rack_desc: "Four seats",
  rack_decoration_desc: "", locked_faces: [], slots: [], design_variant: "a" };
const shelf: EditorRack = { ...table, id: "shelf", type: "shelf", shape: [[1]], position: [4, 3], rack_name: "Books" };
function setup(racks: EditorRack[]): SetupDetailWithBlocked {
  return { id: "s", name: "Movement", status: "draft", parentId: null, runId: null, memo: "", readiness: null,
    created_at: "2026-10-21", updated_at: "2026-10-21", blocked_faces: [],
    store: { id: "store", name: "Movement", type: "cafe", grid_size: [8, 8], weekly_schedule: [], racks } };
}

it("rejects collisions on any footprint cell and keeps pending name edits when moving into clear space", () => {
  const { result } = renderHook(() => useGridEditor(setup([table, shelf])));
  act(() => expect(result.current.moveRacks([table.id], [1, 0])).toContain("overlaps"));
  expect(result.current.racks).toEqual([table, shelf]);
  act(() => {
    result.current.updateRack(table.id, { rack_name: "Window table" });
    expect(result.current.moveRacks([table.id], [-1, 0])).toBeNull();
  });
  expect(result.current.racks).toEqual([{ ...table, rack_name: "Window table", position: [1, 2] }, shelf]);
});

it("checks the rotated footprint at the floor boundary", () => {
  const rotated: EditorRack = { ...table, shape: [[1, 1, 1]], rotation: 90, position: [6, 5] };
  const { result } = renderHook(() => useGridEditor(setup([rotated])));
  act(() => expect(result.current.moveRacks([table.id], [0, 1])).toContain("inside the floor"));
  expect(result.current.racks).toEqual([rotated]);
  act(() => expect(result.current.moveRacks([table.id], [0, -1])).toBeNull());
  expect(result.current.racks[0]).toEqual({ ...rotated, position: [6, 4] });
});

it("moves a paired entrance and exit together or leaves both unchanged when blocked", () => {
  const entrance: EditorRack = { ...table, id: "entrance", type: "entrance", shape: [[1]], position: [0, 7] };
  const exit: EditorRack = { ...entrance, id: "exit", type: "exit" };
  const counter: EditorRack = { ...shelf, id: "counter", type: "counter", position: [2, 7] };
  const { result } = renderHook(() => useGridEditor(setup([entrance, exit, counter])));
  act(() => expect(result.current.moveRacks([entrance.id, exit.id], [1, 0])).toBeNull());
  expect(result.current.racks.slice(0, 2).map((rack) => rack.position)).toEqual([[1, 7], [1, 7]]);
  const before = result.current.racks;
  act(() => expect(result.current.moveRacks([entrance.id, exit.id], [1, 0])).toContain("overlaps"));
  expect(result.current.racks).toBe(before);
});

it("keeps selection on a moved dining group and saves its name and new position", async () => {
  const initialSetup = setup([table, shelf]);
  const onSaved = vi.fn();
  render(<GridEditorDialog open pid="p" sid="s" initialSetup={initialSetup} onClose={vi.fn()} onSaved={onSaved} />);
  fireEvent.click(screen.getByTestId("grid-cell-3-3"));
  fireEvent.change(screen.getByLabelText("Table name"), { target: { value: "Window table" } });
  fireEvent.click(screen.getByRole("button", { name: "Move fixture right" }));
  expect(screen.getByRole("alert").textContent).toContain("overlaps");
  fireEvent.click(screen.getByRole("button", { name: "Move fixture left" }));
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByTestId("grid-cell-2-3").getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByTestId("grid-save-button"));
  await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
  expect(save).toHaveBeenCalledWith("p", "s", { store: { ...initialSetup.store,
    racks: [{ ...table, rack_name: "Window table", position: [1, 2] }, shelf],
  } });
});
