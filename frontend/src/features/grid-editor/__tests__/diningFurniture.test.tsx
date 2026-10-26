// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { EditorRack, SetupDetailWithBlocked } from "../types";
import { GridEditor } from "../GridEditor";
import { RackEditPanel } from "../RackEditPanel";
import { checkLegacy } from "../LegacyDetectModal";
import { computeAdjacentBlocked } from "../adjacentBlocked";
import { rackCells } from "@/shared/utils/grid";
import { diningTableParts } from "@/features/store-viewer/realistic/diningTable";

vi.mock("../RackPreview", () => ({ RackPreview: () => null }));
afterEach(cleanup);

const table: EditorRack = {
  id: "table1", type: "table", shape: [[1, 1], [1, 1]], position: [2, 2], rotation: 0,
  levels: 4, dwell_min: 2, dwell_max: 30, rack_name: "Window table", rack_desc: "",
  rack_decoration_desc: "", locked_faces: [], slots: [], design_variant: "a",
};

it("shows the complete furniture footprint and lets every cell select it", () => {
  const onCellClick = vi.fn();
  render(<GridEditor racks={[table]} gridSize={[8, 6]} blockedFaces={[]} onCellClick={onCellClick} />);
  const cells = screen.getAllByRole("button", { name: /table Window table/ });
  expect(cells).toHaveLength(4);
  fireEvent.click(screen.getByRole("button", { name: "table Window table, column 4, row 4" }));
  expect(onCellClick).toHaveBeenCalledWith([3, 3]);
});

it("edits dining furniture without treating it as a shelf or requiring a legacy reset", () => {
  const setup = { store: { racks: [table] }, runId: null } as SetupDetailWithBlocked;
  expect(checkLegacy(setup)).toBe("ok");
  expect(checkLegacy({ ...setup, store: { ...setup.store!, racks: [{ ...table, type: "shelf" }] } })).toBe("clean");
  const onChange = vi.fn();
  render(<RackEditPanel selectedCell={[3, 3]} selectedCellRacks={[table]} selectedRack={table}
    onChange={onChange} onGateConfigChange={vi.fn()} />);
  expect(screen.getByRole("radio", { name: "Dining table" }).getAttribute("aria-checked")).toBe("true");
  fireEvent.change(screen.getByLabelText("Table name"), { target: { value: "Garden table" } });
  fireEvent.blur(screen.getByLabelText("Table name"));
  expect(onChange).toHaveBeenLastCalledWith({ rack_name: "Garden table" });
  fireEvent.click(screen.getByRole("radio", { name: /^Rack$/ }));
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ type: "shelf", shape: [[1]] }));
});

it("counts furniture as an obstacle without offering it product faces", () => {
  const shelf: EditorRack = { ...table, id: "shelf", type: "shelf", shape: [[1]], position: [1, 3] };
  const blocked = computeAdjacentBlocked([shelf, table], [8, 6]);
  expect(blocked).toContainEqual({ rack_id: "shelf", block: 0, face: "E", reasons: ["occluded"] });
  expect(blocked.some((b) => b.rack_id === table.id)).toBe(false);
  expect(rackCells({ ...table, shape: [[1, 1]], rotation: 90 })).toEqual([[2, 2], [2, 3]]);
});

it.each([[2, 0, "1×2"], [2, 90, "2×1"], [6, 0, "3×2"], [6, 90, "2×3"]] as const)(
  "describes the actual floor footprint of %s seats rotated %s degrees", (seats, rotation, footprint) => {
    const rotated = { ...table, rotation, shape: Array.from({ length: 2 }, () => Array<number>(seats / 2).fill(1)) };
    render(<RackEditPanel selectedCell={[2, 2]} selectedCellRacks={[rotated]} selectedRack={rotated}
      onChange={vi.fn()} onGateConfigChange={vi.fn()} />);
    expect(screen.getByText(`${footprint} cells, including ${seats} chairs. Furniture only; table service is not simulated.`)).toBeTruthy();
  });

it("keeps table and chairs inside their blocked floor area in both renderers", () => {
  for (const [w, d] of [[2, 2], [1, 1], [1.94, 2]]) {
    const parts = diningTableParts(w!, d!);
    expect(parts.length).toBe(w! >= 1.8 ? 29 : 5);
    for (const p of parts) {
      expect(Math.abs(p.position[0]) + p.size[0] / 2).toBeLessThanOrEqual(w! / 2);
      expect(Math.abs(p.position[2]) + p.size[2] / 2).toBeLessThanOrEqual(d! / 2);
      expect(p.position[1] - p.size[1] / 2).toBeGreaterThanOrEqual(0);
    }
  }
});
