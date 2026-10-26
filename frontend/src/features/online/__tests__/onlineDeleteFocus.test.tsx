// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
vi.mock("../SiteDesigner", () => ({ SiteDesigner: ({ onDeleted }: { onDeleted: () => void }) => <button onClick={onDeleted}>Delete this store</button> }));

const site = (id: string, name: string): online.SiteSummary => ({
  id, name, template_id: "fashion", currency: "USD", categories: 1, products: 1, photos: 0, theme_color: "#2563eb",
  device: null, cart_reminder: false, variant_of: "", note: "", created_at: "", updated_at: "",
});

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { name: "Project", currency: "USD" }, personas: [], setups: [] } as never);
  vi.mocked(online.listSites).mockResolvedValue([site("a", "Shop A"), site("b", "Shop B")]);
  vi.mocked(online.listRuns).mockResolvedValue([]);
  vi.mocked(online.listTemplates).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("moves focus to the store now open after deleting one", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OnlinePage projectId="p1" /></QueryClientProvider>);
  const stores = within(await screen.findByRole("region", { name: "Stores" }));
  fireEvent.click(await stores.findByRole("button", { name: /Shop B/ }));
  fireEvent.click(screen.getByRole("tab", { name: /Design/ }));
  fireEvent.click(screen.getByRole("button", { name: "Delete this store" }));
  await waitFor(() => expect(document.activeElement).toBe(stores.getByRole("button", { name: /Shop A/ })));
});
