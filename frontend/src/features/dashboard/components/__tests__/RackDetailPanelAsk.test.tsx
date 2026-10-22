// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { Rack } from "@/shared/types/domain";
import { RackDetailPanel } from "../RackDetailPanel";

afterEach(cleanup);

const rack = { id: "r1", type: "shelf", shape: [[1]], position: [1, 1], rotation: 0, levels: 4, dwell_min: 2, dwell_max: 30,
  rack_name: "Ice cream 2", rack_desc: "", rack_decoration_desc: "", locked_faces: [],
  slots: [{ block: 0, face: "N", level: 1, items: [{ sku: "ic", name: "Ice cream", price: 300, promo: "" }] }] } as unknown as Rack;

it("offers to ask the run analyst about the shelf only when a run can answer", () => {
  const onAsk = vi.fn();
  const view = render(<RackDetailPanel rack={rack} open onClose={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Ask about this shelf" })).toBeNull();
  view.rerender(<RackDetailPanel rack={rack} open onClose={vi.fn()} onAsk={onAsk} />);
  fireEvent.click(screen.getByRole("button", { name: "Ask about this shelf" }));
  expect(onAsk).toHaveBeenCalledTimes(1);
});
