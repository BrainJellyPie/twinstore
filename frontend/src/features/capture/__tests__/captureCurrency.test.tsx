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
beforeEach(() => vi.mocked(api.listCaptures).mockResolvedValue([]));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const status: CaptureStatus = {
  capture_id: "cap_test", status: "completed", stage: "done", progress: 1, error: "",
  options: { detector: "classic", model: "none", currency: "JPY", rack_type: "shelf", label: "Tea" },
  image_name: "shelf.png", image_size: [100, 100], created_at: "", finished_at: "",
  items: 1, facings: 1, gaps: 0, levels: 1, applied_setup_ids: [],
};

function show(currency: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["projects", "project"], { metadata: { currency } });
  return render(<QueryClientProvider client={client}><CapturePage projectId="project" /></QueryClientProvider>);
}

it.each(["KRW", "JPY"])("defaults new captures to the project's %s prices", async (currency) => {
  show(currency);
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Prices in" }) as HTMLSelectElement).value).toBe(currency));
});

it.each([
  ["JPY", "2500", "2600", 2600], ["KRW", "2500", "2600", 2600], ["USD", "25.00", "1.005", 101],
])("edits %s shelf prices in their currency unit with exact decimal rounding", async (currency, displayed, entered, expected) => {
  const view: CaptureView = { status, result: {
    image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency,
    rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
    items: [{ id: "i1", band: 0, level: 1, order: 0, facings: 1, boxes: [], sku: "tea", name: "Tea", brand: "",
      size: "", category: "", raw_category: "", price: 2500, price_estimated: false, price_text: "", confidence: 10, labeled: true }],
  } };
  vi.mocked(api.listCaptures).mockResolvedValue([status]);
  vi.mocked(api.getCapture).mockResolvedValue(view);
  vi.mocked(api.updateCapture).mockResolvedValue(view);
  show(currency);
  const price = await screen.findByPlaceholderText("price") as HTMLInputElement;
  expect(price.value).toBe(displayed);
  fireEvent.change(price, { target: { value: entered } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(api.updateCapture).toHaveBeenCalledWith("project", "cap_test", [expect.objectContaining({ price: expected })]));
});

it("keeps untouched estimated prices estimated when saving another correction", async () => {
  const item = { id: "i1", band: 0, level: 1, order: 0, facings: 1, boxes: [], sku: "tea", name: "Tea", brand: "",
    size: "", category: "", raw_category: "", price: 2500, price_estimated: true, price_text: "", confidence: 10, labeled: true };
  const view: CaptureView = { status, result: {
    image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency: "JPY",
    rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
    items: [item, { ...item, id: "i2", order: 1, sku: "coffee", name: "Coffee", price: 300 }],
  } };
  vi.mocked(api.listCaptures).mockResolvedValue([status]);
  vi.mocked(api.getCapture).mockResolvedValue(view);
  vi.mocked(api.updateCapture).mockResolvedValue(view);
  show("JPY");
  const [tea, coffee] = await screen.findAllByPlaceholderText("price") as HTMLInputElement[];
  // Each row's fields carry the product's name, so a list of many rows stays tellable apart by ear.
  expect(screen.getByRole("textbox", { name: "Price of Coffee" })).toBe(coffee);
  expect(screen.getByRole("combobox", { name: "Category of Tea" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "More facings of Coffee" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Remove Tea" })).toBeTruthy();
  fireEvent.change(screen.getAllByPlaceholderText("Product name")[0]!, { target: { value: "Green tea" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(api.updateCapture).toHaveBeenCalledWith("project", "cap_test", [
    expect.objectContaining({ id: "i1", name: "Green tea", price: null }), expect.objectContaining({ id: "i2", price: null }),
  ]));
  expect(tea!.value).toBe("2500");
  fireEvent.change(coffee!, { target: { value: "320" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(api.updateCapture).toHaveBeenLastCalledWith("project", "cap_test", [
    expect.objectContaining({ id: "i1", price: null }), expect.objectContaining({ id: "i2", price: 320 }),
  ]));
});

it("marks the one price that cannot be read, so it can be found in a long shelf", async () => {
  const item = (id: string, name: string) => ({ id, band: 0, level: 1, order: 0, facings: 1, boxes: [], sku: id, name, brand: "",
    size: "", category: "", raw_category: "", price: 250, price_estimated: false, price_text: "", confidence: 10, labeled: true });
  const view: CaptureView = { status, result: {
    image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency: "USD",
    rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
    items: [item("i1", "Tea"), item("i2", "Cola")],
  } };
  vi.mocked(api.listCaptures).mockResolvedValue([status]);
  vi.mocked(api.getCapture).mockResolvedValue(view);
  show("USD");
  const cola = await screen.findByLabelText("Price of Cola");
  fireEvent.change(cola, { target: { value: "-5" } });
  const alert = await screen.findByRole("alert");
  expect(cola.getAttribute("aria-invalid")).toBe("true");
  expect(cola.getAttribute("aria-describedby")).toBe(alert.id);
  expect(screen.getByLabelText("Price of Tea").getAttribute("aria-invalid")).toBe("false");
});

it("has nothing to save after a typed estimated price is put back as it was", async () => {
  const view: CaptureView = { status, result: {
    image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency: "USD",
    rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
    items: [{ id: "i1", band: 0, level: 1, order: 0, facings: 1, boxes: [], sku: "tea", name: "Tea", brand: "",
      size: "", category: "", raw_category: "", price: null, price_estimated: true, price_text: "", confidence: 10, labeled: true }],
  } };
  vi.mocked(api.listCaptures).mockResolvedValue([status]);
  vi.mocked(api.getCapture).mockResolvedValue(view);
  show("USD");
  const price = await screen.findByLabelText("Price of Tea");
  fireEvent.change(price, { target: { value: "-" } });
  expect(screen.getByRole("button", { name: "Save changes" })).toBeTruthy();
  fireEvent.change(price, { target: { value: "" } });
  expect(screen.getByRole("button", { name: "Saved" })).toBeTruthy();
  expect(price.getAttribute("title")).toBe("Tag unreadable — typical price for the category");
});
