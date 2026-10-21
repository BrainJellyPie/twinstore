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
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
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
  useLocale.getState().setLocale("en");
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getProject).mockImplementation(async (pid) => project(pid, pid === "alpha" ? ["a1", "a2"] : ["b1", "b2"]));
  vi.mocked(api.getSetup).mockImplementation(async (_pid, id) => setup(id));
  vi.mocked(api.getRuns).mockResolvedValue([]);
  vi.mocked(api.getSetupGenerations).mockResolvedValue([]);
});
afterEach(() => {
  useLocale.getState().setLocale("en");
  cleanup(); clients.splice(0).forEach((client) => client.clear());
  useSimulationStore.getState().reset(); usePlaybackControlStore.getState().reset(); useSimulationMetricsStore.getState().reset();
  vi.resetAllMocks();
  vi.restoreAllMocks();
});

function deferred<T>() {
  let reject!: (reason: Error) => void;
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

async function mount(initialLayouts?: api.SetupSummary[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  for (const [pid, ids] of [["alpha", ["a1", "a2", "a3"]], ["beta", ["b1"]]] as const) {
    client.setQueryData(queryKeys.project(pid), project(pid, [...ids]));
    for (const id of ids) { client.setQueryData(queryKeys.setup(pid, id), setup(id)); client.setQueryData(queryKeys.runs(pid, id), []); }
  }
  if (initialLayouts) client.setQueryData(queryKeys.setups("alpha"), initialLayouts);
  const root = createRootRoute({ component: Outlet });
  const route = createRoute({ getParentRoute: () => root, path: "/projects/$pid", component: Route.options.component });
  const router = createRouter({ routeTree: root.addChildren([route]), history: createMemoryHistory({ initialEntries: ["/projects/alpha"] }) });
  await router.load(); render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  return { client, router };
}

it.each(LOCALES)("explains failed layout reads and offers explicit recovery in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); vi.mocked(api.getSetups).mockRejectedValue(new Error("Layout service unavailable"));
  await mount(); const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain(translate(code, "layoutsLoadFailed")); expect(alert.textContent).toContain("Layout service unavailable");
  expect((screen.getByRole("button", { name: translate(code, "reloadLayouts") }) as HTMLButtonElement).disabled).toBe(false);
  expect(screen.queryByText("Loading layout…")).toBeNull(); expect(api.createSetup).not.toHaveBeenCalled();
});

it("shows loading during an initial retry, then opens the recovered layout", async () => {
  const next = deferred<api.SetupSummary[]>();
  vi.mocked(api.getSetups).mockRejectedValueOnce(new Error("Offline")).mockReturnValueOnce(next.promise);
  await mount(); await screen.findByRole("alert"); const retry = screen.getByRole("button", { name: "Reload layouts" }); fireEvent.click(retry);
  await screen.findByRole("status");
  expect(screen.queryByRole("button", { name: "Reload layouts" })).toBeNull();
  expect(api.getSetups).toHaveBeenCalledTimes(2);
  await act(async () => next.resolve([setup("a1")])); await screen.findByText("a1", { selector: "output" });
  expect(screen.queryByRole("alert")).toBeNull(); expect(api.createSetup).not.toHaveBeenCalled();
});

it.each(LOCALES)("lets an empty project create its first layout in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); vi.mocked(api.getSetups).mockResolvedValueOnce([]).mockResolvedValue([setup("a3")]);
  vi.mocked(api.createSetup).mockResolvedValue({ ...setup("a3"), status: "draft" }); await mount();
  await screen.findByText(translate(code, "noLayoutsFound")); expect(screen.queryByText("Loading layout…")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "newLayout") }));
  await screen.findByRole("dialog"); fireEvent.click(screen.getByRole("button", { name: "Create blank" }));
  await screen.findByText("a3", { selector: "output" });
  expect(api.createSetup).toHaveBeenCalledWith("alpha", { mode: "empty", source_setup_id: null, name: "New" });
  expect(screen.queryByText(translate(code, "noLayoutsFound"))).toBeNull();
});

it("retains a cached layout and playback state when refreshing the list fails", async () => {
  const next = deferred<api.SetupSummary[]>();
  vi.mocked(api.getSetups).mockRejectedValueOnce(new Error("Refresh offline")).mockReturnValueOnce(next.promise);
  const { client } = await mount([setup("a1")]); await screen.findByText("a1", { selector: "output" });
  act(() => { usePlaybackControlStore.getState().setSpeed(600); useSimulationMetricsStore.getState().setMetrics({ revenue: 321 }); });
  await act(async () => { await client.invalidateQueries({ queryKey: queryKeys.setups("alpha"), exact: true }); });
  await screen.findByRole("alert"); expect(screen.getByTestId("setup").textContent).toBe("a1");
  expect(usePlaybackControlStore.getState().speed).toBe(600); expect(useSimulationMetricsStore.getState().revenue).toBe(321);
  const retry = screen.getByRole("button", { name: "Reload layouts" }); fireEvent.click(retry);
  await waitFor(() => expect((retry as HTMLButtonElement).disabled).toBe(true)); fireEvent.click(retry);
  expect(api.getSetups).toHaveBeenCalledTimes(2); expect(screen.getByTestId("setup").textContent).toBe("a1");
  await act(async () => next.resolve([setup("a1"), setup("a2")])); await screen.findByRole("button", { name: "a2" });
  expect(screen.queryByRole("alert")).toBeNull(); expect(screen.getByTestId("setup").textContent).toBe("a1");
});

it("does not show an old project's late failure after navigating to another project", async () => {
  const old = deferred<api.SetupSummary[]>();
  vi.mocked(api.getSetups).mockImplementation(pid => pid === "alpha" ? old.promise : Promise.resolve([setup("b1")]));
  const { router } = await mount(); await waitFor(() => expect(api.getSetups).toHaveBeenCalledOnce());
  await act(async () => { await router.navigate({ to: "/projects/$pid", params: { pid: "beta" } }); });
  await screen.findByText("b1", { selector: "output" }); await act(async () => old.reject(new Error("Old project failed")));
  expect(screen.queryByRole("alert")).toBeNull(); expect(screen.getByTestId("project").textContent).toBe("beta");
});

it("distinguishes the first pending request from an empty or failed list", async () => {
  const pending = deferred<api.SetupSummary[]>(); vi.mocked(api.getSetups).mockReturnValue(pending.promise); await mount();
  await screen.findByRole("status"); expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.queryByRole("button", { name: "New layout" })).toBeNull(); expect(api.createSetup).not.toHaveBeenCalled();
  await act(async () => pending.resolve([setup("a1")])); await screen.findByText("a1", { selector: "output" });
});

it("recovers an empty list by reloading without creating a layout", async () => {
  vi.mocked(api.getSetups).mockResolvedValueOnce([]).mockResolvedValueOnce([setup("a1")]);
  await mount(); await screen.findByText("No layouts found.");
  fireEvent.click(screen.getByRole("button", { name: "Reload layouts" }));
  await screen.findByText("a1", { selector: "output" }); expect(api.createSetup).not.toHaveBeenCalled();
});

it("offers another explicit retry after a repeated failure", async () => {
  vi.mocked(api.getSetups).mockRejectedValueOnce(new Error("First failure")).mockRejectedValueOnce(new Error("Second failure"));
  await mount(); await screen.findByText("First failure");
  fireEvent.click(screen.getByRole("button", { name: "Reload layouts" })); await screen.findByText("Second failure");
  expect((screen.getByRole("button", { name: "Reload layouts" }) as HTMLButtonElement).disabled).toBe(false);
  expect(screen.queryByRole("status")).toBeNull(); expect(api.getSetups).toHaveBeenCalledTimes(2);
});
