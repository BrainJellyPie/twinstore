// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { useSimulationStore } from "@/stores/simulationStore";
import { ChannelMix } from "../ChannelMix";

vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getChannelMix: vi.fn() }));
const navigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => navigate }));

const mix: online.ChannelMix = {
  store_run_id: "run_1", store_setup_id: "setup_a", store_run_at: "2026-10-20T10:00:00", online_store: "Corner Mart online", customers: 40,
  both: 12, store_only: 20, online_only: 5, neither: 3, store_spend: 96785, online_spend: 30944,
  store_currency: "USD", online_currency: "USD",
  by_age: [{ group: "20s", customers: 25, both: 10, store_only: 10, online_only: 4, neither: 1 },
    { group: "40s", customers: 15, both: 2, store_only: 10, online_only: 1, neither: 2 }],
  by_gender: [{ group: "Female", customers: 22, both: 7, store_only: 11, online_only: 3, neither: 1 },
    { group: "Male", customers: 18, both: 5, store_only: 9, online_only: 2, neither: 2 }],
};

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ChannelMix projectId="p1" runId="r1" /></QueryClientProvider>);
}

it("splits the customers by where they bought, with spend and the split by age and gender", async () => {
  vi.mocked(online.getChannelMix).mockResolvedValue(mix);
  show();
  expect(await screen.findAllByText("Bought in both")).toHaveLength(2);  // tile and legend
  expect(screen.getByText("12").parentElement!.textContent).toContain("30%");
  expect(screen.getByText("$967.85")).toBeTruthy();
  expect(screen.getByText("$309.44")).toBeTruthy();
  expect(screen.getByRole("img", { name: "Bought in both: 10 · Only in the store: 10 · Only online: 4 · Bought nowhere: 1" })).toBeTruthy();
  expect(screen.getByText(/Online store: Corner Mart online · Customers in both: 40/)).toBeTruthy();
});

it("says how to get a store run when there is none", async () => {
  vi.mocked(online.getChannelMix).mockResolvedValue(null);
  show();
  expect(await screen.findByText(/No store run of these customers yet/)).toBeTruthy();
});

it("opens the store run on its layout, and offers no link when the layout is unknown", async () => {
  vi.mocked(online.getChannelMix).mockResolvedValue(mix);
  show();
  fireEvent.click(await screen.findByRole("button", { name: "Open the store run" }));
  const state = useSimulationStore.getState();
  expect([state.selectedSetupId, state.viewRunId, state.activeTab]).toEqual(["setup_a", "run_1", "dashboard"]);
  expect(navigate).toHaveBeenCalledWith({ to: "/projects/$pid", params: { pid: "p1" } });
  cleanup();
  vi.mocked(online.getChannelMix).mockResolvedValue({ ...mix, store_setup_id: "" });
  show();
  await screen.findAllByText("Bought in both");
  expect(screen.queryByRole("button", { name: "Open the store run" })).toBeNull();
});
