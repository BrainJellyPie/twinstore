// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import type { Store } from "@/shared/types/domain";
import { FloorPlanPreview } from "../components/FloorPlanPreview";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const store: Store = { id: "preview", name: "Dining floor", type: "restaurant", grid_size: [40, 40], weekly_schedule: [], racks: [{
  id: "table", type: "table", position: [10, 10], shape: [[1, 1], [1, 1]], rotation: 0,
  levels: 4, dwell_min: 0, dwell_max: 0, rack_name: "Window table", rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [],
}] };

const gates: Store["racks"] = [
  { ...store.racks[0]!, id: "entry", type: "entrance", position: [0, 2], shape: [[1, 1]], rotation: 90, rack_name: "Side & <entry>" },
  { ...store.racks[0]!, id: "shared-exit", type: "exit", position: [0, 3], shape: [[1]], rack_name: "Shared departure" },
  { ...store.racks[0]!, id: "exit", type: "exit", position: [7, 2], shape: [[1]], rack_name: "Back departure" },
];

it("distinguishes entrance, exit and overlapping gate cells regardless of rack order", () => {
  const view = render(<FloorPlanPreview store={{ ...store, racks: gates }} areas={[]} />);
  const verify = (plan: HTMLElement) => {
    expect(plan.querySelectorAll("[data-gate-kind]")).toHaveLength(3);
    const entrance = plan.querySelector('[data-gate-kind="entrance"]')!;
    const exit = plan.querySelector('[data-gate-kind="exit"]')!;
    const shared = plan.querySelector('[data-gate-kind="shared"]')!;
    expect(entrance.querySelector("text")?.textContent).toBe("IN");
    expect(exit.querySelector("text")?.textContent).toBe("OUT");
    expect(entrance.querySelector("rect")?.getAttribute("fill")).not.toBe(exit.querySelector("rect")?.getAttribute("fill"));
    expect([...shared.querySelectorAll("text")].map((node) => node.textContent)).toEqual(["IN", "OUT"]);
    expect(shared.querySelector("title")?.textContent).toBe("Entrance and exit: Side & <entry> / Shared departure · column 1, row 4");
    expect(shared.querySelectorAll("rect")).toHaveLength(2);
  };
  verify(screen.getByRole("img", { name: "Floor plan preview" }));
  view.rerender(<FloorPlanPreview store={{ ...store, racks: [...gates].reverse() }} areas={[]} />);
  verify(screen.getByRole("img", { name: "Floor plan preview" }));
  fireEvent.click(screen.getByRole("button", { name: "Expand floor plan" }));
  verify(screen.getByRole("img", { name: "Detailed floor plan" }));
  expect(screen.getByText(/Split IN\/OUT: shared gate/)).toBeTruthy();
});

it("opens a detailed plan without submitting and returns to the unchanged creation dialog", async () => {
  const submit = vi.fn();
  render(<Dialog defaultOpen><DialogContent>
    <DialogTitle>New layout</DialogTitle><DialogDescription>Choose a layout.</DialogDescription>
    <form onSubmit={(event) => { event.preventDefault(); submit(); }}>
      <label>Layout name<input defaultValue="Keep my name" /></label>
      <FloorPlanPreview store={store} areas={[{ label: "Reading corner", x: 2, y: 3, width: 4, height: 5 }]} />
      <button type="submit">Create layout</button>
    </form>
  </DialogContent></Dialog>);
  fireEvent.click(screen.getByRole("button", { name: "Expand floor plan" }));
  expect(screen.getByRole("dialog", { name: "Floor plan details" })).toBeTruthy();
  expect(screen.getByRole("img", { name: "Detailed floor plan" }).getAttribute("viewBox")).toBe("-1.2 -1.2 41.4 41.4");
  expect(screen.getByText(/1 dining tables · 4 seats/)).toBeTruthy();
  expect(screen.getByText("Reading corner · 4×5 cells · column 3, row 4")).toBeTruthy();
  expect(screen.getByTestId("detailed-area-preview-0").getAttribute("x")).toBe("2");
  fireEvent.click(screen.getByRole("button", { name: "Zoom in floor plan" }));
  expect(screen.getByText("150%")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Fit floor plan" }));
  expect(screen.getByText("100%")).toBeTruthy();
  expect(submit).not.toHaveBeenCalled();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Floor plan details" })).toBeNull());
  expect(screen.getByRole("dialog", { name: "New layout" })).toBeTruthy();
  expect((screen.getByLabelText("Layout name") as HTMLInputElement).value).toBe("Keep my name");
  expect(submit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Create layout" }));
  expect(submit).toHaveBeenCalledOnce();
});

it("downloads the full floor at any zoom and safely preserves custom names", async () => {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:floor-plan");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<FloorPlanPreview store={{ ...store, name: "Tea & <Books>", weekly_schedule: Array.from({ length: 7 }, (_, index) => ({
    day: index + 1, is_open: index === 6, open_hour: 23, close_hour: 24,
  })), racks: [...store.racks,
    { ...store.racks[0]!, id: "table-six", position: [15, 15], shape: [[1, 1, 1], [1, 1, 1]] }, ...gates] }} areas={[{ label: "A & <B>", x: 2, y: 3, width: 4, height: 5 }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Expand floor plan" }));
  expect(screen.getByText("Operating hours: Mon–Sat: Closed; Sun: 23:00–24:00")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Zoom in floor plan" }));
  fireEvent.click(screen.getByRole("button", { name: "Download SVG" }));
  expect(screen.getByText("150%")).toBeTruthy();
  expect(click).toHaveBeenCalledOnce();
  expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe("twinstore-40x40-floor-plan.svg");
  const blob = createObjectURL.mock.calls[0]?.[0];
  if (!blob) throw new Error("No download was created");
  const source = await new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob);
  });
  const parsed = new DOMParser().parseFromString(source, "image/svg+xml");
  expect(parsed.querySelector("parsererror")).toBeNull();
  const root = parsed.documentElement;
  expect(root.namespaceURI).toBe("http://www.w3.org/2000/svg");
  expect(root.getAttribute("viewBox")).toBe("-1.2 -1.2 41.4 41.4");
  expect(root.getAttribute("width")).toBe("1600");
  expect(root.getAttribute("height")).toBe("1600");
  expect(root.getAttribute("style")).toBeNull();
  expect(root.querySelector("title")?.textContent).toBe("Tea & <Books> — 40×40 cells");
  expect(root.querySelector("desc")?.textContent).toContain("2 dining tables, 10 seats");
  expect(root.querySelector("desc")?.textContent).toContain("Operating hours: Mon–Sat: Closed; Sun: 23:00–24:00.");
  expect(root.querySelector("desc")?.textContent).toContain("Area 1: A & <B>, 4×5 cells at column 3, row 4.");
  expect(root.querySelector("desc")?.textContent).toContain("Split IN/OUT: shared gate");
  const shared = root.querySelector('[data-gate-kind="shared"]')!;
  expect(shared.querySelector("title")?.textContent).toContain("Side & <entry> / Shared departure");
  expect([...shared.querySelectorAll("text")].map((node) => node.textContent)).toEqual(["IN", "OUT"]);
  expect(root.querySelector('[data-gate-kind="exit"] text')?.textContent).toBe("OUT");
  expect(root.querySelector("image, script, foreignObject")).toBeNull();
  await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:floor-plan"));
});

function luminance(hex: string) {
  const rgb = [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return rgb[0]! * 0.2126 + rgb[1]! * 0.7152 + rgb[2]! * 0.0722;
}
function contrast(a: string, b: string) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light! + 0.05) / (dark! + 0.05);
}
it.each(["#000000", "#ffffff", "#757575", "#808080", "#f59e0b", "#475569", "#1b2140", "#ff00ff"])("keeps coordinates, reserved labels and fixture boundaries legible on custom floor %s", (floor) => {
  render(<FloorPlanPreview store={{ ...store, design_colors: { floor } }} areas={[{ label: "Meeting", x: 2, y: 3, width: 2, height: 2 }]} />);
  fireEvent.click(screen.getByRole("button", { name: "Expand floor plan" }));
  const svg = screen.getByRole("img", { name: "Detailed floor plan" });
  const axis = svg.querySelector("text")!;
  expect(contrast(axis.getAttribute("fill")!, floor)).toBeGreaterThanOrEqual(4.5);
  const area = screen.getByTestId("detailed-area-preview-0");
  const label = area.parentElement!.querySelector("text")!;
  expect(contrast(label.getAttribute("fill")!, floor)).toBeGreaterThanOrEqual(4.5);
  const table = [...svg.querySelectorAll("rect")].find((rect) => rect.querySelector("title")?.textContent === "Window table")!;
  expect(contrast(table.getAttribute("stroke")!, floor)).toBeGreaterThanOrEqual(3);
});
