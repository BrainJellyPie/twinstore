// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { LayoutOptions, ReservedArea } from "@/shared/api/client";
import { ReservedAreasEditor } from "../components/ReservedAreasEditor";

afterEach(cleanup);

function Editor({ grid, initial = [], entrance = "left", gateWall = "front" }: { grid: [number, number]; initial?: ReservedArea[]; entrance?: LayoutOptions["entrance"]; gateWall?: LayoutOptions["gate_wall"] }) {
  const [areas, setAreas] = useState<ReservedArea[]>(initial);
  return <><ReservedAreasEditor areas={areas} onChange={setAreas} grid={grid} entrance={entrance} gateWall={gateWall} />
    <output data-testid="areas">{JSON.stringify(areas)}</output></>;
}

function savedAreas(): ReservedArea[] {
  return JSON.parse(screen.getByTestId("areas").textContent ?? "[]") as ReservedArea[];
}

it.each(["custom", "consultation", "pickup", "fitting", "demo", "event"])("fits the %s starting point inside small and large floors", (preset) => {
  for (const grid of [[8, 6], [12, 10], [40, 40]] as [number, number][]) {
    const view = render(<Editor grid={grid} entrance="right" />);
    fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: preset } });
    fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
    const area = savedAreas()[0]!;
    expect(area.x).toBeGreaterThanOrEqual(1);
    expect(area.y).toBeGreaterThanOrEqual(1);
    expect(area.x + area.width).toBeLessThanOrEqual(grid[0] - 1);
    expect(area.y + area.height).toBeLessThanOrEqual(grid[1] - 1);
    expect(area.width).toBeGreaterThan(0);
    expect(area.height).toBeGreaterThan(0);
    expect([area.x, area.y, area.width, area.height].every(Number.isInteger)).toBe(true);
    view.unmount();
  }
});

it.each([['left', 2], ['center', 10], ['right', 19]] as const)("starts pickup near the %s entrance", (entrance, x) => {
  render(<Editor grid={[24, 18]} entrance={entrance} />);
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "pickup" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  expect(savedAreas()).toEqual([{ label: "Pickup", x, y: 14, width: 3, height: 2 }]);
});

it.each([
  ["back", "left", 2, 2, 3, 2], ["back", "center", 10, 2, 3, 2], ["back", "right", 19, 2, 3, 2],
  ["left", "left", 2, 2, 2, 3], ["left", "center", 2, 7, 2, 3], ["left", "right", 2, 13, 2, 3],
  ["right", "left", 20, 2, 2, 3], ["right", "center", 20, 7, 2, 3], ["right", "right", 20, 13, 2, 3],
] as const)("places pickup on the %s wall near its %s gate", (gateWall, entrance, x, y, width, height) => {
  render(<Editor grid={[24, 18]} entrance={entrance} gateWall={gateWall} />);
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "pickup" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  expect(savedAreas()).toEqual([{ label: "Pickup", x, y, width, height }]);
});

it("keeps added areas editable, avoids duplicate names and enforces the eight-area limit", () => {
  render(<Editor grid={[24, 18]} />);
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "consultation" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  expect(savedAreas().map((area) => area.label)).toEqual(["Consultation", "Consultation 2"]);
  fireEvent.change(screen.getByLabelText("Area 1 name"), { target: { value: "Private advice" } });
  fireEvent.change(screen.getByLabelText("Area 1 start column"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Area 1 width"), { target: { value: "5" } });
  expect(savedAreas()[0]).toMatchObject({ label: "Private advice", x: 3, width: 5 });
  for (let index = 2; index < 8; index++) fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  expect(new Set(savedAreas().map((area) => area.label)).size).toBe(8);
  expect((screen.getByRole("button", { name: "Add reserved area" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Remove area 2" }));
  expect((screen.getByRole("button", { name: "Add reserved area" }) as HTMLButtonElement).disabled).toBe(false);
  expect(savedAreas()[0]).toMatchObject({ label: "Private advice", x: 3, width: 5 });
});

it("requires valid floor dimensions before adding a starting point", () => {
  render(<Editor grid={[7, 6]} />);
  expect((screen.getByRole("button", { name: "Add reserved area" }) as HTMLButtonElement).disabled).toBe(true);
  expect(savedAreas()).toEqual([]);
});


it("moves and swaps one existing area without changing other areas or submitting", () => {
  const submit = vi.fn();
  const first = { label: "Consultation", x: 2, y: 3, width: 4, height: 3 };
  const second = { label: "Pickup", x: 5, y: 6, width: 2, height: 2 };
  render(<form onSubmit={submit}><Editor grid={[24, 18]} initial={[first, second]} /></form>);
  fireEvent.click(screen.getByRole("button", { name: "Move area 1 to front right" }));
  expect(savedAreas()).toEqual([{ ...first, x: 19, y: 14 }, second]);
  expect((screen.getByRole("button", { name: "Swap area 1 width and depth" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Move area 1 to center" }));
  fireEvent.click(screen.getByRole("button", { name: "Swap area 1 width and depth" }));
  expect(savedAreas()).toEqual([{ ...first, x: 10, y: 7, width: 3, height: 4 }, second]);
  fireEvent.click(screen.getByRole("button", { name: "Swap area 1 width and depth" }));
  expect(savedAreas()[0]).toEqual({ ...first, x: 10, y: 7 });
  expect(submit).not.toHaveBeenCalled();
});

it("uses current grid dimensions, recovers missing coordinates and holds invalid sizes", () => {
  const first = { label: "Consultation", x: 2, y: 2, width: 4, height: 3 };
  const view = render(<Editor grid={[24, 18]} initial={[first]} />);
  view.rerender(<Editor grid={[8, 6]} initial={[first]} />);
  fireEvent.change(screen.getByLabelText("Area 1 start column"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Move area 1 to back right" }));
  expect(savedAreas()[0]).toEqual({ ...first, x: 3, y: 1 });
  expect((screen.getByLabelText("Area 1 start column") as HTMLInputElement).value).toBe("4");
  fireEvent.change(screen.getByLabelText("Area 1 width"), { target: { value: "" } });
  expect((screen.getByRole("button", { name: "Move area 1 to center" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Swap area 1 width and depth" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Area 1 width"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Move area 1 to front left" }));
  expect(savedAreas()[0]).toEqual({ ...first, x: 1, y: 2, width: 3 });
});

it("keeps oversized swaps disabled without silently moving or shrinking a full interior area", () => {
  const first = { label: "Event", x: 1, y: 1, width: 6, height: 4 };
  render(<Editor grid={[8, 6]} initial={[first]} />);
  const swap = screen.getByRole("button", { name: "Swap area 1 width and depth" });
  expect((swap as HTMLButtonElement).disabled).toBe(true); fireEvent.click(swap);
  expect(savedAreas()).toEqual([first]);
});
