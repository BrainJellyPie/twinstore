// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useCreateLayout } from "@/features/layouts/hooks/useCreateLayout";
import { Route } from "../../routes/projects/$pid";

vi.mock("@/shared/api/client", () => ({ getProject: vi.fn(), getSetups: vi.fn(), getSetup: vi.fn(), getRuns: vi.fn(), deleteProject: vi.fn(), createSetup: vi.fn(), generateBuilding: vi.fn(), generateLayout: vi.fn(), importFloorPlan: vi.fn() }));
vi.mock("@/shared/queries/useSetupGeneration", () => ({ useSetupGeneration: () => ({ phase: "idle" }) }));
vi.mock("@/views/simulation/states/PreparingView", () => ({ PreparingView: () => null }));
vi.mock("@/views/simulation/states/ReadyView", () => ({ ReadyView: () => null }));
vi.mock("@/views/simulation/states/RunningView", () => ({ RunningView: () => null }));
vi.mock("@/views/simulation/states/PlaybackView", () => ({ PlaybackView: () => null }));
vi.mock("@/views/simulation/states/EmptyFloorReadyView", () => ({
  EmptyFloorReadyView: ({ pid, setupId, layouts, onLayoutSelect, onAddLayout }: {
    pid: string; setupId: string; layouts: { id: string }[]; onLayoutSelect: (id: string) => void; onAddLayout: () => void;
  }) => <div><output data-testid="project">{pid}</output><output data-testid="setup">{setupId}</output>
    {layouts.map((layout) => <button key={layout.id} onClick={() => onLayoutSelect(layout.id)}>{layout.id}</button>)}
    <button onClick={onAddLayout}>New layout</button></div>,
}));
vi.mock("@/features/layouts/components/AddLayoutDialog", () => ({
  AddLayoutDialog: function TestAddLayoutDialog({ open, projectId }: { open: boolean; projectId: string }) {
    const createLayout = useCreateLayout();
    return open ? <div role="dialog">Add to {projectId}
      <button onClick={() => createLayout.mutate({ projectId, name: "New", source: { kind: "empty" } })}>Create blank</button>
      {createLayout.isError && <span role="alert">Creation failed</span>}
    </div> : null;
  },
}));
const clients: QueryClient[] = [];
const setup = (id: string): api.SetupDetail => ({ id, name: id, status: "draft", parentId: null, runId: null,
  memo: "", readiness: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", store: null });
function project(pid: string, ids: string[]): api.ProjectDetail {
  return { projectId: pid, metadata: { project_id: pid, name: pid, description: "", store_type: "convenience", currency: "USD",
    grid_size: null, weekly_schedule: [], address: "", customer_profile: "", supplemental_summary: "", created_at: "", updated_at: "" },
    personas: [], state: { activeSetupId: ids[0] ?? "", runningSetups: [] }, setups: ids.map(setup), personasLocked: false };
}
beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getProject).mockImplementation(async (pid) => project(pid, pid === "alpha" ? ["a1", "a2"] : ["b1", "b2"]));
  vi.mocked(api.getSetup).mockImplementation(async (_pid, id) => setup(id));
  vi.mocked(api.getRuns).mockResolvedValue([]);
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach((client) => client.clear());
  useSimulationStore.getState().reset(); usePlaybackControlStore.getState().reset(); useSimulationMetricsStore.getState().reset();
  vi.resetAllMocks();
  vi.restoreAllMocks();
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function mount(secondIds = ["b1", "b2"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  for (const [pid, ids] of [["alpha", ["a1", "a2"]], ["beta", secondIds]] as const) {
    client.setQueryData(queryKeys.project(pid), project(pid, [...ids]));
    client.setQueryData(queryKeys.setups(pid), ids.map(setup));
    for (const id of ids) {
      client.setQueryData(queryKeys.setup(pid, id), setup(id));
      client.setQueryData(queryKeys.runs(pid, id), []);
    }
  }
  const root = createRootRoute({ component: Outlet });
  const route = createRoute({ getParentRoute: () => root, path: "/projects/$pid", component: Route.options.component });
  const router = createRouter({ routeTree: root.addChildren([route]), history: createMemoryHistory({ initialEntries: ["/projects/alpha"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByText("alpha", { selector: "output" });
  fireEvent.click(screen.getByRole("button", { name: "a2" }));
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a2"));
  return { client, router };
}

it("does not request another project's selected layout on direct navigation", async () => {
  const { router } = await mount();
  await act(async () => { await router.navigate({ to: "/projects/$pid", params: { pid: "beta" } }); });
  await waitFor(() => expect(screen.getByTestId("project").textContent).toBe("beta"));
  expect(screen.getByTestId("setup").textContent).toBe("b1");
  expect(api.getSetup).not.toHaveBeenCalled();
  expect(useSimulationStore.getState().selectedSetupId).toBe("b1");
});

it("closes the old layout dialog and resets playback even when layout IDs coincide", async () => {
  const { router } = await mount(["a2", "b2"]);
  fireEvent.click(screen.getByRole("button", { name: "New layout" }));
  act(() => {
    usePlaybackControlStore.getState().play(); usePlaybackControlStore.getState().setSpeed(600);
    usePlaybackControlStore.getState().seek(123); usePlaybackControlStore.getState().setDay(7);
    useSimulationMetricsStore.getState().setMetrics({ revenue: 12345, entered: 99 });
    useSimulationStore.getState().setFollowPersonaId("old-person");
  });
  await act(async () => { await router.navigate({ to: "/projects/$pid", params: { pid: "beta" } }); });
  await waitFor(() => expect(screen.getByTestId("project").textContent).toBe("beta"));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(usePlaybackControlStore.getState()).toMatchObject({ playing: false, speed: 60, currentDay: 1, seekTarget: null });
  expect(useSimulationMetricsStore.getState()).toMatchObject({ revenue: 0, entered: 0 });
  expect(useSimulationStore.getState().followPersonaId).toBeNull();
});

it("does not request the previous layout while the next project has no layouts", async () => {
  const { router } = await mount([]);
  await act(async () => { await router.navigate({ to: "/projects/$pid", params: { pid: "beta" } }); });
  await screen.findByText("Loading layout…");
  expect(api.getSetup).not.toHaveBeenCalled();
  expect(screen.queryByTestId("setup")).toBeNull();
});

it("falls back when a selected layout disappears from the current project", async () => {
  const { client } = await mount();
  await act(async () => { client.setQueryData(queryKeys.setups("alpha"), [setup("a1")]); });
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(useSimulationStore.getState().selectedSetupId).toBe("a1");
});

it("keeps a valid selection and playback state when the same project is refreshed", async () => {
  const { client } = await mount();
  act(() => { usePlaybackControlStore.getState().play(); useSimulationMetricsStore.getState().setMetrics({ revenue: 321 }); });
  await act(async () => { client.setQueryData(queryKeys.project("alpha"), { ...project("alpha", ["a1", "a2"]), personasLocked: true }); });
  expect(screen.getByTestId("setup").textContent).toBe("a2");
  expect(usePlaybackControlStore.getState().playing).toBe(true);
  expect(useSimulationMetricsStore.getState().revenue).toBe(321);
  expect(api.getSetup).not.toHaveBeenCalled();
});

it.each([false, true])("selects a newly created layout before list refresh completes (old request: %s)", async (oldRequest) => {
  const { client } = await mount();
  const beforeCreate = deferred<api.SetupSummary[]>();
  const afterCreate = deferred<api.SetupSummary[]>();
  vi.mocked(api.getSetups).mockReturnValue(afterCreate.promise);
  if (oldRequest) {
    vi.mocked(api.getSetups).mockReturnValueOnce(beforeCreate.promise);
    void client.invalidateQueries({ queryKey: queryKeys.setups("alpha") });
    await waitFor(() => expect(api.getSetups).toHaveBeenCalledOnce());
  }
  vi.mocked(api.createSetup).mockResolvedValue({ ...setup("a3"), status: "draft" });
  fireEvent.click(screen.getByRole("button", { name: "New layout" }));
  fireEvent.click(screen.getByRole("button", { name: "Create blank" }));
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a3"));
  expect(client.getQueryData<api.SetupSummary[]>(queryKeys.setups("alpha"))?.map((item) => item.id)).toEqual(["a1", "a2", "a3"]);
  await act(async () => { beforeCreate.resolve([setup("a1"), setup("a2")]); });
  expect(screen.getByTestId("setup").textContent).toBe("a3");
  await act(async () => { afterCreate.resolve([setup("a1"), setup("a2"), setup("a3")]); });
  expect(useSimulationStore.getState().selectedSetupId).toBe("a3");
});

it("does not change the current project selection when creation in the old project finishes late", async () => {
  const { client, router } = await mount();
  const created = deferred<api.SetupSummaryShort>();
  vi.mocked(api.createSetup).mockReturnValue(created.promise);
  fireEvent.click(screen.getByRole("button", { name: "New layout" }));
  fireEvent.click(screen.getByRole("button", { name: "Create blank" }));
  await waitFor(() => expect(api.createSetup).toHaveBeenCalledOnce());
  await act(async () => { await router.navigate({ to: "/projects/$pid", params: { pid: "beta" } }); });
  fireEvent.click(await screen.findByRole("button", { name: "b2" }));
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("b2"));
  await act(async () => { created.resolve({ ...setup("a3"), status: "draft" }); });
  await waitFor(() => expect(client.getQueryData<api.SetupSummary[]>(queryKeys.setups("alpha"))?.some((item) => item.id === "a3")).toBe(true));
  expect(screen.getByTestId("setup").textContent).toBe("b2");
  expect(useSimulationStore.getState().selectedSetupId).toBe("b2");
  expect(api.getSetup).not.toHaveBeenCalled();
});

it("preserves selection if layout creation fails", async () => {
  await mount();
  vi.mocked(api.createSetup).mockRejectedValue(new Error("Creation failed"));
  fireEvent.click(screen.getByRole("button", { name: "New layout" }));
  fireEvent.click(screen.getByRole("button", { name: "Create blank" }));
  await screen.findByRole("alert");
  expect(screen.getByTestId("setup").textContent).toBe("a2");
  expect(useSimulationStore.getState().selectedSetupId).toBe("a2");
  expect(api.getSetups).not.toHaveBeenCalled();
});
