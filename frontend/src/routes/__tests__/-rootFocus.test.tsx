// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider, useNavigate } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { useLocale } from "@/shared/i18n/i18n";

vi.mock("@/app/CommandBar", () => ({ CommandBar: () => null }));
// A palette that goes to the second page on Enter and, like the real one, closes a moment later.
vi.mock("@/app/CommandPalette", async () => {
  const { useState } = await import("react");
  const { useNavigate } = await import("@tanstack/react-router");
  return {
    CommandPalette: function Palette() {
      const [open, setOpen] = useState(true);
      const navigate = useNavigate();
      const to: string = "/second";
      return open ? <input aria-label="Command" onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        void navigate({ to });
        setTimeout(() => setOpen(false), 300);
      }} /> : null;
    },
  };
});
vi.mock("@/app/ModelSetupBanner", () => ({ ModelSetupBanner: () => null }));
vi.mock("@/app/AppBackdrop", () => ({ AppBackdrop: () => null }));
vi.mock("@/app/QuitTwinStore", () => ({ TabCloseNotice: () => null }));
vi.mock("@/app/RunNotice", () => ({ RunNotice: () => null }));

const { Route: root } = await import("../__root");
const clients: QueryClient[] = [];
beforeEach(() => { useLocale.getState().setLocale("en"); vi.spyOn(window, "scrollTo").mockImplementation(() => {}); });
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.restoreAllMocks(); });

function Away({ to }: { to: string }) {
  const navigate = useNavigate();
  return <button type="button" onClick={() => void navigate({ to })}>Go</button>;
}

async function mount(path: string) {
  const first = createRoute({ getParentRoute: () => root, path: "/first", component: () => <Away to="/second" /> });
  const second = createRoute({ getParentRoute: () => root, path: "/second", component: () => <p>Second page</p> });
  const asks = createRoute({ getParentRoute: () => root, path: "/asks", component: () => <input aria-label="Name" ref={(el) => el?.focus()} /> });
  const leave = createRoute({ getParentRoute: () => root, path: "/leave", component: () => <Away to="/asks" /> });
  const router = createRouter({ routeTree: root.addChildren([first, second, asks, leave]), history: createMemoryHistory({ initialEntries: [path] }) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

it("skips past the header to the page", async () => {
  await mount("/second");
  fireEvent.click(await screen.findByRole("link", { name: "Skip to content" }));
  expect(document.activeElement).toBe(screen.getByRole("main"));
});

it("carries on from the new page when going there removed what had focus", async () => {
  await mount("/first");
  const go = await screen.findByRole("button", { name: "Go" });
  go.focus();
  fireEvent.click(go);
  await screen.findByText("Second page");
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("main")));
});

it("carries on from the new page after the palette that went there closes", async () => {
  await mount("/asks");
  const command = screen.getByRole("textbox", { name: "Command" });
  command.focus();
  fireEvent.keyDown(command, { key: "Enter" });
  await screen.findByText("Second page");
  await waitFor(() => expect(screen.queryByRole("textbox", { name: "Command" })).toBeNull());
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("main")));
});

it("leaves focus where the new page puts it", async () => {
  await mount("/leave");
  const go = await screen.findByRole("button", { name: "Go" });
  go.focus();
  fireEvent.click(go);
  const name = await screen.findByRole("textbox", { name: "Name" });
  await new Promise((resolve) => setTimeout(resolve, 250));
  expect(document.activeElement).toBe(name);
});
