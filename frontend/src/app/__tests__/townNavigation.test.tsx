// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { Route } from "../../routes/town.$pid";

// The route component is code-split (autoCodeSplitting), so the first router.load() would import the whole page
// module graph inside a test's timeout. Load that chunk once here instead.
beforeAll(async () => { await (Route.options.component as { preload?: () => Promise<void> } | undefined)?.preload?.(); }, 120_000);

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  getTown: vi.fn(), getTownDemand: vi.fn(), getScenarios: vi.fn(), getTownSynergy: vi.fn(),
  generateTown: vi.fn(), importTownFromMap: vi.fn(), addTownVenue: vi.fn(), removeTownVenue: vi.fn(),
}));
vi.mock("@/features/town/TownMap", () => ({ TownMap: ({ town, mode, onPlace, onRemove }: {
  town: api.Town; mode: string; onPlace: (x: number, y: number) => void; onRemove: (venue: api.TownVenue) => void;
}) => <div><output data-testid="map">{town.name}:{mode}</output>
  <button onClick={() => onPlace(20, 30)}>Place on map</button>
  <button onClick={() => onRemove(town.venues[0]!)}>Remove on map</button></div> }));
vi.mock("@/features/town/StorefrontCard", () => ({ StorefrontCard: () => null }));
vi.mock("@/features/town/VlmSynergyDialog", () => ({ VlmSynergyDialog: ({ venue }: { venue: api.SynergyRow | null }) => venue ? <div role="dialog">{venue.name}</div> : null }));
const clients: QueryClient[] = [];
const towns: Record<string, api.Town> = Object.fromEntries(["alpha", "beta"].map((id) => [id, {
  id, name: `${id} neighborhood`, archetype: "residential", size_m: 800, buildings: [], roads: [], source: "procedural",
  center_lat: null, center_lon: null, focal_venue_id: "store", venues: [{ id: "store", name: `${id} store`, category: "convenience",
    x: 0, y: 0, attractiveness: 1, open_hour: 0, close_hour: 24, is_focal: true }],
}]));
const synergy: api.SynergyRow[] = [{ venue_id: "alpha_cafe", name: "Alpha cafe", category: "cafe", distance_m: 30,
  effect_on_focal_visitors: 10, effect_on_focal_pct: 2, role: "complement" }];
beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getTown).mockImplementation(async (pid) => towns[pid]!);
  vi.mocked(api.getTownDemand).mockImplementation(() => new Promise(() => {}));
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  vi.mocked(api.getTownSynergy).mockResolvedValue(synergy);
});
afterEach(() => {
  cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); vi.restoreAllMocks();
});
async function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  client.setQueryData(queryKeys.town("beta"), towns.beta);
  const root = createRootRoute({ component: Outlet });
  const route = createRoute({ getParentRoute: () => root, path: "/town/$pid", component: Route.options.component });
  const router = createRouter({ routeTree: root.addChildren([route]), history: createMemoryHistory({ initialEntries: ["/town/alpha"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await waitFor(() => expect(screen.getByTestId("map").textContent).toBe("alpha neighborhood:inspect"));
  const go = async () => { await act(async () => { await router.navigate({ to: "/town/$pid", params: { pid: "beta" } }); }); };
  return { client, go };
}

it("clears the old neighborhood analysis and vision venue when navigating to another project", async () => {
  const { go } = await mount();
  fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
  fireEvent.click(await screen.findByRole("button", { name: "Vision shopper check for Alpha cafe" }));
  expect(screen.getByRole("dialog").textContent).toBe("Alpha cafe");
  await go();
  expect(screen.getByTestId("map").textContent).toBe("beta neighborhood:inspect");
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.queryByText("Alpha cafe")).toBeNull();
});

it("starts the next neighborhood in explore mode with a fresh import form", async () => {
  const { go } = await mount();
  fireEvent.click(screen.getByRole("button", { name: "Close venue" }));
  fireEvent.change(screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul"), { target: { value: "Alpha address" } });
  await go();
  expect(screen.getByTestId("map").textContent).toBe("beta neighborhood:inspect");
  expect((screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul") as HTMLInputElement).value).toBe("");
});

it("preserves edits and analysis during refreshes of the same project", async () => {
  const { client } = await mount();
  fireEvent.click(screen.getByRole("button", { name: "Open venue" }));
  fireEvent.change(screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul"), { target: { value: "Alpha address" } });
  fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
  await screen.findByText("Alpha cafe");
  await act(async () => { client.setQueryData(queryKeys.town("alpha"), { ...towns.alpha }); });
  expect(screen.getByTestId("map").textContent).toBe("alpha neighborhood:place");
  expect((screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul") as HTMLInputElement).value).toBe("Alpha address");
  expect(screen.getByText("Alpha cafe")).toBeTruthy();
});

it.each(["generate", "import", "place", "remove"] as const)("keeps a late %s response in its originating project's cache", async (operation) => {
  const method = { generate: api.generateTown, import: api.importTownFromMap, place: api.addTownVenue, remove: api.removeTownVenue }[operation];
  let finish!: (value: api.Town) => void;
  vi.mocked(method).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  const { go, client } = await mount();
  if (operation === "import") {
    fireEvent.change(screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul"), { target: { value: "Alpha address" } });
  }
  const button = { generate: "Regenerate", import: "Import buildings, shops and roads", place: "Place on map", remove: "Remove on map" }[operation];
  fireEvent.click(screen.getByRole("button", { name: button }));
  // Replacing the current neighborhood asks first.
  if (operation === "generate" || operation === "import") fireEvent.click(screen.getByRole("button", { name: "Replace the current neighborhood?" }));
  await waitFor(() => expect(method).toHaveBeenCalledOnce());
  expect(vi.mocked(method).mock.calls[0]![0]).toBe("alpha");
  await go();
  const updated = { ...towns.alpha!, name: "Alpha updated after leaving" };
  await act(async () => { finish(updated); });
  expect(client.getQueryData(queryKeys.town("beta"))).toEqual(towns.beta);
  await waitFor(() => expect(client.getQueryData(queryKeys.town("alpha"))).toEqual(updated));
  expect(screen.getByTestId("map").textContent).toBe("beta neighborhood:inspect");
});

it("ignores analysis that finishes after leaving its project", async () => {
  let finish!: (value: api.SynergyRow[]) => void;
  vi.mocked(api.getTownSynergy).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  const { go } = await mount();
  fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
  await waitFor(() => expect(api.getTownSynergy).toHaveBeenCalledOnce());
  await go();
  await act(async () => { finish(synergy); });
  expect(screen.queryByText("Alpha cafe")).toBeNull();
});
