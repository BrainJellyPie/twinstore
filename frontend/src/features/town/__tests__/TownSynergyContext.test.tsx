// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { TownPage } from "../TownPage";

vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(),
  getTown: vi.fn(), getTownDemand: vi.fn(), getScenarios: vi.fn(), getTownSynergy: vi.fn(),
}));
vi.mock("../TownMap", () => ({ TownMap: ({ town }: { town: api.Town }) => <div role="img" aria-label={town.name} /> }));
vi.mock("../StorefrontCard", () => ({ StorefrontCard: () => null }));
vi.mock("../VlmSynergyDialog", () => ({ VlmSynergyDialog: ({ venue }: { venue: api.SynergyRow | null }) => venue ? <div role="dialog">{venue.name}</div> : null }));
const clients: QueryClient[] = [];
const town: api.Town = { id: "town", name: "Saved neighborhood", archetype: "residential", size_m: 800, buildings: [], venues: [], roads: [],
  source: "procedural", center_lat: null, center_lon: null, focal_venue_id: "store" };
const row: api.SynergyRow = { venue_id: "cafe", name: "Original cafe", category: "cafe", distance_m: 12, effect_on_focal_visitors: 10, effect_on_focal_pct: 0.1, role: "complement" };
const fresh: api.SynergyRow = { ...row, venue_id: "fresh", name: "Current cafe" };
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getTown).mockResolvedValue(town);
  vi.mocked(api.getTownDemand).mockImplementation(() => new Promise(() => {}));
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  vi.mocked(api.getTownSynergy).mockResolvedValue([row]);
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.resetAllMocks(); vi.restoreAllMocks(); });
async function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  client.setQueryData(queryKeys.town("alpha"), town);
  const root = createRootRoute({ component: () => <TownPage projectId="alpha" /> });
  const router = createRouter({ routeTree: root, history: createMemoryHistory({ initialEntries: ["/"] }) }); await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByRole("button", { name: "Analyze" }); return client;
}
const analyze = () => screen.getByRole("button", { name: "Analyze" });
const check = (name = row.name) => screen.queryByRole("button", { name: `Vision shopper check for ${name}` });
async function completed() { fireEvent.click(analyze()); await screen.findByRole("button", { name: `Vision shopper check for ${row.name}` }); }
async function change(client: QueryClient, kind: "day" | "town") {
  if (kind === "day") fireEvent.click(screen.getByRole("button", { name: "weekend" }));
  else {
    await act(async () => { client.setQueryData(queryKeys.town("alpha"), { ...town, name: "Updated neighborhood" }); });
    await screen.findByRole("img", { name: "Updated neighborhood" });
  }
}
it.each(["weekend", "holiday"])("hides completed weekday results after choosing %s", async day => {
  await mount(); await completed(); fireEvent.click(screen.getByRole("button", { name: day })); expect(check()).toBeNull();
});
it.each(["day", "town"] as const)("ignores an old successful analysis after the %s changes", async kind => {
  const pending = deferred<api.SynergyRow[]>(); vi.mocked(api.getTownSynergy).mockReturnValue(pending.promise);
  const client = await mount(); fireEvent.click(analyze()); await change(client, kind);
  await act(async () => pending.resolve([row])); expect(check()).toBeNull();
});
it.each(["day", "town"] as const)("ignores an old analysis error after the %s changes", async kind => {
  const pending = deferred<api.SynergyRow[]>(); vi.mocked(api.getTownSynergy).mockReturnValue(pending.promise);
  const client = await mount(); fireEvent.click(analyze()); await change(client, kind);
  await act(async () => pending.reject(new Error("Old analysis failed"))); expect(screen.queryByText("Old analysis failed")).toBeNull();
});
it("hides completed results after a background town refresh, including edits that retain its ID", async () => {
  const client = await mount(); await completed(); await change(client, "town"); expect(check()).toBeNull();
});
it.each((["day", "town"] as const).flatMap(kind => [false, true].map(failed => ({ kind, failed }))))("can analyze the new $kind without an old pending response overwriting it (failure: $failed)", async ({ kind, failed }) => {
  const pending = deferred<api.SynergyRow[]>(); vi.mocked(api.getTownSynergy).mockReturnValueOnce(pending.promise).mockResolvedValueOnce([fresh]);
  const client = await mount(); fireEvent.click(analyze()); await waitFor(() => expect((analyze() as HTMLButtonElement).disabled).toBe(true));
  await change(client, kind); expect((analyze() as HTMLButtonElement).disabled).toBe(false); fireEvent.click(analyze());
  await screen.findByRole("button", { name: `Vision shopper check for ${fresh.name}` });
  await act(async () => { if (failed) pending.reject(new Error("Obsolete failure")); else pending.resolve([row]); });
  expect(check(fresh.name)).toBeTruthy(); expect(check()).toBeNull(); expect(screen.queryByText("Obsolete failure")).toBeNull();
  expect(api.getTownSynergy).toHaveBeenLastCalledWith("alpha", kind === "day" ? "weekend" : "weekday");
});
it("shows a current analysis failure and recovers after retrying", async () => {
  vi.mocked(api.getTownSynergy).mockRejectedValueOnce(new Error("Current analysis failed")).mockResolvedValueOnce([fresh]);
  await mount(); fireEvent.click(analyze()); await screen.findByText("Current analysis failed"); fireEvent.click(analyze());
  await screen.findByRole("button", { name: `Vision shopper check for ${fresh.name}` }); expect(screen.queryByText("Current analysis failed")).toBeNull();
});
it("retains results when a background read returns the same town data", async () => {
  const client = await mount(); await completed(); await act(async () => { client.setQueryData(queryKeys.town("alpha"), structuredClone(town)); }); expect(check()).toBeTruthy();
});
it("closes the selected vision result on a day change and does not reopen it when switching back", async () => {
  const client = await mount(); await completed(); fireEvent.click(check()!); expect(screen.getByRole("dialog")).toBeTruthy();
  await change(client, "day"); expect(screen.queryByRole("dialog")).toBeNull(); fireEvent.click(screen.getByRole("button", { name: "weekday" })); expect(screen.queryByRole("dialog")).toBeNull();
});
it("closes the selected vision result when the current town changes", async () => {
  const client = await mount(); await completed(); fireEvent.click(check()!); expect(screen.getByRole("dialog")).toBeTruthy();
  await change(client, "town"); expect(screen.queryByRole("dialog")).toBeNull();
});
it("lands on the results below the button once the analysis finishes", async () => {
  await mount(); await completed();
  expect(document.activeElement).toBe(screen.getByRole("table").parentElement);
});
it("announces a failed analysis next to the button", async () => {
  vi.mocked(api.getTownSynergy).mockRejectedValueOnce(new Error("Current analysis failed"));
  await mount(); fireEvent.click(analyze());
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe("Current analysis failed");
  expect(analyze().closest("section")?.contains(alert)).toBe(true);
});
