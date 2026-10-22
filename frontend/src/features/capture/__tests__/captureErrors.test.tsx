// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "@/shared/api/client";
import type { CaptureResult, CaptureStatus, EditedShelf } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { CapturePage } from "../CapturePage";
import { ShelfLabPanel } from "../ShelfLab";
import { EMPTY_DRAFT } from "../labDraft";

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => vi.fn(), useRouter: () => ({ state: { location: { pathname: "/capture/project" } } }) }));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  listCaptures: vi.fn(), getCapture: vi.fn(), deleteCapture: vi.fn(), getModels: vi.fn().mockResolvedValue([]),
  getSetups: vi.fn().mockResolvedValue([]), listPackages: vi.fn().mockResolvedValue([]), uploadPackage: vi.fn(),
  listEdits: vi.fn().mockResolvedValue([]), deleteEdit: vi.fn(), listLabJobs: vi.fn().mockResolvedValue([]),
}));
vi.mock("../RivalCard", () => ({ RivalCard: () => null }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const result: CaptureResult = {
  image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency: "USD",
  rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
  items: [{ id: "i1", band: 0, level: 1, order: 0, facings: 1, boxes: [], sku: "tea", name: "Tea", brand: "",
    size: "", category: "", raw_category: "", price: 100, price_estimated: false, price_text: "", confidence: 10, labeled: true }],
};
const status: CaptureStatus = {
  capture_id: "cap_test", status: "running", stage: "reading", progress: 0.5, error: "",
  options: { detector: "classic", model: "none", currency: "USD", rack_type: "shelf", label: "Tea" },
  image_name: "shelf.png", image_size: [100, 100], created_at: "", finished_at: "",
  items: 1, facings: 1, gaps: 0, levels: 1, applied_setup_ids: [],
};
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });

it("hides Delete while a capture is processing and shows why a delete failed", async () => {
  vi.mocked(api.listCaptures).mockResolvedValue([status]);
  vi.mocked(api.getCapture).mockResolvedValueOnce({ status, result: null })
    .mockResolvedValue({ status: { ...status, status: "completed", stage: "done", progress: 1 }, result });
  vi.mocked(api.deleteCapture).mockRejectedValue(new ApiError("capture is still being processed", 409));
  const queries = client();
  render(<QueryClientProvider client={queries}><CapturePage projectId="project" /></QueryClientProvider>);
  await screen.findByText("Reading products and price tags…");
  expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  await queries.refetchQueries({ queryKey: ["projects", "project", "captures", "cap_test"] });
  fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
  expect((await screen.findByRole("alert")).textContent).toBe("capture is still being processed");
});

function showLab(editId: string | null = null) {
  return render(<QueryClientProvider client={client()}>
    <ShelfLabPanel projectId="project" captureId="cap_test" result={result} draft={{ ...EMPTY_DRAFT, kind: "replace" }}
      setDraft={vi.fn()} editId={editId} onSelectEdit={vi.fn()} onFocus={vi.fn()} onAttention={vi.fn()} />
  </QueryClientProvider>);
}

it("shows why a Shelf Lab package upload failed", async () => {
  vi.mocked(api.uploadPackage).mockRejectedValue(new ApiError("The file is not a supported image.", 400));
  const { container } = showLab();
  const input = container.querySelector("input[type=file]") as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["x"], "pack.gif", { type: "image/gif" })] } });
  expect((await screen.findByRole("alert")).textContent).toBe("The file is not a supported image.");
});

it("shows why deleting a counterfactual failed", async () => {
  const edit: EditedShelf = { edit_id: "e1", capture_id: "cap_test", edits: [], changes: [], result, promos: {},
    image_size: [100, 100], created_at: "" };
  vi.mocked(api.listEdits).mockResolvedValue([edit]);
  vi.mocked(api.deleteEdit).mockRejectedValue(new ApiError("edit not found: e1", 404));
  showLab("e1");
  fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("edit not found: e1"));
});
