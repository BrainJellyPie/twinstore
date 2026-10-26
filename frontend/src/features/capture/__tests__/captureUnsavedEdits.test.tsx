// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import * as api from "@/shared/api/client";
import type { CaptureStatus, CaptureView } from "@/shared/api/client";
import { CapturePage } from "../CapturePage";

vi.mock("@tanstack/react-router", () => ({ useBlocker: () => ({ status: "idle" }), useNavigate: () => vi.fn(), useRouter: () => ({ state: { location: { pathname: "/capture/project" } } }) }));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  listCaptures: vi.fn(), getCapture: vi.fn(), updateCapture: vi.fn(), getModels: vi.fn().mockResolvedValue([]),
  getSetups: vi.fn().mockResolvedValue([]), createCapture: vi.fn(),
}));
vi.mock("../ShelfLab", () => ({ BeforeAfter: () => null, ShelfLabPanel: () => null }));
vi.mock("../RivalCard", () => ({ RivalCard: () => null }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const status = (id: string, name: string): CaptureStatus => ({
  capture_id: id, status: "completed", stage: "done", progress: 1, error: "",
  options: { detector: "classic", model: "none", currency: "USD", rack_type: "shelf", label: "" },
  image_name: name, image_size: [100, 100], created_at: "", finished_at: "", items: 1, facings: 1, gaps: 0, levels: 1, applied_setup_ids: [],
});
const view = (id: string, name: string, product: string): CaptureView => ({ status: status(id, name), result: {
  image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency: "USD",
  rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
  items: [{ id: `${id}_1`, band: 0, level: 1, order: 0, facings: 1, boxes: [], sku: "", name: product, brand: "", size: "", category: "",
    raw_category: "", price: 199, price_estimated: false, price_text: "", confidence: 0, labeled: true }],
} });

beforeEach(() => {
  vi.mocked(api.listCaptures).mockResolvedValue([status("a", "first.png"), status("b", "second.png")]);
  vi.mocked(api.getCapture).mockImplementation(async (_p, id) => id === "a" ? view("a", "first.png", "Tea") : view("b", "second.png", "Coffee"));
});

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["projects", "project"], { metadata: { currency: "USD" } });
  return render(<QueryClientProvider client={client}><CapturePage projectId="project" /></QueryClientProvider>);
}

it("keeps unsaved corrections across the Shelf Lab tab and asks before another photo drops them", async () => {
  show();
  const name = await screen.findByDisplayValue("Tea");
  fireEvent.change(name, { target: { value: "Green tea" } });

  fireEvent.click(screen.getByRole("button", { name: /Shelf Lab/ }));
  fireEvent.click(screen.getByRole("button", { name: /Planogram/ }));
  expect(screen.getByDisplayValue("Green tea")).toBeTruthy();

  fireEvent.click(screen.getByTitle("second.png"));
  expect(await screen.findByRole("alertdialog")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(screen.getByDisplayValue("Green tea")).toBeTruthy();

  fireEvent.click(screen.getByTitle("second.png"));
  fireEvent.click(await screen.findByRole("button", { name: "Leave without saving" }));
  expect(await screen.findByDisplayValue("Coffee")).toBeTruthy();
  expect(api.updateCapture).not.toHaveBeenCalled();
});
