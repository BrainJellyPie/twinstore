// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { LocalModelPanel } from "../LocalModelPanel";

vi.mock("@/shared/api/client", () => ({ getModelSetup: vi.fn(), startLocalModel: vi.fn(), stopLocalModel: vi.fn() }));

const base: api.ModelSetup = {
  warning: null, cloud_providers: [],
  local: { state: "off", message: "", progress: null, downloaded_mb: 0, total_mb: 0, api_base: null, model_ref: "local", managed: false, runtime: "" },
  hardware: { os: "linux", arch: "x64", cpu: "CPU", cores: 4, threads: 8, ram_gb: 16, ram_free_gb: 8, gpus: [] },
  plan: { backend: "cpu", model: { key: "small", label: "Small model", repo: "model/repo", download_gb: 2, memory_gb: 2 }, device: "CPU", gpu_layers: 0, threads: 4, parallel: 1, context: 4096, reason: "Fits" },
};
const withState = (state: api.LocalVLMStatus["state"], managed = false): api.ModelSetup => ({ ...base, local: { ...base.local, state, managed } });
const engines = { queryKey: queryKeys.engines() };
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.startLocalModel).mockResolvedValue(withState("preparing").local);
  vi.mocked(api.stopLocalModel).mockResolvedValue(withState("off").local);
});
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });

async function show(data: api.ModelSetup) {
  vi.mocked(api.getModelSetup).mockResolvedValue(data);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><LocalModelPanel /></QueryClientProvider>);
  await waitFor(() => expect(client.getQueryData(queryKeys.modelSetup())).toEqual(data));
  await act(async () => {});
  const invalidate = vi.spyOn(client, "invalidateQueries");
  return { client, invalidate };
}

it.each(["preparing", "downloading", "starting"] as const)("lets the user cancel while %s and refreshes engine readiness", async (state) => {
  const { invalidate } = await show(withState(state));
  expect(screen.queryByRole("button", { name: /Setting up/ })).toBeNull();
  const stop = screen.getByRole("button", { name: "Stop" }) as HTMLButtonElement;
  expect(stop.disabled).toBe(false);
  fireEvent.click(stop);
  await waitFor(() => expect(api.stopLocalModel).toHaveBeenCalledOnce());
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith(engines));
  expect(api.startLocalModel).not.toHaveBeenCalled();
});

it("stops a managed running model and starts one that is off", async () => {
  await show(withState("ready", true));
  expect(screen.getByRole("button", { name: "Stop" })).toBeTruthy();
  cleanup();
  const { invalidate } = await show(withState("off"));
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Start Small model" }));
  await waitFor(() => expect(api.startLocalModel).toHaveBeenCalledOnce());
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith(engines));
});

it("does not offer Stop for a server TwinStore did not start", async () => {
  await show(withState("ready", false));
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
  expect((screen.getByRole("button", { name: "Start Small model" }) as HTMLButtonElement).disabled).toBe(true);
});

it("refreshes engine readiness when a poll sees the local model become ready or go away", async () => {
  const { client, invalidate } = await show(withState("starting"));
  const poll = async (data: api.ModelSetup) => {
    vi.mocked(api.getModelSetup).mockResolvedValue(data);
    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.modelSetup() }); });
  };
  await poll(withState("downloading"));
  expect(invalidate).not.toHaveBeenCalledWith(engines);
  await poll(withState("ready", true));
  expect(invalidate).toHaveBeenCalledWith(engines); invalidate.mockClear();
  await poll(withState("ready", true));
  expect(invalidate).not.toHaveBeenCalledWith(engines);
  await poll(withState("error"));
  expect(invalidate).toHaveBeenCalledWith(engines);
});

it("explains a failed check and retries it instead of hiding the section", async () => {
  vi.mocked(api.getModelSetup).mockRejectedValueOnce(new Error("Backend unavailable")).mockResolvedValue(base);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><LocalModelPanel /></QueryClientProvider>);
  expect((await screen.findByRole("alert")).textContent).toContain("Backend unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("button", { name: "Start Small model" })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("shows why starting or stopping the local model failed", async () => {
  vi.mocked(api.startLocalModel).mockRejectedValue(new Error("Not enough disk space"));
  await show(withState("off"));
  fireEvent.click(screen.getByRole("button", { name: "Start Small model" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Could not start the local model: Not enough disk space");
  cleanup();
  vi.mocked(api.stopLocalModel).mockRejectedValue(new Error("Process is not responding"));
  await show(withState("downloading"));
  fireEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Could not stop the local model: Process is not responding");
});

it("says the model is turned off by TWINSTORE_LOCAL_VLM and how to turn it on, instead of claiming it is in use", async () => {
  await show(withState("disabled"));
  const heading = screen.getByRole("heading", { level: 2 }).textContent ?? "";
  expect(heading).toContain("(turned off)");
  expect(heading).not.toContain("in use");
  expect(screen.getByTestId("local-model-turned-off").textContent).toMatch(/TWINSTORE_LOCAL_VLM.*restart TwinStore/s);
  expect(screen.queryByRole("button", { name: /^Start/ })).toBeNull();
});

it("names the download on Start when the model is not on this computer yet", async () => {
  await show({ ...base, local: { ...base.local, downloaded: false } });
  fireEvent.click(screen.getByRole("button", { name: "Download and start Small model (2 GB)" }));
  await waitFor(() => expect(api.startLocalModel).toHaveBeenCalledOnce());
});
