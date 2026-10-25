// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { OnlinePage } from "../OnlinePage";

vi.mock("@tanstack/react-router", () => ({ Link: ({ children }: { children: ReactNode }) => <a>{children}</a> }));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getProject: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(),
  listSites: vi.fn(), listRuns: vi.fn(), listTemplates: vi.fn(),
}));
vi.mock("../BrowserView", () => ({ BrowserView: () => <p>Browser</p> }));

const site = (id: string, name: string, variant_of = ""): online.SiteSummary => ({
  id, name, template_id: "fashion", currency: "USD", categories: 1, products: 1, photos: 0, theme_color: "#2563eb",
  device: null, cart_reminder: false, variant_of, note: "", created_at: "", updated_at: "",
});

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { name: "Project", currency: "USD" }, personas: [], setups: [] } as never);
  vi.mocked(online.listSites).mockResolvedValue([
    site("a", "Shop A"), site("a1", "Shop A – no popup", "a"), site("a2", "Shop A – faster", "a1"),
    site("b", "Shop B"), site("orphan", "Copy of a deleted store", "gone"),
  ]);
  vi.mocked(online.listRuns).mockResolvedValue([]);
  vi.mocked(online.listTemplates).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("nests variants (copies of copies too) under the store they came from, collapsed until opened", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OnlinePage projectId="p1" /></QueryClientProvider>);
  const stores = within(await screen.findByRole("region", { name: "Stores" }));
  await stores.findByRole("button", { name: /Shop B/ });
  expect(stores.getByRole("button", { name: /Copy of a deleted store/ })).toBeTruthy();  // its original is gone: top level
  expect(stores.queryByRole("button", { name: /Shop A – no popup/ })).toBeNull();
  const toggle = stores.getByRole("button", { name: "Variants: 2" });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(toggle);
  expect(stores.getByRole("button", { name: /Shop A – no popup/ })).toBeTruthy();
  expect(stores.getByRole("button", { name: /Shop A – faster/ })).toBeTruthy();
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
});

it("finds stores and runs by name, opening the group of a matching variant", async () => {
  vi.mocked(online.listSites).mockResolvedValue([
    site("a", "Shop A"), site("a1", "Shop A – no popup", "a"), site("a2", "Shop A – faster", "a"),
    site("b", "Shop B"), site("c", "Corner Mart"), site("d", "Glow Room"), site("e", "Edge pets"),
  ]);
  vi.mocked(online.listRuns).mockResolvedValue([
    { run_id: "r1", name: "Popup test", site_ids: ["a", "a1"], site_names: ["Shop A", "Shop A – no popup"], status: "completed",
      phase: "", done: 2, total: 2, error: "", created_at: "2026-10-01T10:00:00", finished_at: "", request: { shoppers: 1 } } as online.OnlineRunStatus,
    { run_id: "r2", name: "Pets", site_ids: ["e"], site_names: ["Edge pets"], status: "completed",
      phase: "", done: 1, total: 1, error: "", created_at: "2026-10-01T10:00:00", finished_at: "", request: { shoppers: 1 } } as online.OnlineRunStatus,
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OnlinePage projectId="p1" /></QueryClientProvider>);
  const box = await screen.findByRole("searchbox", { name: "Find a store or run" });
  await screen.findByRole("button", { name: /Corner Mart/ });
  fireEvent.change(box, { target: { value: "popup" } });
  const stores = within(screen.getByRole("region", { name: "Stores" }));
  expect(stores.getByRole("button", { name: /Shop A – no popup/ })).toBeTruthy();  // its group opened by itself
  expect(stores.queryByRole("button", { name: /Shop A – faster/ })).toBeNull();
  expect(stores.queryByRole("button", { name: /Corner Mart/ })).toBeNull();
  const runs = within(screen.getByRole("region", { name: "Runs" }));
  expect(runs.getByRole("button", { name: /Popup test/ })).toBeTruthy();
  expect(runs.queryByRole("button", { name: /Pets/ })).toBeNull();
  fireEvent.change(box, { target: { value: "zzz" } });
  expect(screen.getByText("Nothing matches.")).toBeTruthy();
});
