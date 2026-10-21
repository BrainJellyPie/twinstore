// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { OptimizeDialog } from "../OptimizeDialog";

vi.mock("@/shared/api/client", () => ({ getScenarios: vi.fn(), getModels: vi.fn(), startOptimization: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: ({ to, children, ...props }: { to: string; children: ReactNode }) => <a href={to} {...props}>{children}</a> }));
const models: api.ModelOption[] = [
  { ref: "provider:text", provider: "A", label: "Text model", vision: false, local: false },
  { ref: "provider:vision", provider: "A", label: "Vision model", vision: true, local: false },
  { ref: "other:vision", provider: "B", label: "Other vision", vision: true, local: true },
];
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  vi.mocked(api.getModels).mockResolvedValue(models);
  // Stop after checking the submitted configuration; no job or model is run.
  vi.mocked(api.startOptimization).mockRejectedValue(new Error("Scripted submission"));
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><OptimizeDialog open onOpenChange={() => {}} projectId="p" setupId="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Vision shoppers decide/ }));
  return client;
}
const start = () => screen.getByRole("button", { name: "Start" }) as HTMLButtonElement;
async function submit() { await act(async () => { fireEvent.click(start()); }); }
async function ready() {
  const client = show();
  await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  return client;
}

it("does not replace an explicitly selected empty ensemble with the server default", async () => {
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  expect(start().disabled).toBe(true);
  expect(screen.getByRole("alert").textContent).toContain("Select at least one ensemble model");
});

it.each(["One model", "Ensemble"])("waits for the model catalog when %s is explicitly selected", async (kind) => {
  vi.mocked(api.getModels).mockReturnValue(new Promise(() => {}));
  show();
  fireEvent.click(screen.getByRole("button", { name: kind }));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  expect(start().disabled).toBe(true);
});

it.each(["", "0", "-0", "-0.5", "-1", "1e309", "NaN", "Infinity"])("blocks the invalid ensemble weight %s and can recover", async (weight) => {
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  const input = screen.getByLabelText("Weight of Vision model");
  fireEvent.change(input, { target: { value: weight } });
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  expect(start().disabled).toBe(true);
  fireEvent.change(input, { target: { value: "0.25" } });
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, expect.objectContaining({
    ensemble: { mode: "mixture", members: [{ model: "provider:vision", weight: 0.25 }, { model: "other:vision", weight: 1 }] },
  }));
});

it.each(["5e-324", "1e-300", "0.001", "0.25", "1", "2.75", "1e308"])("keeps the valid weight %s and vote mode", async (weight) => {
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  fireEvent.change(screen.getByLabelText("Weight of Vision model"), { target: { value: weight } });
  fireEvent.click(screen.getByRole("radio", { name: /^Vote / }));
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, expect.objectContaining({
    ensemble: { mode: "vote", members: [{ model: "provider:vision", weight: Number(weight) }, { model: "other:vision", weight: 1 }] },
  }));
});

it.each(["One model", "Ensemble"])("blocks a removed vision model for %s and allows an explicit default", async (kind) => {
  const client = await ready();
  fireEvent.click(screen.getByRole("button", { name: kind }));
  if (kind === "Ensemble") fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  await act(async () => { client.setQueryData(queryKeys.models(), [models[0]!]); });
  await waitFor(() => expect(start().disabled).toBe(true));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  expect(start().disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Server default" }));
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, expect.objectContaining({ model: null, ensemble: null }));
});

it("retries a failed catalog without silently choosing a model", async () => {
  vi.mocked(api.getModels).mockRejectedValueOnce(new Error("Catalog offline"));
  show();
  await screen.findByText("Catalog offline");
  fireEvent.click(screen.getByRole("button", { name: "One model" }));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Retry models" }));
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Model" }) as HTMLSelectElement).disabled).toBe(false));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  fireEvent.change(screen.getByRole("combobox", { name: "Model" }), { target: { value: "other:vision" } });
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, expect.objectContaining({ model: "other:vision", ensemble: null }));
});

it.each(["loading", "failed"])("preserves a deliberate server default while the catalog is %s", async (state) => {
  if (state === "loading") vi.mocked(api.getModels).mockReturnValue(new Promise(() => {}));
  else vi.mocked(api.getModels).mockRejectedValue(new Error("Catalog offline"));
  show();
  if (state === "failed") await screen.findByText("Catalog offline");
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, expect.objectContaining({ model: null, ensemble: null }));
});

it("allows a deliberate rule-based judge after an incomplete vision choice", async () => {
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  fireEvent.click(screen.getByRole("button", { name: /Rule-based shoppers/ }));
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, undefined);
});

it("keeps a known selected model usable after a background catalog refresh fails", async () => {
  const client = await ready();
  fireEvent.click(screen.getByRole("button", { name: "One model" }));
  vi.mocked(api.getModels).mockRejectedValueOnce(new Error("Refresh offline"));
  await act(async () => { await client.invalidateQueries({ queryKey: queryKeys.models() }); });
  await screen.findByText("Refresh offline");
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, expect.objectContaining({ model: "provider:vision" }));
});

it("can remove unavailable ensemble members without changing the remaining weight", async () => {
  const client = await ready();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  fireEvent.change(screen.getByLabelText("Weight of Vision model"), { target: { value: "0.25" } });
  await act(async () => { client.setQueryData(queryKeys.models(), [models[1]!]); });
  await waitFor(() => expect(start().disabled).toBe(true));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Remove other:vision" }));
  await submit();
  expect(api.startOptimization).toHaveBeenCalledWith("p", "s", expect.anything(), null, expect.objectContaining({
    ensemble: { mode: "mixture", members: [{ model: "provider:vision", weight: 0.25 }] },
  }));
});

it.each([{ catalog: [] }, { catalog: [models[0]!] }])("does not use a catalog without vision models as a valid single choice: %j", async ({ catalog }) => {
  vi.mocked(api.getModels).mockResolvedValue(catalog);
  const client = show();
  await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(catalog));
  fireEvent.click(screen.getByRole("button", { name: "One model" }));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  expect(start().disabled).toBe(true);
});

it("keeps an incomplete vision selection blocked after switching judge types twice", async () => {
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Ensemble" }));
  fireEvent.click(screen.getByRole("button", { name: /Rule-based shoppers/ }));
  expect(start().disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: /Vision shoppers decide/ }));
  await submit();
  expect(api.startOptimization).not.toHaveBeenCalled();
  expect(start().disabled).toBe(true);
});
