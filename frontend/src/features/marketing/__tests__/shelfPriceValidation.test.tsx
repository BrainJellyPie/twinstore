// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { startShelfTest } from "@/shared/api/marketing";
import type { Store } from "@/shared/types/domain";
import { ShelfTestBuilder } from "../ShelfTest";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), startShelfTest: vi.fn(),
  previewShelf: vi.fn().mockResolvedValue({ face: "N", control: "control.png", test: "test.png", applied: [], warnings: [] }),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [] }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const store: Store = {
  id: "store", name: "Store", type: "cafe", grid_size: [8, 6], weekly_schedule: [],
  racks: [{ id: "shelf", type: "shelf", shape: [[1]], position: [2, 2], rotation: 0, levels: 4,
    dwell_min: 2, dwell_max: 30, rack_name: "Tea", rack_desc: "", rack_decoration_desc: "", locked_faces: [],
    slots: [{ block: 0, face: "N", level: 1, items: [{ sku: "tea", name: "Tea", price: 250, promo: "" }] }] }],
};

function show() {
  render(<QueryClientProvider client={new QueryClient()}>
    <ShelfTestBuilder projectId="project" setupId="setup" store={store} currency="USD" onStarted={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.change(screen.getByRole("combobox", { name: "Product under test" }), { target: { value: "tea" } });
  fireEvent.click(screen.getByRole("button", { name: "NEW" }));
  return screen.getByPlaceholderText(/leave empty to keep/);
}

it.each(["-1", "invalid", "1e3"])("does not silently discard an invalid price %s when a sign is also selected", (price) => {
  fireEvent.change(show(), { target: { value: price } });
  expect((screen.getByRole("button", { name: "Run shelf test" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByRole("alert").textContent).toMatch(/price/i);
  expect(startShelfTest).not.toHaveBeenCalled();
});

it("keeps a blank optional price and submits corrected decimal prices with the other changes", async () => {
  vi.mocked(startShelfTest).mockResolvedValue({ job_id: "slf_test", kind: "shelf", name: "Test", status: "pending",
    stage: "queued", progress: 0, error: "", created_at: "", finished_at: "" });
  const price = show();
  const run = screen.getByRole("button", { name: "Run shelf test" }) as HTMLButtonElement;
  expect(run.disabled).toBe(false);
  fireEvent.change(price, { target: { value: "1.005" } });
  fireEvent.click(run);
  await waitFor(() => expect(startShelfTest).toHaveBeenCalledWith("project", expect.objectContaining({
    changes: [expect.objectContaining({ kind: "price", price: 101 }), expect.objectContaining({ kind: "promo", promo: "NEW" })],
  })));
});
