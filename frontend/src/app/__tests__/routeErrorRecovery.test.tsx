// @vitest-environment jsdom
import { Suspense } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, QueryErrorResetBoundary, useSuspenseQuery } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Link, Outlet, RouterProvider, useLocation, useParams } from "@tanstack/react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RouteErrorBoundary } from "../providers/RouteErrorBoundary";
import { LOCALES } from "@/shared/i18n/messages";
import { translate, useLocale } from "@/shared/i18n/i18n";

const read = vi.fn<(resource: string) => Promise<string>>();
const clients: QueryClient[] = [];
beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  read.mockImplementation(async key => { if (key === "alpha") throw new Error("Server failure alpha"); return `Loaded ${key}`; });
});
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); useLocale.getState().setLocale("en"); vi.restoreAllMocks(); vi.resetAllMocks(); });

function Page({ home = false }: { home?: boolean }) {
  const params = useParams({ strict: false }) as { pid?: string };
  const search = useLocation({ select: location => location.searchStr });
  const key = home ? "home" : `${params.pid}${search}`;
  const { data } = useSuspenseQuery({ queryKey: ["resource", key], queryFn: () => read(key) });
  return <output>{data}</output>;
}
function Root() {
  return <><nav><Link to="/">Global home</Link><Link to="/projects/$pid" params={{ pid: "beta" }}>Global beta</Link><Link to="/settings">Global settings</Link></nav>
    <QueryErrorResetBoundary><RouteErrorBoundary><Suspense fallback={<p role="status">Loading resource</p>}><Outlet /></Suspense></RouteErrorBoundary></QueryErrorResetBoundary></>;
}
async function mount(path = "/projects/alpha", loader?: () => Promise<void>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  const root = createRootRoute({ component: Root });
  const home = createRoute({ getParentRoute: () => root, path: "/", component: () => <Page home /> });
  const project = createRoute({ getParentRoute: () => root, path: "/projects/$pid", component: Page });
  const settings = createRoute({ getParentRoute: () => root, path: "/settings", loader, component: () => <output>Settings loaded</output> });
  const router = createRouter({ routeTree: root.addChildren([home, project, settings]), defaultPendingMs: 60_000, history: createMemoryHistory({ initialEntries: [path] }) });
  await router.load(); render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

it.each(["Global home", "Global beta"])("clears a failed page after using %s", async label => {
  await mount(); await screen.findByText("Server failure alpha"); fireEvent.click(screen.getByRole("link", { name: label }));
  await screen.findByText(label === "Global home" ? "Loaded home" : "Loaded beta", { selector: "output" });
  expect(screen.queryByText("Server failure alpha")).toBeNull(); expect(read.mock.calls.filter(([key]) => key === "alpha")).toHaveLength(1);
});

it.each(LOCALES)("localizes recovery controls and retries the current query in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); const router = await mount(); await screen.findByText("Server failure alpha");
  expect(screen.getByRole("alert").textContent).toContain(translate(code, "routeErrorTitle"));
  expect(screen.getByRole("button", { name: translate(code, "backToStores") })).toBeTruthy();
  read.mockResolvedValue("Recovered alpha"); fireEvent.click(screen.getByRole("button", { name: translate(code, "tryAgain") }));
  await screen.findByText("Recovered alpha", { selector: "output" }); expect(router.state.location.pathname).toBe("/projects/alpha"); expect(read).toHaveBeenCalledTimes(2);
});

it("waits for a pending destination before discarding the old page error", async () => {
  let release!: () => void; const pending = new Promise<void>(resolve => { release = resolve; });
  const router = await mount("/projects/alpha", () => pending); await screen.findByText("Server failure alpha");
  fireEvent.click(screen.getByRole("link", { name: "Global settings" })); await waitFor(() => expect(router.state.location.pathname).toBe("/settings"));
  expect(screen.getByText("Server failure alpha")).toBeTruthy(); expect(read).toHaveBeenCalledOnce();
  await act(async () => release()); await screen.findByText("Settings loaded", { selector: "output" }); expect(screen.queryByText("Server failure alpha")).toBeNull(); expect(read).toHaveBeenCalledOnce();
});

it("recovers when navigation changes the search on the same path", async () => {
  const router = await mount(); await screen.findByText("Server failure alpha");
  act(() => { router.history.push("/projects/alpha?recover=1"); });
  await screen.findByText("Loaded alpha?recover=1", { selector: "output" }); expect(screen.queryByText("Server failure alpha")).toBeNull();
});

it("shows the destination's own failure and lets it retry", async () => {
  read.mockImplementation(async key => { throw new Error(`Server failure ${key}`); });
  await mount(); await screen.findByText("Server failure alpha"); fireEvent.click(screen.getByRole("link", { name: "Global beta" }));
  await screen.findByText("Server failure beta"); expect(screen.queryByText("Server failure alpha")).toBeNull();
  read.mockResolvedValue("Recovered beta"); fireEvent.click(screen.getByRole("button", { name: "Try again" })); await screen.findByText("Recovered beta", { selector: "output" });
});

it("keeps the failed page while changing display language without retrying it", async () => {
  await mount(); await screen.findByText("Server failure alpha"); act(() => useLocale.getState().setLocale("ko"));
  expect(screen.getByRole("alert").textContent).toContain(translate("ko", "routeErrorTitle")); expect(read).toHaveBeenCalledOnce();
});

it("lets Back to stores retry when the store list itself failed", async () => {
  read.mockRejectedValueOnce(new Error("Store list unavailable")).mockResolvedValue("Recovered home");
  const router = await mount("/"); await screen.findByText("Store list unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Back to stores" })); await screen.findByText("Recovered home", { selector: "output" }); expect(router.state.location.pathname).toBe("/");
});
