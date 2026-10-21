// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import type { Store } from "@/shared/types/domain";
import { FloorPlanPreview } from "../components/FloorPlanPreview";

afterEach(cleanup);

const store: Store = { id: "preview", name: "Dining floor", type: "restaurant", grid_size: [40, 40], weekly_schedule: [], racks: [{
  id: "table", type: "table", position: [10, 10], shape: [[1, 1], [1, 1]], rotation: 0,
  levels: 4, dwell_min: 0, dwell_max: 0, rack_name: "Window table", rack_desc: "", rack_decoration_desc: "", locked_faces: [], slots: [],
}] };

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
