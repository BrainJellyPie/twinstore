// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { NotFound, RouteError } from "../RouteError";
import { ApiError } from "@/shared/api/errors";
import { LOCALES } from "@/shared/i18n/messages";
import { translate, useLocale } from "@/shared/i18n/i18n";

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.restoreAllMocks(); });

async function mount(path: string) {
  const root = createRootRoute({ component: () => <Outlet /> });
  const home = createRoute({ getParentRoute: () => root, path: "/", component: () => <output>Stores page</output> });
  const project = createRoute({
    getParentRoute: () => root, path: "/projects/$pid", component: () => <output>Store page</output>,
    loader: ({ params }) => {
      if (params.pid === "gone") throw new ApiError("project not found", 404);
      if (params.pid === "broken") throw new Error("disk unreadable");
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
