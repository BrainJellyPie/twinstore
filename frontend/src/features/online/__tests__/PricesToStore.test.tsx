// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as marketing from "@/shared/api/marketing";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { useExperimentDraft } from "@/stores/experimentDraftStore";
import { PricesToStore } from "../PricesToStore";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => navigate }));

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getSetups: vi.fn(), getProject: vi.fn() }));
vi.mock("@/shared/api/marketing", async (original) => ({ ...await original<typeof marketing>(), checkLayoutEdit: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getRunStoreChanges: vi.fn() }));

const changes: online.RunStoreChanges = {
  name: "Lower price", currency: "USD", changes: [{ kind: "price", sku: "SKU-1", price: 189 } as marketing.VariantChange],
  skipped: ["the page design, delivery and checkout options have no shelf counterpart"],
};

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getSetups).mockResolvedValue([
    { id: "setup_a", name: "Main floor" }, { id: "setup_b", name: "Summer layout" },
  ] as api.SetupSummary[]);
  vi.mocked(api.getProject).mockResolvedValue({ state: { activeSetupId: "setup_b", runningSetups: [] } } as unknown as api.ProjectDetail);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><PricesToStore projectId="p1" runId="r1" variant={1} /></QueryClientProvider>);
}

it("reviews a variant's prices on the active layout in the run's currency and says what stays online", async () => {
  vi.mocked(online.getRunStoreChanges).mockResolvedValue(changes);
  vi.mocked(marketing.checkLayoutEdit).mockResolvedValue({
    name: "Lower price", source_sha256: "x", applied: ["Oat milk: price $1.99 → $1.89"], warnings: [], changes: changes.changes,
  } as unknown as marketing.LayoutEditDraft);
  mount();
  const layout = await screen.findByRole("combobox", { name: "Store layout" }) as HTMLSelectElement;
  expect(layout.value).toBe("setup_b");
  expect(screen.getByText(/Stays online:/).parentElement?.textContent).toContain("no shelf counterpart");
  fireEvent.change(layout, { target: { value: "setup_a" } });
  fireEvent.click(screen.getByRole("button", { name: "Review on the layout" }));
  expect(await screen.findByText("Oat milk: price $1.99 → $1.89")).toBeTruthy();
  expect(marketing.checkLayoutEdit).toHaveBeenCalledWith("p1", "setup_a", { name: "Lower price", changes: changes.changes, currency: "USD" });
  expect(online.getRunStoreChanges).toHaveBeenCalledWith("p1", "r1", 1, expect.anything());
});

it("shows nothing when the variant changed no price", async () => {
  vi.mocked(online.getRunStoreChanges).mockResolvedValue({ ...changes, changes: [] });
  mount();
  await vi.waitFor(() => expect(online.getRunStoreChanges).toHaveBeenCalled());
  expect(screen.queryByRole("combobox", { name: "Store layout" })).toBeNull();
});

it("shows a failed transfer request and lets the owner retry", async () => {
  vi.mocked(online.getRunStoreChanges).mockRejectedValueOnce(new Error("This transfer exceeds 500 price changes"))
    .mockResolvedValue(changes);
  mount();
  expect((await screen.findByRole("alert")).textContent).toContain("500 price changes");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("combobox", { name: "Store layout" })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("opens the variant's prices as an A/B test on the chosen layout", async () => {
  vi.mocked(online.getRunStoreChanges).mockResolvedValue({ ...changes, name: "Threadline – all prices 10 % lower than the rival" });
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Test it in the store" }));
  expect(useExperimentDraft.getState().take("p1")).toEqual({
    setup_id: "setup_b", engine: "rule", panel: 300, focus_skus: [],
    variants: [{ name: "Threadline – all prices 10 % lower than", changes: changes.changes }],
  });
  expect(navigate).toHaveBeenCalledWith({ to: "/marketing/$pid", params: { pid: "p1" } });
});

it("explains why a variant with more changes than an A/B test holds is not offered as one", async () => {
  const many = Array.from({ length: 21 }, (_, i) => ({ kind: "price", sku: `SKU-${i}`, price: 100 + i }) as marketing.VariantChange);
  vi.mocked(online.getRunStoreChanges).mockResolvedValue({ ...changes, changes: many });
  mount();
  expect(await screen.findByText(/takes up to 20 changes and this variant has 21/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Test it in the store" })).toBeNull();
});
