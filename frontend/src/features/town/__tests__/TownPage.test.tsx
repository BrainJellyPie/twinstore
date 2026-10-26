// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { TownPage } from "../TownPage";
import { useAssistStore } from "@/stores/assistStore";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getTown: vi.fn(), getTownDemand: vi.fn(), getScenarios: vi.fn(),
  generateTown: vi.fn(), importTownFromMap: vi.fn(), describeTown: vi.fn(),
}));
vi.mock("../TownMap", () => ({ TownMap: ({ town }: { town: api.Town }) => <div role="img" aria-label={town.name} /> }));
vi.mock("../StorefrontCard", () => ({ StorefrontCard: () => null }));
vi.mock("../VlmSynergyDialog", () => ({ VlmSynergyDialog: () => null }));
const clients: QueryClient[] = [];
const town: api.Town = { id: "town", name: "Saved neighborhood", archetype: "residential", size_m: 800, buildings: [], venues: [], roads: [],
  source: "procedural", center_lat: null, center_lon: null, focal_venue_id: "store" };
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getTownDemand).mockImplementation(() => new Promise(() => {}));
  vi.mocked(api.getScenarios).mockResolvedValue([]);
});
afterEach(() => { useAssistStore.setState({ pending: null }); cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); vi.restoreAllMocks(); });
async function mount(cached?: api.Town) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  if (cached) client.setQueryData(queryKeys.town("alpha"), cached);
  const root = createRootRoute({ component: () => <TownPage projectId="alpha" /> });
  const router = createRouter({ routeTree: root, history: createMemoryHistory({ initialEntries: ["/"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByRole("link", { name: "Back to store" });
  return client;
}

it("does not offer to create or import a neighborhood before the existing town finishes loading", async () => {
  const pending = deferred<api.Town | null>();
  vi.mocked(api.getTown).mockReturnValue(pending.promise);
  await mount();
  expect(screen.queryByText("Generate a neighborhood")).toBeNull();
  expect(screen.queryByText("Real map (OpenStreetMap)")).toBeNull();
  await act(async () => { pending.resolve(null); });
  expect(await screen.findByRole("button", { name: "Generate" })).toBeTruthy();
});

it("shows the load failure and retry instead of treating an unreadable town as empty", async () => {
  vi.mocked(api.getTown).mockRejectedValue(new Error("Neighborhood unavailable"));
  await mount();
  expect((await screen.findByRole("alert")).textContent).toContain("Neighborhood unavailable");
  expect(screen.queryByText("Place the store in its neighborhood")).toBeNull();
  expect(screen.queryByText("Generate a neighborhood")).toBeNull();
  expect(screen.queryByText("Real map (OpenStreetMap)")).toBeNull();
  expect((screen.getByRole("button", { name: "Retry" }) as HTMLButtonElement).disabled).toBe(false);
});

it("recovers a saved neighborhood after retrying a failed initial request", async () => {
  vi.mocked(api.getTown).mockRejectedValueOnce(new Error("Temporary failure")).mockResolvedValueOnce(town);
  await mount();
  fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("img", { name: town.name })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(api.getTown).toHaveBeenCalledTimes(2);
  expect(api.generateTown).not.toHaveBeenCalled();
  expect(api.importTownFromMap).not.toHaveBeenCalled();
});

it("keeps a failed retry visible and allows another attempt", async () => {
  vi.mocked(api.getTown).mockRejectedValueOnce(new Error("First failure")).mockRejectedValueOnce(new Error("Still unavailable")).mockResolvedValueOnce(null);
  await mount();
  fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Still unavailable"));
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("button", { name: "Generate" })).toBeTruthy();
  expect(api.getTown).toHaveBeenCalledTimes(3);
});

it("preserves cached town data and form edits when background refresh fails, then disables duplicate retries", async () => {
  const client = await mount(town);
  fireEvent.change(screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul"), { target: { value: "Keep this address" } });
  vi.mocked(api.getTown).mockRejectedValueOnce(new Error("Offline"));
  await act(async () => { await client.refetchQueries({ queryKey: queryKeys.town("alpha"), exact: true }); });
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByRole("img", { name: town.name })).toBeTruthy();
  const pending = deferred<api.Town | null>(); vi.mocked(api.getTown).mockReturnValueOnce(pending.promise);
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Retry" }) as HTMLButtonElement).disabled).toBe(true));
  expect((screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul") as HTMLInputElement).value).toBe("Keep this address");
  await act(async () => { pending.resolve({ ...town, name: "Refreshed neighborhood" }); });
  expect(await screen.findByRole("img", { name: "Refreshed neighborhood" })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect((screen.getByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul") as HTMLInputElement).value).toBe("Keep this address");
});

it("shows the creation controls for a successfully loaded empty neighborhood", async () => {
  await mount();
  expect(await screen.findByRole("button", { name: "Generate" })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
});

const demand: api.TownDemand = { focal_venue_id: "store", day_type: "weekday", total_daily_visitors: 137, direct_visitors: 100,
  linked_visitors: 37, hourly_totals: Array(24).fill(0), segment_totals: {}, origin_shares: [], linked_trips: [], store_shares: [],
  market_share: 0.1, catchment_radius_50_m: 50, catchment_radius_80_m: 100, avg_walk_distance_m: 80 };

it("shows a demand failure instead of estimating forever, then recovers on retry", async () => {
  vi.mocked(api.getTown).mockResolvedValue(town);
  vi.mocked(api.getTownDemand).mockRejectedValueOnce(new Error("Demand unavailable")).mockResolvedValueOnce(demand);
  await mount();
  expect((await screen.findByRole("alert")).textContent).toContain("Demand unavailable");
  expect(screen.queryByText("Estimating…")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry estimate" }));
  expect(await screen.findByText("137", { exact: true })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(api.getTownDemand).toHaveBeenCalledTimes(2);
});

it("clears the previous demand failure when changing the day type", async () => {
  vi.mocked(api.getTown).mockResolvedValue(town);
  vi.mocked(api.getTownDemand).mockImplementation(async (_pid, day) => {
    if (day === "weekday") throw new Error("Weekday estimate unavailable");
    return { ...demand, day_type: day };
  });
  await mount(); await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Weekend" }));
  expect(await screen.findByText("137", { exact: true })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(api.getTownDemand).toHaveBeenLastCalledWith("alpha", "weekend", null, expect.any(AbortSignal));
  // The chosen day and map tool are announced, not shown by color alone.
  expect(screen.getByRole("button", { name: "Weekend", pressed: true })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Weekday", pressed: false })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Explore", pressed: true })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Open venue" }));
  expect(screen.getByRole("button", { name: "Explore", pressed: false })).toBeTruthy();
});

it("keeps cached estimates visible after a refresh failure and prevents duplicate retries", async () => {
  vi.mocked(api.getTown).mockResolvedValue(town);
  vi.mocked(api.getTownDemand).mockResolvedValueOnce(demand);
  const client = await mount(); await screen.findByText("137", { exact: true });
  vi.mocked(api.getTownDemand).mockRejectedValueOnce(new Error("Estimate refresh unavailable"));
  await act(async () => { await client.refetchQueries({ queryKey: queryKeys.townDemand("alpha", "weekday", null) }); });
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByText("137", { exact: true })).toBeTruthy();
  const pending = deferred<api.TownDemand>(); vi.mocked(api.getTownDemand).mockReturnValueOnce(pending.promise);
  fireEvent.click(screen.getByRole("button", { name: "Retry estimate" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Retry estimate" }) as HTMLButtonElement).disabled).toBe(true));
  await act(async () => { pending.resolve({ ...demand, total_daily_visitors: 211 }); });
  expect(await screen.findByText("211", { exact: true })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("shows estimating only while a first estimate is actually pending", async () => {
  vi.mocked(api.getTown).mockResolvedValue(town);
  const pending = deferred<api.TownDemand>(); vi.mocked(api.getTownDemand).mockReturnValue(pending.promise);
  await mount();
  expect(await screen.findByText("Estimating…")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  await act(async () => { pending.resolve(demand); });
  expect(await screen.findByText("137", { exact: true })).toBeTruthy();
  expect(screen.queryByText("Estimating…")).toBeNull();
});


it("sets up the generator from a description and generates only on request", async () => {
  vi.mocked(api.describeTown).mockResolvedValue({ rationale: "A dense student street with rivals.", spec: {
    archetype: "university", size_m: 650, density: 0.8, n_competitors: 2, neighbor_categories: ["cafe", "bank"], seed: 1, name: "Campus" } });
  vi.mocked(api.generateTown).mockResolvedValue(town);
  await mount();
  fireEvent.change(await screen.findByLabelText("Describe the area"), { target: { value: "A busy campus street with two rival stores" } });
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
  expect(await screen.findByText(/A dense student street with rivals\. Check the settings, then generate\./)).toBeTruthy();
  expect(api.describeTown).toHaveBeenCalledWith("alpha", { text: "A busy campus street with two rival stores", seed: 1 });
  expect(api.generateTown).not.toHaveBeenCalled();
  expect((screen.getByLabelText("Archetype") as HTMLSelectElement).value).toBe("university");
  expect(screen.getByRole("button", { name: "Bank", pressed: true })).toBeTruthy();  // a neighbor outside the usual chips still shows
  fireEvent.click(screen.getByRole("button", { name: "Generate" }));
  await waitFor(() => expect(api.generateTown).toHaveBeenCalledWith("alpha", expect.objectContaining({ archetype: "university", n_competitors: 2 })));
});

it("opens the generator and sets it up from an area described in the command palette", async () => {
  vi.mocked(api.describeTown).mockResolvedValue({ rationale: "Offices and lunch traffic.", spec: {
    archetype: "business_district", size_m: 700, density: 0.7, n_competitors: 1, neighbor_categories: ["cafe"], seed: 1, name: "Offices" } });
  useAssistStore.getState().send({ projectId: "alpha", destination: "area", text: "An office district with one rival and lunch crowds" });
  await mount(town);
  await waitFor(() => expect(api.describeTown).toHaveBeenCalledWith("alpha", { text: "An office district with one rival and lunch crowds", seed: 1 }));
  expect((screen.getByLabelText("Describe the area") as HTMLTextAreaElement).value).toBe("An office district with one rival and lunch crowds");
  expect(await screen.findByText(/Offices and lunch traffic\./)).toBeTruthy();
  expect((screen.getByLabelText("Describe the area").closest("details") as HTMLDetailsElement).open).toBe(true);
  expect(api.generateTown).not.toHaveBeenCalled();
});

it("asks before a new neighborhood replaces the current one, and replaces it on the second click", async () => {
  vi.mocked(api.getTown).mockResolvedValue(town);
  vi.mocked(api.generateTown).mockResolvedValue({ ...town, name: "Fresh neighborhood" });
  await mount();
  fireEvent.click(await screen.findByRole("button", { name: "Regenerate" }));
  expect(api.generateTown).not.toHaveBeenCalled();
  expect(screen.getByRole("status").textContent).toContain("storefront ratings on the current map are lost");
  fireEvent.click(screen.getByRole("button", { name: "Replace the current neighborhood?" }));
  await waitFor(() => expect(api.generateTown).toHaveBeenCalledOnce());
});

it("asks before a map import replaces the current neighborhood; leaving the button cancels", async () => {
  vi.mocked(api.getTown).mockResolvedValue(town);
  vi.mocked(api.importTownFromMap).mockResolvedValue({ ...town, name: "Imported" });
  await mount();
  fireEvent.change(await screen.findByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul"), { target: { value: "Seoul" } });
  const importButton = screen.getByRole("button", { name: "Import buildings, shops and roads" });
  fireEvent.click(importButton);
  fireEvent.blur(screen.getByRole("button", { name: "Replace the current neighborhood?" }));
  expect(screen.getByRole("button", { name: "Import buildings, shops and roads" })).toBeTruthy();
  expect(api.importTownFromMap).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Import buildings, shops and roads" }));
  fireEvent.click(screen.getByRole("button", { name: "Replace the current neighborhood?" }));
  await waitFor(() => expect(api.importTownFromMap).toHaveBeenCalledWith("alpha", { address: "Seoul", radius_m: 600 }));
});

it("creates the first neighborhood without asking", async () => {
  vi.mocked(api.generateTown).mockResolvedValue(town);
  await mount();
  fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
  await waitFor(() => expect(api.generateTown).toHaveBeenCalledOnce());
});

it.each([["2.5", 2], ["-4", 0], ["75", 60], ["", null]])("sends rivals typed as %j as a count the server accepts", async (typed, sent) => {
  vi.mocked(api.generateTown).mockResolvedValue(town);
  await mount();
  fireEvent.change(await screen.findByRole("spinbutton", { name: "Rivals" }), { target: { value: typed } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Seed" }), { target: { value: "3.7" } });
  fireEvent.click(screen.getByRole("button", { name: "Generate" }));
  await waitFor(() => expect(api.generateTown).toHaveBeenCalledWith("alpha", expect.objectContaining({ n_competitors: sent, seed: 3 })));
});

it("says once that no visitors are expected instead of showing zero distances and walks", async () => {
  vi.mocked(api.getTown).mockResolvedValue(town);
  vi.mocked(api.getTownDemand).mockImplementation(async (_pid, day) => day === "weekend"
    ? { ...demand, day_type: day, total_daily_visitors: 0, direct_visitors: 0, linked_visitors: 0, hourly_totals: Array(24).fill(0),
        catchment_radius_50_m: 0, catchment_radius_80_m: 0, avg_walk_distance_m: 0, market_share: 0 }
    : demand);
  await mount();
  expect(await screen.findByText("137", { exact: true })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Weekend" }));
  expect((await screen.findByText(/No visitors are expected on a weekend/)).getAttribute("role")).toBe("status");
  expect(screen.queryByText("0 m")).toBeNull();
});

it("says what a slow map import is doing, with the time it has taken", async () => {
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.importTownFromMap).mockImplementation(() => new Promise(() => {}));
  await mount();
  fireEvent.change(await screen.findByPlaceholderText("Address, e.g. 84 Heukseok-ro, Seoul"), { target: { value: "Seoul" } });
  vi.useFakeTimers();
  try {
    fireEvent.click(screen.getByRole("button", { name: "Import buildings, shops and roads" }));
    expect(screen.getByText("Downloading buildings, shops and roads…")).toBeTruthy();
    await act(async () => { vi.advanceTimersByTime(20_000); });
    expect(screen.getByText(/Busy map servers can take a few minutes/)).toBeTruthy();
    expect(screen.getByText("(20 s)")).toBeTruthy();
  } finally {
    vi.useRealTimers();
  }
});

it("says the area's size is its side length, not a radius", async () => {
  vi.mocked(api.getTown).mockResolvedValue({ ...town, size_m: 1200, source: "osm" });
  await mount();
  await screen.findByRole("img", { name: "Saved neighborhood" });
  expect(document.body.textContent).toContain("1,200 m across · OpenStreetMap");
});
