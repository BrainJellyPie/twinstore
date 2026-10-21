// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "@/shared/api/client";
import type { CaptureResult, LabJobStatus, Sim2RealReport } from "@/shared/api/client";
import { ShelfLabPanel } from "../ShelfLab";
import { EMPTY_DRAFT } from "../labDraft";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  listPackages: vi.fn().mockResolvedValue([]), listEdits: vi.fn().mockResolvedValue([]),
  listLabJobs: vi.fn().mockResolvedValue([]), getSetups: vi.fn().mockResolvedValue([]),
  startSim2Real: vi.fn(), getLabJob: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const status: LabJobStatus = {
  job_id: "s2r_test", kind: "sim2real", capture_id: "cap_test", status: "completed", progress: 1,
  stage: "done", error: "", created_at: "", finished_at: "",
};
const result: CaptureResult = {
  image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "fake", currency: "USD",
  rack_type: "shelf", bands: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false,
  items: [{ id: "i1", band: 0, level: 1, order: 0, facings: 1, boxes: [], sku: "tea", name: "Tea", brand: "",
    size: "", category: "", raw_category: "", price: 100, price_estimated: false, price_text: "", confidence: 10, labeled: true }],
};

async function show(pairs: number) {
  const report: Sim2RealReport = {
    job_id: status.job_id, capture_id: status.capture_id, edit_id: "", model: "fake", personas: 2,
    conditions: ["render", "photo"], products: { tea: "Tea" }, answers: [], notes: [], seconds: 1,
    agreement: [{ condition: "photo", pairs, same_pick: 0, ci_low: 0, ci_high: 0, interest_spearman: null }],
    stats: [{ condition: "photo", answers: pairs, errors: 2 - pairs, none_rate: 0, mean_interest: 0, level_share: {}, picks: {} }],
  };
  vi.mocked(api.startSim2Real).mockResolvedValue(status);
  vi.mocked(api.getLabJob).mockResolvedValue({ status, sim2real: report, audit: null });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ShelfLabPanel projectId="project" captureId="cap_test" result={result} draft={EMPTY_DRAFT} setDraft={vi.fn()}
      editId={null} onSelectEdit={vi.fn()} onFocus={vi.fn()} onAttention={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Run sim2real panel" }));
  await screen.findByText("Photo + tags vs render");
}

it("does not present an old report with no response pairs as zero agreement", async () => {
  await show(0);
  expect(screen.queryByText("0%")).toBeNull();
  expect(screen.getByText("No complete response pairs")).toBeTruthy();
  expect(screen.queryByText("0% none")).toBeNull();
  expect(screen.getByText("No successful responses")).toBeTruthy();
  expect(screen.getByText("2 model calls failed")).toBeTruthy();
});

it("keeps a measured zero-agreement result visible when a pair exists", async () => {
  await show(1);
  expect(screen.getByText("0%")).toBeTruthy();
  expect(screen.queryByText("No complete response pairs")).toBeNull();
  expect(screen.getByText("1 model call failed")).toBeTruthy();
});
