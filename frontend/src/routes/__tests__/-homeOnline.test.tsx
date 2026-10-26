// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import type { ProjectListItem } from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";

const navigate = vi.fn();
const projects = vi.hoisted(() => ({ list: [] as ProjectListItem[], loading: false, error: null as Error | null }));
vi.mock("@tanstack/react-router", async (original) => ({
  ...await original<typeof import("@tanstack/react-router")>(),
  createFileRoute: () => (options: { component: () => ReactNode }) => ({ options }),
  useNavigate: () => navigate,
  Link: ({ to, params, children, className }: { to: string; params?: { pid: string }; children: ReactNode; className?: string }) =>
    <a href={params ? to.replace("$pid", params.pid) : to} className={className}>{children}</a>,
}));
vi.mock("@/shared/queries/useProjects", () => ({
  useProjects: () => ({ data: projects.list, isLoading: projects.loading, isFetching: false, error: projects.error, refetch: vi.fn() }),
}));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getStoreTemplates: vi.fn(async () => []), getScenarios: vi.fn(async () => []),
}));
vi.mock("@/features/home/HeroStore", () => ({ HeroStore: () => null }));
vi.mock("@/features/home/StoreGallery", () => ({ StoreGallery: () => null }));

const { Route } = await import("../index");
const Home = (Route as unknown as { options: { component: () => ReactNode } }).options.component;

beforeEach(() => {
  useLocale.getState().setLocale("en");
  projects.loading = false;
  projects.error = null;
});
afterEach(() => { cleanup(); navigate.mockReset(); localStorage.clear(); });

async function mount() {
  const client = new QueryClient();
  // The page suspends while its translations load; the first load can take seconds on a busy machine.
  await act(async () => { render(<QueryClientProvider client={client}><Home /></QueryClientProvider>); });
  await screen.findByRole("heading", { level: 1 }, { timeout: 10_000 });
}

const store = (id: string, name: string, updated: string) => ({
  project_id: id, name, description: "", store_type: "cafe", grid_size: null, weekly_schedule: [], created_at: updated,
  updated_at: updated, status: "Ready",
}) as ProjectListItem;

it("opens the online stores of the most recently changed store from the home screen", async () => {
  projects.list = [store("old", "Old shop", "2026-10-01T00:00:00Z"), store("new", "New shop", "2026-10-20T00:00:00Z")];
  await mount();
  const button = await screen.findByRole("button", { name: "Online stores" });
  expect(button.getAttribute("title")).toContain("New shop");
  fireEvent.click(button);
  expect(navigate).toHaveBeenCalledWith({ to: "/online/$pid", params: { pid: "new" } });
});

it("asks for a store first when there is none", async () => {
  projects.list = [];
  await mount();
  fireEvent.click(await screen.findByRole("button", { name: "Online stores" }));
  expect(navigate).toHaveBeenCalledWith({ to: "/projects/new" });
});

it.each(["loading", "failed"])("does not treat a %s store list as a confirmed empty account", async (state) => {
  projects.list = [];
  projects.loading = state === "loading";
  projects.error = state === "failed" ? new Error("Offline") : null;
  await mount();
  const button = await screen.findByRole("button", { name: "Online stores" });
  expect(button.hasAttribute("disabled")).toBe(true);
  fireEvent.click(button);
  expect(navigate).not.toHaveBeenCalled();
});

it("leads a returning visitor back to the store opened last, or else the latest changed one", async () => {
  projects.list = [store("old", "Old shop", "2026-10-01T00:00:00Z"), store("new", "New shop", "2026-10-20T00:00:00Z")];
  await mount();
  expect((await screen.findByRole("link", { name: /Continue where you left off.*New shop/ })).getAttribute("href")).toBe("/projects/new");
  expect(screen.getByRole("button", { name: "Your stores: 2" })).toBeTruthy();
  cleanup();
  localStorage.setItem("twinstore.lastStore", "old");
  await mount();
  expect((await screen.findByRole("link", { name: /Continue where you left off.*Old shop/ })).getAttribute("href")).toBe("/projects/old");
});

it("offers no shortcut before there is a store", async () => {
  projects.list = [];
  await mount();
  await screen.findByRole("button", { name: "Online stores" });
  expect(screen.queryByText("Continue where you left off")).toBeNull();
});

it("moves keyboard focus to the store list that its button scrolls to", async () => {
  projects.list = [store("old", "Old shop", "2026-10-01T00:00:00Z"), store("new", "New shop", "2026-10-20T00:00:00Z")];
  await mount();
  const heading = document.body.appendChild(Object.assign(document.createElement("h2"), { id: "stores-heading", tabIndex: -1 }));
  heading.scrollIntoView = vi.fn();
  fireEvent.click(screen.getByRole("button", { name: "Your stores: 2" }));
  expect(document.activeElement).toBe(heading);
  heading.remove();
});
