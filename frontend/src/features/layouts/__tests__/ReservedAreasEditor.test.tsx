// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { LayoutOptions, ReservedArea } from "@/shared/api/client";
import { ReservedAreasEditor } from "../components/ReservedAreasEditor";

afterEach(cleanup);

function Editor({ grid, entrance = "left" }: { grid: [number, number]; entrance?: LayoutOptions["entrance"] }) {
  const [areas, setAreas] = useState<ReservedArea[]>([]);
  return <><ReservedAreasEditor areas={areas} onChange={setAreas} grid={grid} entrance={entrance} />
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
