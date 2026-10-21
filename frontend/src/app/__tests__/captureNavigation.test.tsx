// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useSimulationStore } from "@/stores/simulationStore";
import { webcrypto } from "node:crypto";
import { Route } from "../../routes/capture.$pid";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  listCaptures: vi.fn(), getCapture: vi.fn(), getModels: vi.fn(), getSetups: vi.fn(), getSetup: vi.fn(), getProject: vi.fn(), createCapture: vi.fn(),
}));
vi.mock("@/features/capture/ShelfLab", () => ({ BeforeAfter: () => null, ShelfLabPanel: () => null }));
vi.mock("@/features/capture/RivalCard", () => ({ RivalCard: () => null }));
const clients: QueryClient[] = [];
let captures: Record<string, string[]>;
function status(id: string): api.CaptureStatus {
  return { capture_id: id, status: "completed", stage: "done", progress: 1, error: "",
    options: { detector: "classic", model: "none", currency: "USD", rack_type: "shelf", label: "Tea" },
    image_name: id + ".png", image_size: [100, 100], created_at: "", finished_at: "", items: 0, facings: 0, gaps: 0, levels: 0, applied_setup_ids: [] };
}
const result: api.CaptureResult = { image_size: [100, 100], tilt_deg: 0, detector: "classic", detection_sources: {}, model: "none", currency: "USD",
  rack_type: "shelf", bands: [], items: [], gaps: [], dominant_category: "", notes: [], timings: {}, vlm_calls: 0, edited: false };
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  captures = { alpha: ["cap_a1", "cap_a2"], beta: ["cap_b1"] };
  vi.mocked(api.listCaptures).mockImplementation(async (pid) => captures[pid]!.map(status));
  vi.mocked(api.getCapture).mockImplementation(async (pid, id) => {
    if (!captures[pid]?.includes(id)) throw new Error("Capture does not belong to this project");
    return { status: status(id), result };
  });
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.getSetups).mockResolvedValue([]);
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach((client) => client.clear()); useSimulationStore.getState().reset();
  vi.resetAllMocks(); vi.restoreAllMocks(); vi.unstubAllGlobals();
});
async function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  for (const pid of ["alpha", "beta"]) client.setQueryData(["projects", pid], { metadata: { currency: "USD" } });
  const root = createRootRoute({ component: Outlet });
  const route = createRoute({ getParentRoute: () => root, path: "/capture/$pid", component: Route.options.component });
  const router = createRouter({ routeTree: root.addChildren([route]), history: createMemoryHistory({ initialEntries: ["/capture/alpha"] }) });
  await router.load();
  const view = render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Shelf photo" });
  const go = async () => { await act(async () => { await router.navigate({ to: "/capture/$pid", params: { pid: "beta" } }); }); };
  return { ...view, client, router, go };
}
function expectOnlyOwnedCaptures() {
  expect(vi.mocked(api.getCapture).mock.calls.filter(([pid, id]) => !captures[pid]?.includes(id))).toEqual([]);
}

it("opens the next project's photo without requesting the previous project's selected capture", async () => {
  const { go } = await mount();
  fireEvent.click(screen.getByTitle("cap_a2.png"));
  await waitFor(() => expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("/alpha/captures/cap_a2/"));
  await go();
  await waitFor(() => expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("/beta/captures/cap_b1/"));
  expectOnlyOwnedCaptures();
});

it("opens existing photos in the next project after choosing Add photos in the previous project", async () => {
  const { go } = await mount();
  fireEvent.click(screen.getByRole("button", { name: "Add photos" }));
  expect(await screen.findByText("Choose photos or drop them here")).toBeTruthy();
  await go();
  await waitFor(() => expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("/beta/captures/cap_b1/"));
  expectOnlyOwnedCaptures();
});

it("resets capture-specific editing state when a cached destination uses the same capture ID", async () => {
  captures = { alpha: ["shared"], beta: ["shared"] };
  const { go, client } = await mount();
  client.setQueryData(["projects", "beta", "captures", "shared"], { status: status("shared"), result });
  fireEvent.click(screen.getByRole("button", { name: /^Replace a rack/ }));
  expect(screen.getAllByRole("combobox")).toHaveLength(2);
  await go();
  await waitFor(() => expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("/beta/captures/shared/"));
  expect(screen.getAllByRole("combobox")).toHaveLength(1);
});

it("keeps the selected photo and Add photos mode when refreshing the same project", async () => {
  const { client } = await mount();
  fireEvent.click(screen.getByTitle("cap_a2.png"));
  await waitFor(() => expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("/alpha/captures/cap_a2/"));
  await act(async () => { client.setQueryData(["projects", "alpha", "captures"], captures.alpha!.map(status)); });
  expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("/alpha/captures/cap_a2/");
  fireEvent.click(screen.getByRole("button", { name: "Add photos" }));
  await act(async () => { client.setQueryData(["projects", "alpha", "captures"], captures.alpha!.map(status)); });
  expect(screen.getByText("Choose photos or drop them here")).toBeTruthy();
  expect(screen.queryByRole("img", { name: "Shelf photo" })).toBeNull();
});

it("does not select a late upload from the previous project in an empty destination", async () => {
  captures.beta = [];
  let finish!: (value: api.CaptureStatus) => void;
  vi.mocked(api.createCapture).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  const { go, container } = await mount();
  fireEvent.click(screen.getByRole("button", { name: "Add photos" }));
  await screen.findByText("Choose photos or drop them here");
  fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(["photo"], "shelf.png", { type: "image/png" })] } });
  await waitFor(() => expect((screen.getByRole("button", { name: "Start / resume queue" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await waitFor(() => expect(api.createCapture).toHaveBeenCalledOnce());
  await go();
  await act(async () => { finish(status("cap_uploaded_alpha")); });
  await screen.findByText("Choose photos or drop them here");
  expect(screen.queryByRole("alert")).toBeNull();
  expectOnlyOwnedCaptures();
});
