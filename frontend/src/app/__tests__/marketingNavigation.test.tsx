// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as marketing from "@/shared/api/marketing";
import { queryKeys } from "@/shared/queries/keys";
import { Route } from "../../routes/marketing.$pid";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getProject: vi.fn(), getSetup: vi.fn(), listPackages: vi.fn(),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), getMarketingInfo: vi.fn(), listExperiments: vi.fn(), getExperiment: vi.fn(),
  listSurveys: vi.fn(), listPitches: vi.fn(), listShelfTests: vi.fn(), listConjoints: vi.fn(), deleteExperiment: vi.fn(),
}));
const clients: QueryClient[] = [];
let projects: Record<string, api.ProjectDetail>;
const jobs: Record<string, string[]> = { alpha: ["exp_a1", "exp_a2"], beta: ["exp_b1"] };
function setup(id: string): api.SetupDetail {
  return { id, name: id, status: "draft", parentId: null, runId: null, memo: "", readiness: null, created_at: "", updated_at: "", store: null };
}
function job(id: string): marketing.JobStatus {
  return { job_id: id, kind: "experiment", name: id, status: "failed", error: "", stage: "", progress: 0, created_at: "", finished_at: "" };
}
beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  projects = Object.fromEntries(["alpha", "beta"].map((pid) => [pid, { projectId: pid,
    metadata: { project_id: pid, name: pid, description: "", store_type: "convenience", currency: "USD", grid_size: null,
      weekly_schedule: [], address: "", customer_profile: "", supplemental_summary: "", created_at: "", updated_at: "" },
    personas: [], state: { activeSetupId: `${pid}_1`, runningSetups: [] }, setups: [setup(`${pid}_1`), setup(`${pid}_2`)], personasLocked: false,
  }]));
  vi.mocked(api.getProject).mockImplementation(async (pid) => projects[pid]!);
  vi.mocked(api.getSetup).mockImplementation(async (pid, sid) => {
    if (!projects[pid]!.setups.some((s) => s.id === sid)) throw new Error("Layout does not belong to project");
    return setup(sid);
  });
  vi.mocked(api.listPackages).mockResolvedValue([]);
  vi.mocked(marketing.getMarketingInfo).mockResolvedValue({ currency: "USD" });
  vi.mocked(marketing.listExperiments).mockImplementation(async (pid) => jobs[pid]!.map(job));
  vi.mocked(marketing.getExperiment).mockImplementation(async (pid, id) => {
    if (!jobs[pid]?.includes(id)) throw new Error("Job does not belong to project");
    return { ...job(id), error: `Loaded ${pid}/${id}`, report: null };
  });
  for (const fn of [marketing.listSurveys, marketing.listPitches, marketing.listShelfTests, marketing.listConjoints]) vi.mocked(fn).mockResolvedValue([]);
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); vi.restoreAllMocks(); });
async function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  for (const pid of ["alpha", "beta"]) client.setQueryData(queryKeys.project(pid), projects[pid]);
  const root = createRootRoute({ component: Outlet });
  const route = createRoute({ getParentRoute: () => root, path: "/marketing/$pid", component: Route.options.component });
  const router = createRouter({ routeTree: root.addChildren([route]), history: createMemoryHistory({ initialEntries: ["/marketing/alpha"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByText("Loaded alpha/exp_a1");
  const go = async () => { await act(async () => { await router.navigate({ to: "/marketing/$pid", params: { pid: "beta" } }); }); };
  return { client, go };
}
function expectOwnedRequests() {
  expect(vi.mocked(api.getSetup).mock.calls.filter(([pid, id]) => !projects[pid]!.setups.some((s) => s.id === id))).toEqual([]);
  expect(vi.mocked(marketing.getExperiment).mock.calls.filter(([pid, id]) => !jobs[pid]!.includes(id))).toEqual([]);
}

it("opens the new project's latest job without requesting the previous selected job", async () => {
  const { go } = await mount();
  fireEvent.click(screen.getByRole("button", { name: /^exp_a2/ }));
  await screen.findByText("Loaded alpha/exp_a2");
  await go();
  await screen.findByText("Loaded beta/exp_b1");
  expectOwnedRequests();
}, 15_000);

it("selects the destination layout after choosing a layout in the previous project", async () => {
  const { go } = await mount();
  fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), { target: { value: "alpha_2" } });
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_2", expect.any(AbortSignal)));
  await go();
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Layout" }) as HTMLSelectElement).value).toBe("beta_1"));
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("beta", "beta_1", expect.any(AbortSignal)));
  expectOwnedRequests();
});

it("does not request a previous layout in a destination with no layouts", async () => {
  projects.beta!.state.activeSetupId = ""; projects.beta!.setups = [];
  const { go } = await mount();
  fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), { target: { value: "alpha_2" } });
  await go();
  await screen.findByText("Loaded beta/exp_b1");
  expect(vi.mocked(api.getSetup).mock.calls.filter(([pid]) => pid === "beta")).toEqual([]);
  expectOwnedRequests();
});

it("opens existing destination jobs after selecting New test in the previous project", async () => {
  const { go } = await mount();
  fireEvent.click(screen.getByRole("button", { name: "New A/B test" }));
  expect(screen.queryByText("Loaded alpha/exp_a1")).toBeNull();
  await go();
  await screen.findByText("Loaded beta/exp_b1");
  expectOwnedRequests();
});

it("preserves the chosen job and layout during a same-project refresh", async () => {
  const { client } = await mount();
  fireEvent.click(screen.getByRole("button", { name: /^exp_a2/ }));
  await screen.findByText("Loaded alpha/exp_a2");
  fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), { target: { value: "alpha_2" } });
  await act(async () => {
    client.setQueryData(queryKeys.project("alpha"), { ...projects.alpha });
    client.setQueryData(marketing.marketingKeys.experiments("alpha"), jobs.alpha!.map(job));
  });
  expect(screen.getByText("Loaded alpha/exp_a2")).toBeTruthy();
  expect((screen.getByRole("combobox", { name: "Layout" }) as HTMLSelectElement).value).toBe("alpha_2");
});

it("falls back to an owned layout when the saved active layout no longer exists", async () => {
  projects.alpha!.state.activeSetupId = "removed_layout";
  await mount();
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_1", expect.any(AbortSignal)));
  expectOwnedRequests();
});

it("does not load a stale active layout when the project has no layouts", async () => {
  projects.alpha!.setups = [];
  await mount();
  expect(vi.mocked(api.getSetup).mock.calls.filter(([pid]) => pid === "alpha")).toEqual([]);
});

it("loads the current layout after a refresh removes the explicitly selected layout", async () => {
  const { client } = await mount();
  fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), { target: { value: "alpha_2" } });
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_2", expect.any(AbortSignal)));
  projects.alpha = { ...projects.alpha!, state: { activeSetupId: "alpha_3", runningSetups: [] }, setups: [setup("alpha_3")] };
  await act(async () => { client.setQueryData(queryKeys.project("alpha"), projects.alpha); });
  await waitFor(() => expect(screen.queryByRole("option", { name: "alpha_2" })).toBeNull());
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_3", expect.any(AbortSignal)));
});

it("keeps a valid explicit choice when another session changes the saved active layout", async () => {
  const { client } = await mount();
  fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), { target: { value: "alpha_2" } });
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_2", expect.any(AbortSignal)));
  vi.mocked(api.getSetup).mockClear();
  projects.alpha = { ...projects.alpha!, state: { activeSetupId: "alpha_3", runningSetups: [] }, setups: [...projects.alpha!.setups, setup("alpha_3")] };
  await act(async () => { client.setQueryData(queryKeys.project("alpha"), projects.alpha); });
  expect((screen.getByRole("combobox", { name: "Layout" }) as HTMLSelectElement).value).toBe("alpha_2");
  expect(api.getSetup).not.toHaveBeenCalled();
});

it("prefers a valid saved active layout over the first owned layout", async () => {
  projects.alpha!.state.activeSetupId = "alpha_2";
  await mount();
  expect((screen.getByRole("combobox", { name: "Layout" }) as HTMLSelectElement).value).toBe("alpha_2");
  expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_2", expect.any(AbortSignal));
  expectOwnedRequests();
});

it.each(["removed_layout", ""])("falls back to the first remaining layout after both choices disappear (%s)", async (activeSetupId) => {
  const { client } = await mount();
  fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), { target: { value: "alpha_2" } });
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_2", expect.any(AbortSignal)));
  vi.mocked(api.getSetup).mockClear();
  projects.alpha = { ...projects.alpha!, state: { activeSetupId, runningSetups: [] }, setups: [setup("alpha_3")] };
  await act(async () => { client.setQueryData(queryKeys.project("alpha"), projects.alpha); });
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_3", expect.any(AbortSignal)));
  expect((screen.getByRole("combobox", { name: "Layout" }) as HTMLSelectElement).value).toBe("alpha_3");
  expectOwnedRequests();
});

it("clears the selection without another layout request when a refresh removes every layout", async () => {
  const { client } = await mount();
  fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), { target: { value: "alpha_2" } });
  await waitFor(() => expect(api.getSetup).toHaveBeenCalledWith("alpha", "alpha_2", expect.any(AbortSignal)));
  vi.mocked(api.getSetup).mockClear();
  projects.alpha = { ...projects.alpha!, setups: [] };
  await act(async () => { client.setQueryData(queryKeys.project("alpha"), projects.alpha); });
  await waitFor(() => expect(screen.queryByRole("option", { name: "alpha_2" })).toBeNull());
  expect((screen.getByRole("combobox", { name: "Layout" }) as HTMLSelectElement).value).toBe("");
  expect(api.getSetup).not.toHaveBeenCalled();
});

it("opens price checks in Market and resets the draft on project navigation", async () => {
  const { go } = await mount();
  fireEvent.click(screen.getByRole("tab", { name: /Price checks/ }));
  await screen.findByRole("region", { name: "Shelf and checkout price checks" });
  fireEvent.change(screen.getByLabelText("Store reference"), { target: { value: "alpha-store" } });
  await go();
  fireEvent.click(screen.getByRole("tab", { name: /Price checks/ }));
  expect((await screen.findByLabelText("Store reference") as HTMLInputElement).value).toBe("");
  expectOwnedRequests();
});
