// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { useLocale } from "@/shared/i18n/i18n";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getProject: vi.fn() }));
vi.mock("@/app/CommandBar", () => ({ CommandBar: () => null }));
vi.mock("@/app/CommandPalette", () => ({ CommandPalette: () => null }));
vi.mock("@/app/ModelSetupBanner", () => ({ ModelSetupBanner: () => null }));
vi.mock("@/app/AppBackdrop", () => ({ AppBackdrop: () => null }));
vi.mock("@/app/QuitTwinStore", () => ({ TabCloseNotice: () => null }));
vi.mock("@/app/RunNotice", () => ({ RunNotice: () => null }));

const { Route: root } = await import("../__root");
const clients: QueryClient[] = [];
beforeEach(() => { useLocale.getState().setLocale("en"); vi.spyOn(window, "scrollTo").mockImplementation(() => {}); });
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.restoreAllMocks(); vi.resetAllMocks(); });

async function mount(path: string) {
  const online = createRoute({ getParentRoute: () => root, path: "/online/$pid", component: () => <output>Online page</output> });
  const settings = createRoute({ getParentRoute: () => root, path: "/settings", component: () => <output>Settings page</output> });
  const router = createRouter({ routeTree: root.addChildren([online, settings]), history: createMemoryHistory({ initialEntries: [path] }) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

it("shows a deleted store's page as missing instead of an empty page", async () => {
  vi.mocked(api.getProject).mockRejectedValue(new ApiError("project not found", 404));
  await mount("/online/gone");
  expect((await screen.findByRole("alert")).textContent).toContain("This store no longer exists");
  expect(screen.queryByText("Online page")).toBeNull();
});

it("shows the page of a store that exists, and other pages without asking for a store", async () => {
  vi.mocked(api.getProject).mockResolvedValue({ project_id: "p1" } as unknown as Awaited<ReturnType<typeof api.getProject>>);
  await mount("/online/p1");
  expect(await screen.findByText("Online page")).toBeTruthy();
  cleanup();
  await mount("/settings");
  expect(await screen.findByText("Settings page")).toBeTruthy();
  expect(api.getProject).toHaveBeenCalledOnce();
});

it("keeps the page when the store cannot be read for another reason", async () => {
  vi.mocked(api.getProject).mockRejectedValue(new ApiError("server busy", 503));
  await mount("/online/p1");
  expect(await screen.findByText("Online page")).toBeTruthy();
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });  // let the request fail
  expect(api.getProject).toHaveBeenCalledOnce();
  expect(screen.getByText("Online page")).toBeTruthy();
  expect(screen.queryByText("This store no longer exists")).toBeNull();
});
