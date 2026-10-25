// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import type { ProjectListItem } from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";

const navigate = vi.fn();
const projects = vi.hoisted(() => ({ list: [] as ProjectListItem[] }));
vi.mock("@tanstack/react-router", async (original) => ({
  ...await original<typeof import("@tanstack/react-router")>(),
  createFileRoute: () => (options: { component: () => ReactNode }) => ({ options }),
  useNavigate: () => navigate,
}));
vi.mock("@/shared/queries/useProjects", () => ({
  useProjects: () => ({ data: projects.list, isLoading: false, isFetching: false, error: null, refetch: vi.fn() }),
}));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getStoreTemplates: vi.fn(async () => []), getScenarios: vi.fn(async () => []),
}));
vi.mock("@/features/home/HeroStore", () => ({ HeroStore: () => null }));
vi.mock("@/features/home/StoreGallery", () => ({ StoreGallery: () => null }));

const { Route } = await import("../index");
const Home = (Route as unknown as { options: { component: () => ReactNode } }).options.component;

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); navigate.mockReset(); });

async function mount() {
  const client = new QueryClient();
  // The page suspends while its translations load.
  await act(async () => { render(<QueryClientProvider client={client}><Home /></QueryClientProvider>); });
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
