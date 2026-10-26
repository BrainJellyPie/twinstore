// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { designShelfTest, startShelfTest } from "@/shared/api/marketing";
import type { Store } from "@/shared/types/domain";
import { ShelfTestBuilder } from "../ShelfTest";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
  getModelSetup: vi.fn().mockResolvedValue({ cloud_providers: [], local: { state: "stopped", downloaded: true, progress: null } }),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), startShelfTest: vi.fn(), designShelfTest: vi.fn(),
  previewShelf: vi.fn().mockResolvedValue({ face: "N", control: "control.png", test: "test.png", applied: [], warnings: [] }),
}));
vi.mock("@tanstack/react-router", async (original) => ({
  ...await original<typeof import("@tanstack/react-router")>(), Link: ({ children }: { children: ReactNode }) => <a href="/settings">{children}</a>,
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [{ asset_id: "pkg_gold", name: "Gold label" }] }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const rack = (id: string, name: string, sku: string) => ({ id, type: "shelf" as const, shape: [[1]], position: [2, 2] as [number, number],
  rotation: 0 as const, levels: 4, dwell_min: 2, dwell_max: 30, rack_name: name, rack_desc: "", rack_decoration_desc: "", locked_faces: [],
  slots: [{ block: 0, face: "N" as const, level: 1, items: [{ sku, name: sku.toUpperCase(), price: 250, promo: "" }] }] });
const store = { id: "store", name: "Store", type: "cafe", grid_size: [8, 6], weekly_schedule: [],
  racks: [rack("drinks", "Drinks", "cola"), rack("tea", "Tea", "tea")] } as unknown as Store;

function mount(prefill?: { id: number; text: string }) {
  render(<QueryClientProvider client={new QueryClient()}>
    <ShelfTestBuilder projectId="p" setupId="s" store={store} currency="USD" prefill={prefill} onStarted={vi.fn()} />
  </QueryClientProvider>);
}

it("drafts the product, its shelf and the changes from a question, then runs them as drafted", async () => {
  vi.mocked(designShelfTest).mockResolvedValue({ name: "Gold label", rack_id: "tea", target_sku: "tea", age_groups: ["20s"],
    changes: [{ kind: "package", sku: "tea", asset_id: "pkg_gold" }, { kind: "price", sku: "tea", price: 199, keep_reference: true },
      { kind: "promo", sku: "tea", promo: "2+1" }], rationale: "Pack, price and sign.", warnings: [] });
  vi.mocked(startShelfTest).mockResolvedValue({ job_id: "slf", kind: "shelf", name: "", status: "pending", stage: "", progress: 0, error: "", created_at: "", finished_at: "" });
  mount();
  fireEvent.change(screen.getByLabelText("Question for the shelf test"), { target: { value: "Would a gold label stand out on the tea shelf?" } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the test" }));
  expect(await screen.findByText(/Pack, price and sign\./)).toBeTruthy();
  expect(designShelfTest).toHaveBeenCalledWith("p", { question: "Would a gold label stand out on the tea shelf?", setup_id: "s" });
  expect((screen.getByRole("combobox", { name: "Product under test" }) as HTMLSelectElement).value).toBe("tea");
  expect((screen.getByPlaceholderText(/leave empty to keep/) as HTMLInputElement).value).toBe("1.99");
  expect(screen.getByRole("button", { name: "2+1" })).toBeTruthy();  // a sign outside the usual chips still shows
  fireEvent.click(screen.getByRole("button", { name: "Run shelf test" }));
  await waitFor(() => expect(startShelfTest).toHaveBeenCalled());
  expect(startShelfTest).toHaveBeenCalledWith("p", expect.objectContaining({ rack_id: "tea", target_sku: "tea", name: "Gold label", age_groups: ["20s"],
    changes: [{ kind: "package", sku: "tea", asset_id: "pkg_gold" }, { kind: "price", sku: "tea", price: 199, keep_reference: true }, { kind: "promo", sku: "tea", promo: "2+1" }] }));
});

it("drafts once from a request routed by the command palette", async () => {
  vi.mocked(designShelfTest).mockResolvedValue({ name: "Sign", rack_id: "drinks", target_sku: "cola", age_groups: [],
    changes: [{ kind: "promo", sku: "cola", promo: "SALE" }], rationale: "One sign.", warnings: [] });
  mount({ id: 2, text: "Would a SALE sign make the cola stand out?" });
  expect(await screen.findByText(/One sign\./)).toBeTruthy();
  expect(designShelfTest).toHaveBeenCalledTimes(1);
  expect((screen.getByLabelText("Question for the shelf test") as HTMLInputElement).value).toBe("Would a SALE sign make the cola stand out?");
});

it("offers model setup when a run fails for want of a model", async () => {
  vi.mocked(startShelfTest).mockRejectedValue(new Error("No model server answers at http://127.0.0.1:8081/v1"));
  mount();
  fireEvent.change(screen.getByRole("combobox", { name: "Product under test" }), { target: { value: "cola" } });
  fireEvent.change(screen.getByPlaceholderText(/leave empty to keep/), { target: { value: "1.99" } });
  fireEvent.click(screen.getByRole("button", { name: "Run shelf test" }));
  expect((await screen.findByRole("alert")).textContent).toContain("No model server answers");
  expect(await screen.findByTestId("needs-model")).toBeTruthy();
  expect(screen.getByRole("button", { name: /Start local model/ })).toBeTruthy();
});
