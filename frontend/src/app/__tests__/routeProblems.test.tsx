// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { NotFound, RouteError } from "../RouteError";
import { getHealth } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { LOCALES } from "@/shared/i18n/messages";
import { translate, useLocale } from "@/shared/i18n/i18n";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), getHealth: vi.fn() }));

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.restoreAllMocks(); sessionStorage.clear(); });

async function mount(path: string) {
  const root = createRootRoute({ component: () => <Outlet /> });
  const home = createRoute({ getParentRoute: () => root, path: "/", component: () => <output>Stores page</output> });
  const project = createRoute({
    getParentRoute: () => root, path: "/projects/$pid", component: () => <output>Store page</output>,
    loader: ({ params }) => {
      if (params.pid === "gone") throw new ApiError("project not found", 404);
      if (params.pid === "broken") throw new Error("disk unreadable");
      if (params.pid === "stale") throw new TypeError("Failed to fetch dynamically imported module: http://127.0.0.1:8765/assets/marketing-1a2b.js");
    },
  });
  const router = createRouter({
    routeTree: root.addChildren([home, project]), defaultErrorComponent: RouteError, defaultNotFoundComponent: NotFound,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  await router.load();
  render(<RouterProvider router={router} />);
  return router;
}

it.each(LOCALES)("explains an address that matches no page and leads back to the stores in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  const router = await mount("/no/such/page");
  expect((await screen.findByRole("alert")).textContent).toContain(translate(code, "pageNotFoundTitle"));
  fireEvent.click(screen.getByRole("button", { name: translate(code, "backToStores") }));
  await screen.findByText("Stores page");
  expect(router.state.location.pathname).toBe("/");
});

it("says a store no longer exists rather than showing the server's error", async () => {
  await mount("/projects/gone");
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("This store no longer exists");
  expect(screen.getByText("project not found").closest("details")).toBeTruthy();
});

it("keeps other failures' details one click away and can try again", async () => {
  await mount("/projects/broken");
  expect((await screen.findByRole("alert")).textContent).toContain("Something went wrong");
  expect(screen.getByText("disk unreadable").closest("details")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
});

it("does not reload into the browser's error page while the server is down, and reloads once it answers", async () => {
  vi.mocked(getHealth).mockRejectedValue(new TypeError("Failed to fetch"));
  await mount("/projects/stale");
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("The backend is not reachable");
  expect(alert.textContent).toContain("Check that it is still running, then try again.");
  expect(sessionStorage.getItem("twinstore.reloadedForUpdate")).toBeNull();
  vi.mocked(getHealth).mockResolvedValue({} as Awaited<ReturnType<typeof getHealth>>);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  // The server answers now: the page reloads to load its script.
  await waitFor(() => expect(sessionStorage.getItem("twinstore.reloadedForUpdate")).not.toBeNull());
});
