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
import type { GenerationListItem, GenerationStatus } from "@/shared/types/domain";
import type { SetupGenerationState } from "@/shared/queries/useSetupGeneration";
import { Route } from "../../routes/projects/$pid";

vi.mock("@/shared/api/client", () => ({ getProject: vi.fn(), getSetups: vi.fn(), getSetup: vi.fn(), getRuns: vi.fn(), deleteProject: vi.fn(), createSetup: vi.fn(), generateBuilding: vi.fn(), generateLayout: vi.fn(), importFloorPlan: vi.fn(), getSetupGenerations: vi.fn(), getGenerationStatus: vi.fn(), regeneratePersona: vi.fn() }));
vi.mock("@/views/simulation/states/PreparingView", () => ({ PreparingView: ({ generation, onAbandonProject, onBackToStores }: {
  generation: SetupGenerationState; onAbandonProject: () => Promise<void>; onBackToStores: () => void;
}) =>
  <div><output data-testid="generation">{generation.phase}:{generation.currentGenId}</output><button onClick={generation.retry}>Retry generation</button>
    <button onClick={() => { void onAbandonProject().catch(() => {}); }}>Confirmed deletion</button><button onClick={onBackToStores}>Return to stores</button></div>,
}));
vi.mock("@/views/simulation/states/ReadyView", () => ({ ReadyView: () => null }));
vi.mock("@/views/simulation/states/RunningView", () => ({ RunningView: () => null }));
vi.mock("@/views/simulation/states/PlaybackView", () => ({ PlaybackView: () => null }));
vi.mock("@/views/simulation/states/EmptyFloorReadyView", () => ({
  EmptyFloorReadyView: ({ pid, setupId, layouts, onLayoutSelect, onAddLayout }: {
    pid: string; setupId: string; layouts: { id: string }[]; onLayoutSelect: (id: string) => void; onAddLayout: () => void;
  }) => <div><output data-testid="project">{pid}</output><output data-testid="setup">{setupId}</output>
    {layouts.map((layout) => <button key={layout.id} data-layout-id={layout.id} onClick={() => onLayoutSelect(layout.id)}>{layout.id}</button>)}
    <button data-layout-finder-trigger>Test finder</button><button data-layout-finder-result onClick={() => onLayoutSelect(layouts[0]!.id)}>First result</button>
    <button onClick={onAddLayout}>New layout</button></div>,
}));
vi.mock("@/features/layouts/components/AddLayoutDialog", () => ({
  AddLayoutDialog: function TestAddLayoutDialog({ open, projectId, onOpenChange, isCurrentProject }: { open: boolean; projectId: string; onOpenChange: (open: boolean) => void; isCurrentProject?: () => boolean }) {
    const createLayout = useCreateLayout({ active: open, projectId, canSelect: isCurrentProject });
    return open ? <div role="dialog">Add to {projectId}<button onClick={() => onOpenChange(false)}>Close creation</button>
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
  vi.mocked(api.getSetupGenerations).mockResolvedValue([]);
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

async function mount(secondIds = ["b1", "b2"], settingsLoader?: () => Promise<void>) {
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
  const settings = createRoute({ getParentRoute: () => root, path: "/settings", loader: settingsLoader, component: () => <output>Settings page</output> });
  const router = createRouter({ routeTree: root.addChildren([route, settings]), defaultPendingMs: 60_000, history: createMemoryHistory({ initialEntries: ["/projects/alpha"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByText("alpha", { selector: "output" });
  fireEvent.click(screen.getByRole("button", { name: "a2" }));
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a2"));
  return { client, router };
}

async function mountFailed(pathname = "/projects/alpha", settingsLoader?: () => Promise<void>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  const failed = { ...setup("a1"), readiness: { ready: false, reasons: ["layout_pending" as const] } };
  client.setQueryData(queryKeys.project("alpha"), project("alpha", ["a1"]));
  client.setQueryData(queryKeys.setups("alpha"), [failed]); client.setQueryData(queryKeys.setup("alpha", "a1"), failed);
  client.setQueryData(queryKeys.runs("alpha", "a1"), []);
  vi.mocked(api.getSetups).mockResolvedValue([failed]);
  vi.mocked(api.getSetupGenerations).mockResolvedValue([{ gen_id: "failed_layout", status: "failed", kind: "layout", setup_id: "a1", error: "Layout failed", progress: null, created_at: null, updated_at: null }]);
  const root = createRootRoute({ component: Outlet });
  const route = createRoute({ getParentRoute: () => root, path: "/projects/$pid", component: Route.options.component });
  const wizard = createRoute({ getParentRoute: () => root, path: "/projects/new", component: () => <output>New-store form</output> });
  const home = createRoute({ getParentRoute: () => root, path: "/", component: () => <output>Store list</output> });
  const settings = createRoute({ getParentRoute: () => root, path: "/settings", loader: settingsLoader, component: () => <output>Settings page</output> });
  const router = createRouter({ routeTree: root.addChildren([route, wizard, home, settings]), defaultPendingMs: 60_000,
    history: createMemoryHistory({ initialEntries: [pathname] }) });
  await router.load(); render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByText("failed:failed_layout", { selector: "output" });
  return { router };
}

it.each(["/projects/alpha", "/projects/alpha/"])("opens the wizard after confirmed deletion from %s", async (pathname) => {
  vi.mocked(api.deleteProject).mockResolvedValue({ status: "deleted" }); const { router } = await mountFailed(pathname);
  fireEvent.click(screen.getByRole("button", { name: "Confirmed deletion" })); await screen.findByText("New-store form");
  expect(api.deleteProject).toHaveBeenCalledWith("alpha"); expect(router.state.location.pathname).toBe("/projects/new");
});

it("opens the new-store form even though the deleted store's data is gone", async () => {
  vi.mocked(api.deleteProject).mockResolvedValue({ status: "deleted" }); const { router } = await mountFailed();
  // After deletion the store has no layouts left and its details 404 — refetching them used to leave
  // "No layouts found" with the deleted store in the breadcrumb.
  const gone = () => Promise.reject(new Error("HTTP 404: Project not found"));
  vi.mocked(api.getProject).mockImplementation(gone); vi.mocked(api.getSetups).mockResolvedValue([]);
  vi.mocked(api.getSetup).mockImplementation(gone); vi.mocked(api.getRuns).mockImplementation(gone);
  vi.mocked(api.getSetupGenerations).mockImplementation(gone);
  fireEvent.click(screen.getByRole("button", { name: "Confirmed deletion" }));
  await screen.findByText("New-store form");
  expect(router.state.location.pathname).toBe("/projects/new");
  expect(api.getProject).not.toHaveBeenCalled(); expect(api.getSetups).not.toHaveBeenCalled();
});

it("keeps the current page after a deletion failure", async () => {
  vi.mocked(api.deleteProject).mockRejectedValue(new Error("Deletion unavailable")); const { router } = await mountFailed();
  fireEvent.click(screen.getByRole("button", { name: "Confirmed deletion" }));
  await waitFor(() => expect(api.deleteProject).toHaveBeenCalledOnce());
  expect(router.state.location.pathname).toBe("/projects/alpha"); expect(screen.queryByText("New-store form")).toBeNull();
});

it("preserves a destination already loading while deletion completes on the old page", async () => {
  const deletion = deferred<{ status: string }>(), loading = deferred<void>(); vi.mocked(api.deleteProject).mockReturnValue(deletion.promise);
  const { router } = await mountFailed("/projects/alpha", () => loading.promise);
  fireEvent.click(screen.getByRole("button", { name: "Confirmed deletion" })); await waitFor(() => expect(api.deleteProject).toHaveBeenCalledOnce());
  let navigation!: Promise<void>; act(() => { navigation = router.navigate({ to: "/settings" }); });
  await waitFor(() => expect(router.state.location.pathname).toBe("/settings"));
  expect(screen.getByRole("button", { name: "Confirmed deletion" })).toBeTruthy();
  await act(async () => deletion.resolve({ status: "deleted" }));
  expect(router.state.location.pathname).toBe("/settings"); expect(screen.queryByText("New-store form")).toBeNull();
  await act(async () => { loading.resolve(); await navigation; }); await screen.findByText("Settings page");
});

it("returns to stores without deleting the failed project", async () => {
  const { router } = await mountFailed(); fireEvent.click(screen.getByRole("button", { name: "Return to stores" }));
  await screen.findByText("Store list"); expect(router.state.location.pathname).toBe("/"); expect(api.deleteProject).not.toHaveBeenCalled();
});

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
  await screen.findByText("No layouts found.");
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

it("keeps the selected layout while its uncached details are loading", async () => {
  const { client } = await mount();
  const details = deferred<api.SetupDetail>();
  client.removeQueries({ queryKey: queryKeys.setup("alpha", "a1"), exact: true });
  vi.mocked(api.getSetup).mockReturnValue(details.promise);
  fireEvent.click(screen.getByRole("button", { name: "a1" }));
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "a1", expect.any(AbortSignal)));
  expect(useSimulationStore.getState().selectedSetupId).toBe("a1");
  await act(async () => { details.resolve(setup("a1")); });
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(useSimulationStore.getState().selectedSetupId).toBe("a1");
});

it.each(["layout", "persona"] as const)("does not poll an old %s job under the replacement layout", async (kind) => {
  const listing = deferred<GenerationListItem[]>();
  const oldStatus = deferred<GenerationStatus>();
  const generation: GenerationListItem = { gen_id: "old-generation", setup_id: "a2", kind, status: "running", error: null, progress: null, created_at: null, updated_at: null };
  vi.mocked(api.getSetupGenerations).mockImplementation(async (_pid, sid) => sid === "a2" ? listing.promise : []);
  vi.mocked(api.getGenerationStatus).mockReturnValue(oldStatus.promise);
  const { client } = await mount();
  await act(async () => { listing.resolve([generation]); });
  await screen.findByTestId("generation");
  expect(api.getGenerationStatus).toHaveBeenCalledWith("alpha", "a2", "old-generation");
  await act(async () => { client.setQueryData(queryKeys.setups("alpha"), [setup("a1")]); });
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(api.getGenerationStatus).not.toHaveBeenCalledWith("alpha", "a1", "old-generation");
  await act(async () => { oldStatus.resolve({ ...generation, status: "failed", error: "Old layout disappeared" }); });
  expect(screen.getByTestId("setup").textContent).toBe("a1");
  expect(screen.queryByTestId("generation")).toBeNull();
});

it("ignores a late persona retry response from a removed layout", async () => {
  const listing = deferred<GenerationListItem[]>();
  const retried = deferred<{ gen_id: string }>();
  vi.mocked(api.getSetupGenerations).mockImplementation(async (_pid, sid) => sid === "a2" ? listing.promise : []);
  vi.mocked(api.regeneratePersona).mockReturnValue(retried.promise);
  vi.mocked(api.getGenerationStatus).mockImplementation(() => new Promise(() => {}));
  const { client } = await mount();
  await act(async () => { listing.resolve([{ gen_id: "failed-generation", setup_id: "a2", kind: "persona", status: "failed", error: "Failed", progress: null, created_at: null, updated_at: null }]); });
  fireEvent.click(await screen.findByRole("button", { name: "Retry generation" }));
  await waitFor(() => expect(api.regeneratePersona).toHaveBeenCalledWith("alpha", "a2"));
  await act(async () => { client.setQueryData(queryKeys.setups("alpha"), [setup("a1")]); });
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  await act(async () => { retried.resolve({ gen_id: "late-generation" }); });
  expect(api.getGenerationStatus).not.toHaveBeenCalled();
  expect(screen.getByTestId("setup").textContent).toBe("a1");
});


it("restores focus to the opened layout after keyed content is replaced", async () => {
  await mount(); const target = screen.getByRole("button", { name: "a1" }); target.focus(); fireEvent.click(target);
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "a1" }));
});
it("preserves focus moved outside while a requested layout is still loading", async () => {
  const { client } = await mount(); const loading = deferred<api.SetupDetail>();
  client.removeQueries({ queryKey: queryKeys.setup("alpha", "a1") }); vi.mocked(api.getSetup).mockReturnValue(loading.promise);
  const outside = document.createElement("button"); outside.textContent = "Other control"; document.body.append(outside);
  try {
    const target = screen.getByRole("button", { name: "a1" }); target.focus(); fireEvent.click(target);
    await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "a1", expect.any(AbortSignal))); outside.focus();
    await act(async () => loading.resolve(setup("a1"))); await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
    expect(document.activeElement).toBe(outside);
  } finally { outside.remove(); }
});


it("restores the finder trigger after opening a result replaces the project content", async () => {
  await mount(); const result = screen.getByRole("button", { name: "First result" }); result.focus(); fireEvent.click(result);
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1")); expect(document.activeElement).toBe(screen.getByRole("button", { name: "Test finder" }));
});
it("does not restore project focus while another route is already loading", async () => {
  const settings = deferred<void>(); const { client, router } = await mount(undefined, () => settings.promise);
  const layout = deferred<api.SetupDetail>(); client.removeQueries({ queryKey: queryKeys.setup("alpha", "a1") }); vi.mocked(api.getSetup).mockReturnValue(layout.promise);
  const target = screen.getByRole("button", { name: "a1" }); target.focus(); fireEvent.click(target);
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "a1", expect.any(AbortSignal)));
  let navigation!: Promise<void>; act(() => { navigation = router.navigate({ to: "/settings" }); }); await waitFor(() => expect(router.state.location.pathname).toBe("/settings"));
  await act(async () => layout.resolve(setup("a1"))); await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(document.activeElement).not.toBe(screen.getByRole("button", { name: "a1" }));
  await act(async () => { settings.resolve(); await navigation; }); await screen.findByText("Settings page");
});

it("restores a reachable tab when the focused selected layout is removed by a list refresh", async () => {
  const { client } = await mount(); screen.getByRole("button", { name: "a2" }).focus();
  await act(async () => { client.setQueryData(queryKeys.setups("alpha"), [setup("a1")]); });
  await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "a1" }));
});

it("does not restore navigation focus after the user deliberately blurs it while loading", async () => {
  const { client } = await mount(); const loading = deferred<api.SetupDetail>();
  client.removeQueries({ queryKey: queryKeys.setup("alpha", "a1") }); vi.mocked(api.getSetup).mockReturnValue(loading.promise);
  const target = screen.getByRole("button", { name: "a1" }); target.focus(); fireEvent.click(target);
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "a1", expect.any(AbortSignal))); target.blur();
  await act(async () => loading.resolve(setup("a1"))); await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(document.activeElement).toBe(document.body);
});

it("retains navigation focus when Suspense blurs a hidden old view before replacing it", async () => {
  const { client } = await mount(); const loading = deferred<api.SetupDetail>();
  client.removeQueries({ queryKey: queryKeys.setup("alpha", "a1") }); vi.mocked(api.getSetup).mockReturnValue(loading.promise);
  const target = screen.getByRole("button", { name: "a1" }); target.focus(); fireEvent.click(target);
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "a1", expect.any(AbortSignal)));
  target.checkVisibility = () => false; target.blur();
  await act(async () => loading.resolve(setup("a1"))); await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "a1" }));
});


it.each([false, true])("keeps the current layout after creation is dismissed (another layout selected: %s)", async (chooseOther) => {
  const { client } = await mount(); const created = deferred<api.SetupSummaryShort>(); vi.mocked(api.createSetup).mockReturnValue(created.promise);
  vi.mocked(api.getSetups).mockResolvedValue([setup("a1"), setup("a2"), setup("a3")]);
  fireEvent.click(screen.getByRole("button", { name: "New layout" })); fireEvent.click(screen.getByRole("button", { name: "Create blank" }));
  await waitFor(() => expect(api.createSetup).toHaveBeenCalledOnce()); fireEvent.click(screen.getByRole("button", { name: "Close creation" }));
  if (chooseOther) { fireEvent.click(screen.getByRole("button", { name: "a1" })); await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1")); }
  await act(async () => created.resolve({ ...setup("a3"), status: "draft" }));
  await waitFor(() => expect(client.getQueryData<api.SetupSummary[]>(queryKeys.setups("alpha"))?.some(item => item.id === "a3")).toBe(true));
  expect(screen.getByTestId("setup").textContent).toBe(chooseOther ? "a1" : "a2"); expect(useSimulationStore.getState().selectedSetupId).toBe(chooseOther ? "a1" : "a2");
});

it.each([false, true])("does not reactivate an old creation after its dialog is reopened (selection changed: %s)", async (chooseOther) => {
  const { client } = await mount(); const created = deferred<api.SetupSummaryShort>(); vi.mocked(api.createSetup).mockReturnValue(created.promise);
  vi.mocked(api.getSetups).mockResolvedValue([setup("a1"), setup("a2"), setup("a3")]);
  fireEvent.click(screen.getByRole("button", { name: "New layout" })); fireEvent.click(screen.getByRole("button", { name: "Create blank" }));
  await waitFor(() => expect(api.createSetup).toHaveBeenCalledOnce()); fireEvent.click(screen.getByRole("button", { name: "Close creation" }));
  if (chooseOther) fireEvent.click(screen.getByRole("button", { name: "a1" }));
  fireEvent.click(await screen.findByRole("button", { name: "New layout" }));
  await act(async () => created.resolve({ ...setup("a3"), status: "draft" }));
  await waitFor(() => expect(client.getQueryData<api.SetupSummary[]>(queryKeys.setups("alpha"))?.some(item => item.id === "a3")).toBe(true));
  expect(screen.getByTestId("setup").textContent).toBe(chooseOther ? "a1" : "a2");
});
it("keeps a route already loading while the old project and creation dialog are still mounted", async () => {
  const loading = deferred<void>(), created = deferred<api.SetupSummaryShort>(); const { client, router } = await mount(undefined, () => loading.promise);
  vi.mocked(api.createSetup).mockReturnValue(created.promise); vi.mocked(api.getSetups).mockResolvedValue([setup("a1"), setup("a2"), setup("a3")]);
  fireEvent.click(screen.getByRole("button", { name: "New layout" })); fireEvent.click(screen.getByRole("button", { name: "Create blank" })); await waitFor(() => expect(api.createSetup).toHaveBeenCalledOnce());
  let navigation!: Promise<void>; act(() => { navigation = router.navigate({ to: "/settings" }); }); await waitFor(() => expect(router.state.location.pathname).toBe("/settings"));
  expect(screen.getByRole("dialog")).toBeTruthy(); await act(async () => created.resolve({ ...setup("a3"), status: "draft" }));
  await waitFor(() => expect(client.getQueryData<api.SetupSummary[]>(queryKeys.setups("alpha"))?.some(item => item.id === "a3")).toBe(true));
  expect(screen.getByTestId("setup").textContent).toBe("a2"); expect(useSimulationStore.getState().selectedSetupId).toBe("a2");
  await act(async () => { loading.resolve(); await navigation; }); await screen.findByText("Settings page");
});
it("checks current intent after waiting for an old list query to cancel", async () => {
  const { client } = await mount(); const canceling = deferred<void>(); const cancel = vi.spyOn(client, "cancelQueries").mockReturnValueOnce(canceling.promise);
  vi.mocked(api.createSetup).mockResolvedValue({ ...setup("a3"), status: "draft" }); vi.mocked(api.getSetups).mockResolvedValue([setup("a1"), setup("a2"), setup("a3")]);
  fireEvent.click(screen.getByRole("button", { name: "New layout" })); fireEvent.click(screen.getByRole("button", { name: "Create blank" })); await waitFor(() => expect(cancel).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByRole("button", { name: "Close creation" })); fireEvent.click(screen.getByRole("button", { name: "a1" })); await waitFor(() => expect(screen.getByTestId("setup").textContent).toBe("a1"));
  await act(async () => canceling.resolve()); await waitFor(() => expect(client.getQueryData<api.SetupSummary[]>(queryKeys.setups("alpha"))?.some(item => item.id === "a3")).toBe(true));
  expect(screen.getByTestId("setup").textContent).toBe("a1");
});
