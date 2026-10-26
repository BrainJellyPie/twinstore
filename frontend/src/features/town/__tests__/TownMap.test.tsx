// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Town } from "@/shared/api/client";
import { TownMap } from "../TownMap";

const town: Town = { id: "town", name: "Test town", archetype: "residential", size_m: 800, buildings: [], venues: [], roads: [],
  source: "procedural", center_lat: null, center_lon: null, focal_venue_id: "store" };
beforeEach(() => { vi.stubGlobal("PointerEvent", MouseEvent); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const shapes = [
  { name: "wide", width: 400, height: 200, x: 170, y: 80 },
  { name: "tall", width: 200, height: 400, x: 70, y: 180 },
  { name: "square", width: 200, height: 200, x: 70, y: 80 },
];
function mount(width: number, height: number) {
  const place = vi.fn();
  render(<TownMap town={town} mode="place" onPlace={place} onRemove={vi.fn()} />);
  const svg = screen.getByRole("img", { name: "Map of Test town" });
  Object.defineProperty(svg, "getBoundingClientRect", { value: () => ({ left: 20, top: 30, width, height }) });
  Object.defineProperty(svg, "getScreenCTM", { value: () => {
    const [x, y, size] = svg.getAttribute("viewBox")!.split(" ").map(Number);
    const scale = Math.min(width, height) / size!;
    const e = 20 + (width - Math.min(width, height)) / 2 - x! * scale;
    const f = 30 + (height - Math.min(width, height)) / 2 - y! * scale;
    return { inverse: () => ({ a: 1 / scale, b: 0, c: 0, d: 1 / scale, e: -e / scale, f: -f / scale }) };
  } });
  Object.defineProperty(svg, "createSVGPoint", { value: () => ({ x: 0, y: 0,
    matrixTransform(matrix: { a: number; b: number; c: number; d: number; e: number; f: number }) {
      return { x: this.x * matrix.a + this.y * matrix.c + matrix.e, y: this.x * matrix.b + this.y * matrix.d + matrix.f };
    },
  }) });
  return { svg, place };
}

it.each(shapes)("places a venue at the visible map position in a $name viewport", ({ width, height, x, y }) => {
  const { svg, place } = mount(width, height);
  fireEvent.pointerDown(svg, { clientX: x, clientY: y });
  fireEvent.pointerUp(svg, { clientX: x, clientY: y });
  expect(place).toHaveBeenCalledWith(200, 600);
});

it.each(shapes)("keeps the point beneath the cursor fixed while zooming in a $name viewport", ({ width, height, x, y }) => {
  const { svg, place } = mount(width, height);
  fireEvent.wheel(svg, { clientX: x, clientY: y, deltaY: -100 });
  const view = svg.getAttribute("viewBox")!.split(" ").map(Number);
  expect(view[0]).toBeCloseTo(200 - 200 / 1.15);
  expect(view[1]).toBeCloseTo(200 - 200 / 1.15);
  expect(view[2]).toBeCloseTo(800 / 1.15);
  fireEvent.pointerDown(svg, { clientX: x, clientY: y });
  fireEvent.pointerUp(svg, { clientX: x, clientY: y });
  expect(place).toHaveBeenCalledWith(200, 600);
});

it.each(shapes)("pans by the visible distance without placing a venue in a $name viewport", ({ width, height, x, y }) => {
  const { svg, place } = mount(width, height);
  fireEvent.pointerDown(svg, { clientX: x, clientY: y });
  fireEvent.pointerMove(svg, { clientX: x + 50, clientY: y + 25 });
  fireEvent.pointerUp(svg, { clientX: x + 50, clientY: y + 25 });
  const view = svg.getAttribute("viewBox")!.split(" ").map(Number);
  expect(view[0]).toBeCloseTo(-200);
  expect(view[1]).toBeCloseTo(-100);
  expect(place).not.toHaveBeenCalled();
});

it.each(shapes)("keeps repeated drag updates anchored to their starting point in a $name viewport", ({ width, height, x, y }) => {
  const { svg, place } = mount(width, height);
  fireEvent.pointerDown(svg, { clientX: x, clientY: y });
  fireEvent.pointerMove(svg, { clientX: x + 50, clientY: y + 25 });
  fireEvent.pointerMove(svg, { clientX: x + 100, clientY: y + 50 });
  fireEvent.pointerUp(svg, { clientX: x + 100, clientY: y + 50 });
  const view = svg.getAttribute("viewBox")!.split(" ").map(Number);
  expect(view[0]).toBeCloseTo(-400);
  expect(view[1]).toBeCloseTo(-200);
  expect(place).not.toHaveBeenCalled();
});

it.each(shapes)("preserves the cursor's world point at both zoom limits in a $name viewport", ({ width, height, x, y }) => {
  const { svg, place } = mount(width, height);
  for (const [deltaY, limit] of [[-100, 800 / 12], [100, 960]]) {
    for (let i = 0; i < 50; i++) fireEvent.wheel(svg, { clientX: x, clientY: y, deltaY });
    expect(Number(svg.getAttribute("viewBox")!.split(" ")[2])).toBeCloseTo(limit!);
    fireEvent.pointerDown(svg, { clientX: x, clientY: y });
    fireEvent.pointerUp(svg, { clientX: x, clientY: y });
    expect(place).toHaveBeenLastCalledWith(200, 600);
  }
});

it.each(shapes.flatMap((shape) => [-100, 100].map((deltaY) => ({ ...shape, deltaY }))))("consumes vertical wheel input without scrolling the page in a $name viewport ($deltaY)", ({ width, height, x, y, deltaY }) => {
  const { svg } = mount(width, height);
  const event = new WheelEvent("wheel", { bubbles: true, cancelable: true, clientX: x, clientY: y, deltaY });
  fireEvent(svg, event);
  expect(event.defaultPrevented).toBe(true);
  expect(Number(svg.getAttribute("viewBox")!.split(" ")[2])).not.toBe(800);
});

it.each(shapes)("does not zoom for a horizontal wheel gesture in a $name viewport", ({ width, height, x, y }) => {
  const { svg } = mount(width, height);
  fireEvent.wheel(svg, { clientX: x, clientY: y, deltaX: 100, deltaY: 0 });
  expect(svg.getAttribute("viewBox")).toBe("0 0 800 800");
});

it("stops intercepting wheel input after the map is unmounted", () => {
  const { svg } = mount(200, 200);
  cleanup();
  const event = new WheelEvent("wheel", { bubbles: true, cancelable: true, deltaY: 100 });
  fireEvent(svg, event);
  expect(event.defaultPrevented).toBe(false);
});

it("stops panning once a venue is closed, so the next mouse move leaves the map still", () => {
  const remove = vi.fn();
  const venue = { id: "cafe", name: "Corner café", category: "cafe", x: 200, y: 600, is_focal: false } as Town["venues"][number];
  render(<TownMap town={{ ...town, venues: [venue] }} mode="remove" onPlace={vi.fn()} onRemove={remove} />);
  const svg = screen.getByRole("img", { name: "Map of Test town" });
  Object.defineProperty(svg, "getScreenCTM", { value: () => ({ inverse: () => ({ a: 4, b: 0, c: 0, d: 4, e: 0, f: 0 }) }) });
  const dot = svg.querySelector("g[transform] circle")!;
  fireEvent.pointerDown(dot, { clientX: 70, clientY: 180 });
  fireEvent.pointerUp(dot, { clientX: 70, clientY: 180 });
  expect(remove).toHaveBeenCalledWith(venue);
  fireEvent.pointerMove(svg, { clientX: 160, clientY: 90 });
  expect(svg.getAttribute("viewBox")).toBe("0 0 800 800");
});
