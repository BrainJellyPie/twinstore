// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserHistory, createRootRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { Route } from "../online.$pid";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getProject: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), listSites: vi.fn(), listRuns: vi.fn(), listTemplates: vi.fn() }));
vi.mock("@/features/online/BrowserView", () => ({ BrowserView: () => <p>Browsing store</p> }));
vi.mock("@/features/online/SiteDesigner", () => ({ SiteDesigner: () => <input aria-label="Unsaved design" defaultValue="" /> }));
vi.mock("@/features/online/RunLauncher", () => ({ RunLauncher: ({ compareWith }: { compareWith?: string }) => <output>Comparing {compareWith ?? "none"}</output> }));
vi.mock("@/features/online/RunReport", () => ({ RunReport: ({ runId, initialJourney }: { runId: string; initialJourney?: { shopper: string } }) => {
  const [shopper] = useState(initialJourney?.shopper ?? "none");
  return <output>Run {runId}; shopper {shopper}</output>;
} }));
const clients: QueryClient[] = [];
const histories: ReturnType<typeof createBrowserHistory>[] = [];
beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { currency: "USD" }, personas: [], setups: [] } as never);
  vi.mocked(online.listSites).mockResolvedValue(["a", "b"].map((id) => ({ id, name: `Shop ${id}`, template_id: "fashion", currency: "USD", categories: 1, products: 1, photos: 0, theme_color: "#2563eb", device: null, variant_of: "", note: "", created_at: "", updated_at: "" })));
  vi.mocked(online.listRuns).mockResolvedValue([]);
  vi.mocked(online.listTemplates).mockResolvedValue([]);
});
afterEach(() => { cleanup(); histories.splice(0).forEach((h) => h.destroy()); clients.splice(0).forEach((c) => c.clear()); vi.restoreAllMocks(); vi.resetAllMocks(); });
async function mount(search = "") {
  window.history.replaceState(null, "", `/online/p1${search}`);
  const history = createBrowserHistory({ window });
  histories.push(history);
  const root = createRootRoute({ component: Outlet });
  const route = Route.update({ getParentRoute: () => root, id: "/online/$pid", path: "/online/$pid" } as never);
  const router = createRouter({ routeTree: root.addChildren([route]), history });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  await act(async () => {
    await router.load();
    render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  });
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
  return router;
}
it("keeps the first design click open when saving the selected store in the URL", async () => {
  await mount();
  fireEvent.click(await screen.findByRole("tab", { name: "Design" }));
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
  expect(screen.getByRole("textbox", { name: "Unsaved design" })).toBeTruthy();
  expect(new URLSearchParams(window.location.search).get("site")).toBe("a");
});
it("keeps an incoming comparison after its one-time query is consumed", async () => {
  await mount("?site=a&compare=b");
  expect(screen.getByText("Comparing b")).toBeTruthy();
});
it("keeps an incoming shopper replay and still follows a subsequent routed link", async () => {
  const router = await mount("?run=r1&shopper=customer1&variant=1");
  expect(screen.getByText("Run r1; shopper customer1")).toBeTruthy();
  await act(async () => { await router.navigate({ to: "/online/$pid", params: { pid: "p1" }, search: { run: "r2", shopper: "customer2", variant: 0 } }); });
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
  expect(screen.getByText("Run r2; shopper customer2")).toBeTruthy();
  expect(new URLSearchParams(window.location.search).get("run")).toBe("r2");
  await act(async () => { await router.navigate({ to: "/online/$pid", params: { pid: "p1" }, search: { site: "b", compare: "a" }, replace: true }); });
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
  expect(screen.getByText("Comparing a")).toBeTruthy();
  expect(new URLSearchParams(window.location.search).get("site")).toBe("b");
});
