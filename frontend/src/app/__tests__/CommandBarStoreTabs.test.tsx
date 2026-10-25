// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { CommandBar } from "../CommandBar";

const state = vi.hoisted(() => ({ pathname: "/settings", projects: [] as { project_id: string }[] }));
vi.mock("@tanstack/react-router", () => ({
  useLocation: () => ({ pathname: state.pathname }),
  Link: ({ children, to, params, ...rest }: { children: ReactNode; to: string; params?: Record<string, string> } & Record<string, unknown>) =>
    <a href={params?.pid !== undefined ? to.replace("$pid", params.pid) : to} {...(rest as object)}>{children}</a>,
}));
vi.mock("@/shared/queries/useProjects", () => ({ useProjects: () => ({ data: state.projects }) }));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getHealth: vi.fn(), getProject: vi.fn() }));
vi.mock("../QuitTwinStore", () => ({ QuitButton: () => null }));

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getHealth).mockResolvedValue({ status: "ok" });
  localStorage.clear();
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function show(pathname: string, projects: string[]) {
  state.pathname = pathname;
  state.projects = projects.map((project_id) => ({ project_id }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><CommandBar /></QueryClientProvider>);
}

it("opens the store used last from pages outside a store", () => {
  show("/projects/proj_b", ["proj_a", "proj_b"]);
  cleanup();
  show("/settings", ["proj_a", "proj_b"]);
  expect(screen.getByRole("link", { name: "Floor" }).getAttribute("href")).toBe("/projects/proj_b");
  expect(screen.getByRole("link", { name: "Online" }).getAttribute("href")).toBe("/online/proj_b");
});

it("opens the only store, and stays disabled with several stores and none remembered", () => {
  show("/settings", ["proj_only"]);
  expect(screen.getByRole("link", { name: "Area" }).getAttribute("href")).toBe("/town/proj_only");
  cleanup();
  show("/settings", ["proj_a", "proj_b"]);
  expect(screen.getByRole("link", { name: "Area" }).getAttribute("aria-disabled")).toBe("true");
});
