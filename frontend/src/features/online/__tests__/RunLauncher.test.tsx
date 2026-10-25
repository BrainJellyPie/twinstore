// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { queryKeys } from "@/shared/queries/keys";
import { useLocale } from "@/shared/i18n/i18n";
import { RunLauncher } from "../RunLauncher";

vi.mock("@/shared/api/client", () => ({ getModels: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), startRun: vi.fn(), getSite: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: ({ children }: { children: ReactNode }) => <span>{children}</span> }));
const models: api.ModelOption[] = [
  { ref: "local:text", provider: "Local", label: "Local text", vision: false, local: true },
  { ref: "local:vision", provider: "Local", label: "Local vision", vision: true, local: true },
];
const site: online.SiteSummary = {
  id: "s1", name: "Shop", template_id: "fashion", currency: "USD", categories: 1, products: 4, photos: 0,
  theme_color: "#000000", device: null, variant_of: "", note: "", created_at: "", updated_at: "",
};
const clients: QueryClient[] = [];
beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getModels).mockResolvedValue(models);
  vi.mocked(online.getSite).mockRejectedValue(new Error("Store options unavailable"));
  vi.mocked(online.startRun).mockImplementation(() => new Promise(() => {}));
});
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><RunLauncher projectId="p1" sites={[site]} firstSiteId="s1"
    hasCustomers onStarted={vi.fn()} /></QueryClientProvider>);
  return client;
}
function start() { return screen.getByRole("button", { name: "Start run" }) as HTMLButtonElement; }
async function chooseText() {
  const client = mount();
  fireEvent.click(screen.getByRole("radio", { name: /^Text model/ }));
  await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  return client;
}

it("blocks an empty ensemble instead of submitting the default model", async () => {
  await chooseText();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  expect(start().disabled).toBe(true);
  fireEvent.click(start());
  expect(online.startRun).not.toHaveBeenCalled();
});

it("keeps an incomplete single-model choice blocked after a delayed catalog arrives", async () => {
  let resolve: (items: api.ModelOption[]) => void = () => {};
  vi.mocked(api.getModels).mockReturnValue(new Promise((done) => { resolve = done; }));
  mount();
  fireEvent.click(screen.getByRole("radio", { name: /^Text model/ }));
  fireEvent.click(screen.getByRole("button", { name: "One model" }));
  expect(start().disabled).toBe(true);
  await act(async () => { resolve(models); });
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Model" }) as HTMLSelectElement).disabled).toBe(false));
  expect(start().disabled).toBe(true);
  fireEvent.change(screen.getByRole("combobox", { name: "Model" }), { target: { value: "local:text" } });
  await waitFor(() => expect(start().disabled).toBe(false));
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({ model: "local:text" })));
});

it.each(["", "0", "-2"])("blocks invalid ensemble weight %j and accepts the corrected choice", async (weight) => {
  await chooseText();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  fireEvent.click(screen.getByLabelText("Local · Local text"));
  const input = screen.getByLabelText("Weight of Local text");
  fireEvent.change(input, { target: { value: weight } });
  expect(start().disabled).toBe(true);
  fireEvent.change(input, { target: { value: "2" } });
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({
    ensemble: { mode: "mixture", members: [{ model: "local:text", weight: 2 }] },
  })));
});

it.each(["single", "ensemble"])("blocks a text-only %s when switching to vision shoppers", async (kind) => {
  await chooseText();
  fireEvent.click(screen.getByRole("button", { name: kind === "single" ? "One model" : "Ensemble" }));
  if (kind === "ensemble") fireEvent.click(screen.getByLabelText("Local · Local text"));
  fireEvent.click(screen.getByRole("radio", { name: /^Vision model/ }));
  expect(start().disabled).toBe(true);
  fireEvent.click(start());
  expect(online.startRun).not.toHaveBeenCalled();
});

it("blocks a model removed by a catalog refresh", async () => {
  const client = await chooseText();
  fireEvent.click(screen.getByRole("button", { name: "One model" }));
  await act(async () => { client.setQueryData(queryKeys.models(), [models[1]!]); });
  await waitFor(() => expect(start().disabled).toBe(true));
});

it("does not offer shelf-voting mode to online vision shoppers", async () => {
  await chooseText();
  fireEvent.click(screen.getByRole("radio", { name: /^Vision model/ }));
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  expect(screen.queryByRole("radio", { name: /^Vote / })).toBeNull();
});

it("allows rules even when a previous model choice is incomplete", async () => {
  await chooseText();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  fireEvent.click(screen.getByRole("radio", { name: /^Rules/ }));
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({ policy: "rule", model: null, ensemble: null })));
});

it("allows an explicitly chosen server default while the catalog is unavailable", async () => {
  vi.mocked(api.getModels).mockRejectedValue(new Error("Offline"));
  mount();
  fireEvent.click(screen.getByRole("radio", { name: /^Text model/ }));
  await screen.findByText("Offline");
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({ policy: "text", model: null, ensemble: null })));
});

it("sends where visitors come from, and needs at least one source", async () => {
  mount();
  fireEvent.change(screen.getByRole("slider", { name: "Direct" }), { target: { value: "0" } });
  expect(start().disabled).toBe(true);
  expect(screen.getByText("Give at least one traffic source a share above zero.")).toBeTruthy();
  fireEvent.change(screen.getByRole("slider", { name: "Direct" }), { target: { value: "100" } });
  fireEvent.change(screen.getByRole("slider", { name: "Search engine" }), { target: { value: "50" } });
  expect(start().disabled).toBe(false);
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({
    arrivals: { direct: 1, search_engine: 0.5, social: 0, email: 0 },
  })));
});

it("offers other stores in the same currency as the rival shop and sends the choice", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  const sites = [site, { ...site, id: "s2", name: "Neighbour" }, { ...site, id: "s3", name: "Seoul shop", currency: "KRW" }];
  render(<QueryClientProvider client={client}><RunLauncher projectId="p1" sites={sites} firstSiteId="s1"
    hasCustomers onStarted={vi.fn()} /></QueryClientProvider>);
  const picker = screen.getByRole("combobox", { name: /Rival shop/ }) as HTMLSelectElement;
  expect([...picker.options].map((o) => o.text)).toEqual(["None", "Neighbour"]);
  fireEvent.change(picker, { target: { value: "s2" } });
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({ site_ids: ["s1"], rival_site_id: "s2" })));
  // Comparing the rival itself drops it as the rival.
  fireEvent.click(screen.getByRole("checkbox", { name: /Neighbour/ }));
  expect([...picker.options].map((o) => o.text)).toEqual(["None"]);
  expect(picker.value).toBe("");
});

it("starts with a variant made to be tested already compared with its store", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  const sites = [site, { ...site, id: "s2", name: "AI design" }];
  render(<QueryClientProvider client={client}><RunLauncher projectId="p1" sites={sites} firstSiteId="s1" compareWith="s2"
    hasCustomers onStarted={vi.fn()} /></QueryClientProvider>);
  expect((screen.getByRole("checkbox", { name: /AI design/ }) as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Compare stores: 2" }));
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({ site_ids: ["s1", "s2"] })));
});
