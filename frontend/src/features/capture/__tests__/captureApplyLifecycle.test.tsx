// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useSimulationStore } from "@/stores/simulationStore";
import { CapturePage } from "../CapturePage";

const { navigate, router } = vi.hoisted(() => ({ navigate: vi.fn(), router: { state: { location: { pathname: "/capture/project" } } } }));
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => navigate, useRouter: () => router }));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  listCaptures: vi.fn(), getCapture: vi.fn(), getModels: vi.fn(), getSetups: vi.fn(), getSetup: vi.fn(), getProject: vi.fn(), applyCapture: vi.fn(),
}));
vi.mock("../ShelfLab", () => ({ BeforeAfter: () => null, ShelfLabPanel: () => null }));
vi.mock("../RivalCard", () => ({ RivalCard: () => null }));
const clients: QueryClient[] = [];
const status: api.CaptureStatus = {
  capture_id: "cap_first", status: "completed", stage: "done", progress: 1, error: "",
  options: { detector: "classic", model: "none", currency: "USD", rack_type: "shelf", label: "Tea" },
  image_name: "first.png", image_size: [100, 100], created_at: "", finished_at: "",
  items: 0, facings: 0, gaps: 0, levels: 0, applied_setup_ids: [],
};
const result: api.CaptureResult = { image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency: "USD",
  rack_type: "shelf", bands: [], items: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false };
const applied: api.CaptureApplyResult = { setup_id: "new_layout", rack_ids: [], face: "front", placed_items: 0, placed_facings: 0, dropped: [], notes: [] };
const setup: api.SetupDetail = { id: "source", name: "Source", status: "draft", parentId: null, runId: null, memo: "", readiness: null,
  created_at: "", updated_at: "", store: null };
beforeEach(() => {
  router.state.location.pathname = "/capture/project";
  vi.mocked(api.listCaptures).mockResolvedValue([status, { ...status, capture_id: "cap_second", image_name: "second.png" }]);
  vi.mocked(api.getCapture).mockImplementation(async (_pid, captureId) => ({ status: { ...status, capture_id: captureId }, result }));
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.getSetups).mockResolvedValue([setup]);
  vi.mocked(api.getSetup).mockResolvedValue(setup);
  vi.mocked(api.applyCapture).mockResolvedValue(applied);
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); useSimulationStore.getState().reset(); });
async function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  client.setQueryData(["projects", "project"], { metadata: { currency: "USD" } });
  const mounted = render(<QueryClientProvider client={client}><CapturePage projectId="project" /></QueryClientProvider>);
  const apply = await screen.findByRole("button", { name: "Create a layout with this shelf" });
  await waitFor(() => expect((apply as HTMLButtonElement).disabled).toBe(false));
  return { ...mounted, client, apply };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

it("opens the new layout after a successful apply while the capture remains active", async () => {
  const { apply } = await mount(); fireEvent.click(apply);
  await waitFor(() => expect(navigate).toHaveBeenCalledWith({ to: "/projects/$pid", params: { pid: "project" } }));
  expect(useSimulationStore.getState().selectedSetupId).toBe("new_layout");
  expect(api.applyCapture).toHaveBeenCalledWith("project", "cap_first", { setup_id: "source", new_rack: true });
});

it("does not navigate or replace another page's selection when the user leaves before apply completes", async () => {
  const pending = deferred<api.CaptureApplyResult>(); vi.mocked(api.applyCapture).mockReturnValue(pending.promise);
  const { apply, unmount } = await mount(); fireEvent.click(apply);
  await waitFor(() => expect(api.applyCapture).toHaveBeenCalledOnce());
  unmount(); useSimulationStore.getState().setSelectedSetupId("other_project_layout");
  await act(async () => { pending.resolve(applied); });
  expect(navigate).not.toHaveBeenCalled();
  expect(useSimulationStore.getState().selectedSetupId).toBe("other_project_layout");
});

it("does not interrupt another selected capture when an older apply response arrives", async () => {
  const pending = deferred<api.CaptureApplyResult>(); vi.mocked(api.applyCapture).mockReturnValue(pending.promise);
  const { apply } = await mount(); fireEvent.click(apply);
  await waitFor(() => expect(api.applyCapture).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByTitle("second.png"));
  await waitFor(() => expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("cap_second"));
  await act(async () => { pending.resolve(applied); });
  expect(navigate).not.toHaveBeenCalled();
  expect(useSimulationStore.getState().selectedSetupId).toBeNull();
  expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("cap_second");
});

it("rechecks whether the user left while the refreshed layout list was pending", async () => {
  const refreshed = deferred<api.SetupSummary[]>();
  const { apply, unmount } = await mount();
  vi.mocked(api.getSetups).mockReturnValue(refreshed.promise);
  fireEvent.click(apply);
  await waitFor(() => expect(api.getSetups).toHaveBeenCalledTimes(2));
  expect(navigate).not.toHaveBeenCalled();
  unmount(); useSimulationStore.getState().setSelectedSetupId("elsewhere");
  await act(async () => { refreshed.resolve([setup]); });
  expect(navigate).not.toHaveBeenCalled();
  expect(useSimulationStore.getState().selectedSetupId).toBe("elsewhere");
});

it.each(["/projects/elsewhere", "/capture/another_project", "/settings"])("preserves a navigation already loading %s before the old page unmounts", async (pathname) => {
  const pending = deferred<api.CaptureApplyResult>(); vi.mocked(api.applyCapture).mockReturnValue(pending.promise);
  const { apply } = await mount(); fireEvent.click(apply);
  await waitFor(() => expect(api.applyCapture).toHaveBeenCalledOnce());
  router.state.location.pathname = pathname;
  await act(async () => { pending.resolve(applied); });
  expect(navigate).not.toHaveBeenCalled();
  expect(useSimulationStore.getState().selectedSetupId).toBeNull();
});
