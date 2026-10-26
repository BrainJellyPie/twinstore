// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "@/shared/api/client";
import type { CaptureResult } from "@/shared/api/client";
import { ShelfLabPanel } from "../ShelfLab";
import { EMPTY_DRAFT, type LabDraft } from "../labDraft";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  listPackages: vi.fn().mockResolvedValue([]), listEdits: vi.fn().mockResolvedValue([]),
  listLabJobs: vi.fn().mockResolvedValue([]), getSetups: vi.fn().mockResolvedValue([]), createEdit: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const item = (id: string, name: string, order: number) => ({
  id, band: 0, level: 1, order, facings: 1, boxes: [], sku: id, name, brand: "", size: "", category: "", raw_category: "",
  price: 100, price_estimated: false, price_text: "", confidence: 10, labeled: true,
});
const result: CaptureResult = {
  image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "fake", currency: "USD",
  rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
  items: [item("tea", "Tea", 0), item("cola", "Cola", 1)],
};

function Panel() {
  const [draft, setDraft] = useState<LabDraft>(EMPTY_DRAFT);
  return <ShelfLabPanel projectId="project" captureId="cap" result={result} draft={draft} setDraft={setDraft}
    editId={null} onSelectEdit={vi.fn()} onFocus={vi.fn()} onAttention={vi.fn()} />;
}

it("chooses the products of a swap from lists as well as on the photo, and clears one with its own button", async () => {
  vi.mocked(api.createEdit).mockImplementation(() => new Promise(() => {}));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Panel /></QueryClientProvider>);
  fireEvent.change(screen.getByRole("combobox", { name: "Product" }), { target: { value: "tea" } });
  fireEvent.change(screen.getByRole("combobox", { name: "With" }), { target: { value: "cola" } });
  const clear = screen.getByRole("button", { name: "Clear With" });
  expect(clear.closest("button, select")).toBe(clear);  // not nested inside another control
  fireEvent.click(screen.getByRole("button", { name: "Render counterfactual" }));
  await waitFor(() => expect(api.createEdit).toHaveBeenCalledWith("project", "cap", [{ kind: "swap", item_id: "tea", other_id: "cola" }]));
  fireEvent.click(clear);
  expect((screen.getByRole("combobox", { name: "With" }) as HTMLSelectElement).value).toBe("");
});

it("marks a price tag that cannot be read as the field in error", async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Panel /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Price tag/ }));
  const field = screen.getByPlaceholderText("New price (USD)");
  expect(field.getAttribute("aria-invalid")).toBe("false");
  fireEvent.change(field, { target: { value: "abc" } });
  expect(field.getAttribute("aria-invalid")).toBe("true");
  expect(field.getAttribute("aria-describedby")).toBe(screen.getByRole("alert").id);
});
