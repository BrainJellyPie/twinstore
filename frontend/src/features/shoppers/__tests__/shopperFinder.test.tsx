// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import * as api from "@/shared/api/client";
import { setupWithKey } from "@/features/settings/__tests__/modelSetupWithKey";
import { askGroup, findShoppers, listGroups } from "@/shared/api/interview";
import type { CustomerResult, Persona, Store } from "@/shared/types/domain";
import { useAssistStore } from "@/stores/assistStore";
import { ShopperPanel } from "../ShopperPanel";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(), findShoppers: vi.fn(), listGroups: vi.fn(), askGroup: vi.fn(),
  suggestGroupQuestions: vi.fn(), deleteGroup: vi.fn(),
}));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]), getModelSetup: vi.fn() }));
vi.mock("@tanstack/react-router", async (original) => ({
  ...await original<typeof import("@tanstack/react-router")>(), Link: ({ children }: { children: React.ReactNode }) => <a href="/settings">{children}</a>,
}));
beforeEach(() => { vi.mocked(api.getModelSetup).mockResolvedValue(setupWithKey); });
afterEach(() => { cleanup(); vi.clearAllMocks(); useAssistStore.setState({ pending: null }); });

const shopper = (id: string, spent: number): CustomerResult => ({
  persona_id: id, day: 1, arrival_time: "15:00:00", leave_time: "15:10:00", total_spent: spent,
  timeline: [{ elapsed_sec: 0, x: 0, y: 0, action: "browse", target_rack: "r1" }],
} as unknown as CustomerResult);
const persona = (id: string, identity: string): Persona => ({ id, identity, age_group: "20s", gender: "Female" } as unknown as Persona);
const customers = [shopper("p1", 0), shopper("p2", 0), shopper("p3", 500)];
const personas = [persona("p1", "Student A"), persona("p2", "Student B"), persona("p3", "Office worker")];

function mount() {
  render(<QueryClientProvider client={new QueryClient()}>
    <ShopperPanel projectId="p" runId="r" customers={customers} personas={personas} store={{ racks: [] } as unknown as Store} />
  </QueryClientProvider>);
}

it("lists exactly the shoppers found from a description and can interview them as a group", async () => {
  vi.mocked(findShoppers).mockResolvedValue({ label: "Afternoon browsers", persona_ids: ["p2", "p1"], total: 3,
    criteria: ["Bought nothing", "Arrived at or after 15:00"], warnings: ['No shelf "Moon shelf" in this store; that condition was left out.'], sort: "nothing", near_misses: [] });
  vi.mocked(listGroups).mockResolvedValue([]);
  vi.mocked(askGroup).mockImplementation(() => new Promise(() => {}));
  mount();
  fireEvent.change(screen.getByLabelText("Describe shoppers to find"), { target: { value: "browsers who bought nothing this afternoon" } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  const card = await screen.findByRole("region", { name: "Found shoppers" });
  expect(findShoppers).toHaveBeenCalledWith("p", "r", "browsers who bought nothing this afternoon");
  expect(within(card).getByText("2 of 3 shoppers")).toBeTruthy();
  expect(within(card).getByText("Arrived at or after 15:00")).toBeTruthy();
  expect(within(card).getByText(/Moon shelf/)).toBeTruthy();
  const names = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
  expect(names).toHaveLength(2);
  expect(names[0]).toContain("Student B");  // the found order is kept
  expect(names.some((n) => n.includes("Office worker"))).toBe(false);

  fireEvent.click(within(card).getByRole("button", { name: "Interview these shoppers" }));
  expect(await screen.findByRole("button", { name: "Afternoon browsers · 2" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /^Ask 2$/ }));
  await waitFor(() => expect(askGroup).toHaveBeenCalled());
  expect(vi.mocked(askGroup).mock.calls[0]![2]).toMatchObject({ segment: "all", size: 2, persona_ids: ["p2", "p1"] });
});

it("clears the found shoppers back to the whole run", async () => {
  vi.mocked(findShoppers).mockResolvedValue({ label: "Big baskets", persona_ids: ["p3"], total: 3, criteria: ["Spent at least $1.00"], warnings: [], sort: "spent", near_misses: [] });
  mount();
  fireEvent.change(screen.getByLabelText("Describe shoppers to find"), { target: { value: "big spenders" } });
  fireEvent.keyDown(screen.getByLabelText("Describe shoppers to find"), { key: "Enter" });
  await screen.findByRole("region", { name: "Found shoppers" });
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Interview these shoppers" })).toBeNull();  // one shopper is not a group
  fireEvent.click(screen.getByRole("button", { name: "Clear the found shoppers" }));
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
});

it("says which single condition keeps everyone out when nobody fits", async () => {
  vi.mocked(findShoppers).mockResolvedValue({ label: "Nobody", persona_ids: [], total: 3, criteria: ["Bought nothing", "Spent at least $1.00"],
    warnings: [], sort: "spent", near_misses: ['Without "Bought nothing": 1 shopper'] });
  mount();
  fireEvent.change(screen.getByLabelText("Describe shoppers to find"), { target: { value: "empty baskets that spent money" } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  expect(await screen.findByText('Without "Bought nothing": 1 shopper')).toBeTruthy();
  expect(screen.getByText("No shopper matches.")).toBeTruthy();
});

it("searches a description routed from the command palette once", async () => {
  vi.mocked(findShoppers).mockResolvedValue({ label: "Students", persona_ids: ["p1"], total: 3, criteria: ["Persona mentions: student"],
    warnings: [], sort: "spent", near_misses: [] });
  useAssistStore.getState().send({ projectId: "p", destination: "find_shoppers", text: "students who left empty-handed" });
  mount();
  expect(await screen.findByRole("region", { name: "Found shoppers" })).toBeTruthy();
  expect(findShoppers).toHaveBeenCalledTimes(1);
  expect((screen.getByLabelText("Describe shoppers to find") as HTMLInputElement).value).toBe("students who left empty-handed");
});

it("tells assistive technology which sort is chosen", () => {
  vi.mocked(listGroups).mockResolvedValue([]);
  mount();
  const top = screen.getByRole("button", { name: "Top spenders" });
  const empty = screen.getByRole("button", { name: "Left empty-handed" });
  expect([top.getAttribute("aria-pressed"), empty.getAttribute("aria-pressed")]).toEqual(["true", "false"]);
  fireEvent.click(empty);
  expect([top.getAttribute("aria-pressed"), empty.getAttribute("aria-pressed")]).toEqual(["false", "true"]);
});

it("offers model setup when no model can find shoppers from a description", async () => {
  vi.mocked(api.getModelSetup).mockResolvedValue({ cloud_providers: [], local: { state: "stopped", downloaded: true, progress: null } } as unknown as api.ModelSetup);
  vi.mocked(findShoppers).mockRejectedValue(new Error("No model API key is set."));
  vi.mocked(listGroups).mockResolvedValue([]);
  mount();
  fireEvent.change(screen.getByLabelText("Describe shoppers to find"), { target: { value: "browsers who bought nothing" } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  expect((await screen.findByRole("alert")).textContent).toBe("No model API key is set.");
  expect(await screen.findByTestId("needs-model")).toBeTruthy();
});
