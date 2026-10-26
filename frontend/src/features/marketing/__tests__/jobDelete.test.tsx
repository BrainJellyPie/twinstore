// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as marketing from "@/shared/api/marketing";
import { MarketingPage } from "../MarketingPage";

vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  getProject: vi.fn(),
  getSetup: vi.fn(),
  getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...(await original<typeof import("@/shared/api/marketing")>()),
  getMarketingInfo: vi.fn().mockResolvedValue({ currency: "USD" }),
  listExperiments: vi.fn(),
  listSurveys: vi.fn().mockResolvedValue([]),
  listPitches: vi.fn().mockResolvedValue([]),
  listShelfTests: vi.fn().mockResolvedValue([]),
  listConjoints: vi.fn().mockResolvedValue([]),
  getExperiment: vi.fn(() => new Promise(() => {})),
  deleteExperiment: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [] }) }));

const job: marketing.JobStatus = {
  job_id: "exp_1", kind: "experiment", name: "Tea promo", status: "completed", stage: "done", progress: 1, error: "",
  created_at: "2026-10-01T10:00:00Z", finished_at: "2026-10-01T10:05:00Z",
};
const clients: QueryClient[] = [];

beforeEach(() => {
  vi.mocked(api.getProject).mockResolvedValue({
    metadata: { currency: "USD" }, state: { activeSetupId: "s1" }, setups: [{ id: "s1", name: "Layout", status: "draft" }], personas: [],
  } as never);
  vi.mocked(api.getSetup).mockResolvedValue({ id: "s1", name: "Layout", status: "draft", store: { currency: "USD", racks: [] } } as never);
  vi.mocked(marketing.listExperiments).mockResolvedValue([job]);
  vi.mocked(marketing.deleteExperiment).mockResolvedValue(undefined);
});
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.clearAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><MarketingPage projectId="p" /></QueryClientProvider>);
}

it("asks before deleting a finished study and deletes it on the second click", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Delete Tea promo" }));
  expect(marketing.deleteExperiment).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Delete?" }));
  await waitFor(() => expect(marketing.deleteExperiment).toHaveBeenCalledWith("p", "exp_1"));
  // The deleted item held focus; it moves to the list's New test button.
  await waitFor(() => expect(document.activeElement?.textContent).toContain("New A/B test"));
});

it("leaving the delete button cancels the question", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Delete Tea promo" }));
  fireEvent.blur(screen.getByRole("button", { name: "Delete?" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete Tea promo" }));
  expect(marketing.deleteExperiment).not.toHaveBeenCalled();
});
