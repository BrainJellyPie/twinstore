// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { ModelSetupBanner } from "../ModelSetupBanner";

vi.mock("@/shared/api/client", () => ({ getModelSetup: vi.fn(), startLocalModel: vi.fn(), stopLocalModel: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: ({ to, children, ...props }: { to: string; children: ReactNode }) => <a href={to} {...props}>{children}</a> }));

const base: api.ModelSetup = {
  warning: "No API key is set. Start the local model or connect a provider. Download: 2 GB.", cloud_providers: [],
  local: { state: "off", message: "Not started", progress: null, downloaded_mb: 0, total_mb: 0, api_base: null, model_ref: "local", managed: false, runtime: "" },
  hardware: { os: "linux", arch: "x64", cpu: "CPU", cores: 4, threads: 8, ram_gb: 16, ram_free_gb: 8, gpus: [] },
  plan: { backend: "cpu", model: { key: "small", label: "Small model", repo: "model/repo", download_gb: 2, memory_gb: 2 }, device: "CPU", gpu_layers: 0, threads: 4, parallel: 1, context: 4096, reason: "" },
};
const clients: QueryClient[] = [];
beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(api.getModelSetup).mockResolvedValue(base);
  vi.mocked(api.startLocalModel).mockResolvedValue({ ...base.local, state: "preparing" });
});
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.restoreAllMocks(); vi.resetAllMocks(); });

async function show(data = base) {
  vi.mocked(api.getModelSetup).mockResolvedValue(data);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
  const view = render(<QueryClientProvider client={client}><ModelSetupBanner /></QueryClientProvider>);
  await waitFor(() => expect(client.getQueryData(queryKeys.modelSetup())).toEqual(data));
  await act(async () => {});
  return { ...view, client };
}
function expand() { const details = document.querySelector("details")!; details.open = true; fireEvent(details, new Event("toggle")); }

it("makes free previews clear and folds model installation details", async () => {
  await show();
  expect(screen.getByText("Explore without an API key")).toBeTruthy();
  expect(screen.getByText(/Rule-based previews are available/)).toBeTruthy();
  expect(document.querySelector("details")!.open).toBe(false);
  expect(api.startLocalModel).not.toHaveBeenCalled();
  expand();
  expect(screen.getByRole("button", { name: "Start local model" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Model settings" }).getAttribute("href")).toBe("/settings");
});

it.each(["preparing", "downloading", "starting"] as const)("keeps preparation progress visible for %s while details stay folded", async (state) => {
  await show({ ...base, local: { ...base.local, state, progress: 0.25, downloaded_mb: 128, total_mb: 512 } });
  expect(screen.getByText("Preparing vision shoppers…")).toBeTruthy();
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("25");
  expect(screen.getByText("128 / 512 MB")).toBeTruthy();
  expect(document.querySelector("details")!.open).toBe(false);
  expect(api.startLocalModel).not.toHaveBeenCalled();
});

it.each([[null, null], [NaN, null], [Infinity, null], [-1, "0"], [0, "0"], [1, "100"], [3, "100"]])("keeps progress accessible and bounded for %s", async (progress, expected) => {
  await show({ ...base, local: { ...base.local, state: "downloading", progress, message: "Getting ready" } });
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(expected);
});

it("explains when a local vision model is ready", async () => {
  await show({ ...base, local: { ...base.local, state: "ready" } });
  expect(screen.getByText("Local vision model ready")).toBeTruthy();
  expand(); expect(screen.queryByRole("button", { name: /local model/ })).toBeNull();
});

it("offers retry for a failed model and settings for a disabled model", async () => {
  const { client } = await show({ ...base, local: { ...base.local, state: "error" } }); expand();
  expect(screen.getByRole("button", { name: "Retry local model" })).toBeTruthy();
  await act(async () => { client.setQueryData(queryKeys.modelSetup(), { ...base, local: { ...base.local, state: "disabled" } }); });
  await waitFor(() => expect(screen.queryByRole("button", { name: /local model/ })).toBeNull());
  expect(screen.getByRole("link", { name: "Model settings" })).toBeTruthy();
});

it("does not show a warning after a provider is connected", async () => {
  await show({ ...base, warning: null, cloud_providers: ["openai"] });
  expect(screen.queryByRole("status")).toBeNull();
});

it("keeps the dismissed state hidden across remounts but surfaces state changes", async () => {
  const view = await show();
  fireEvent.click(screen.getByRole("button", { name: "Hide this notice" }));
  expect(sessionStorage.getItem("twinstore.modelBanner.dismissed")).toBe("off");
  view.unmount();
  const { client } = await show();
  expect(screen.queryByRole("status")).toBeNull();
  await act(async () => { client.setQueryData(queryKeys.modelSetup(), { ...base, local: { ...base.local, state: "error" } }); });
  expect(await screen.findByText("Vision model needs attention")).toBeTruthy();
});

it("still renders and dismisses when browser storage is unavailable", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Storage blocked"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage blocked"); });
  await show();
  fireEvent.click(screen.getByRole("button", { name: "Hide this notice" }));
  expect(screen.queryByRole("status")).toBeNull();
});

it("explains a failed start and permits retry without automatically starting", async () => {
  vi.mocked(api.startLocalModel).mockRejectedValueOnce(new Error("Download unavailable"));
  await show(); expand();
  fireEvent.click(screen.getByRole("button", { name: "Start local model" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Download unavailable");
  const start = screen.getByRole("button", { name: "Start local model" });
  expect((start as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(start);
  await waitFor(() => expect(api.startLocalModel).toHaveBeenCalledTimes(2));
});

it("prevents repeat starts while the first request is pending", async () => {
  let resolve!: (status: api.LocalVLMStatus) => void;
  vi.mocked(api.startLocalModel).mockReturnValue(new Promise((done) => { resolve = done; }));
  await show(); expand();
  fireEvent.click(screen.getByRole("button", { name: "Start local model" }));
  const pending = await screen.findByRole("button", { name: "Starting…" });
  fireEvent.click(pending);
  expect(api.startLocalModel).toHaveBeenCalledOnce();
  await act(async () => resolve({ ...base.local, state: "preparing" }));
});

it.each(["preparing", "downloading", "starting"] as const)("offers Stop while the local model is %s", async (state) => {
  vi.mocked(api.stopLocalModel).mockRejectedValueOnce(new Error("Process is not responding")).mockResolvedValue({ ...base.local, state: "off" });
  await show({ ...base, local: { ...base.local, state } }); expand();
  expect(screen.queryByRole("button", { name: /Start local model|Retry local model/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Stop local model" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Process is not responding");
  fireEvent.click(screen.getByRole("button", { name: "Stop local model" }));
  await waitFor(() => expect(api.stopLocalModel).toHaveBeenCalledTimes(2));
});

it("does not offer Stop when the local model is off or ready", async () => {
  await show(); expand();
  expect(screen.queryByRole("button", { name: "Stop local model" })).toBeNull();
});

it("says starting the local model downloads it, and how much, before anything is downloaded", async () => {
  await show({ ...base, local: { ...base.local, downloaded: false } });
  expand();
  expect(screen.getByRole("button", { name: "Download local model (2 GB)" })).toBeTruthy();
  expect(api.startLocalModel).not.toHaveBeenCalled();
  cleanup();
  await show({ ...base, local: { ...base.local, downloaded: true } });
  expand();
  expect(screen.getByRole("button", { name: "Start local model" })).toBeTruthy();
});

it("explains the setup in the selected language rather than the server's English", async () => {
  const { useLocale } = await import("@/shared/i18n/i18n");
  useLocale.getState().setLocale("ko");
  await show({ ...base, local: { ...base.local, downloaded: false } });
  expand();
  expect(screen.getByText("API 키가 없어 비전 AI 고객을 실행할 모델이 없습니다. 모델 설정에서 키를 추가하거나 로컬 모델(Small model · CPU, 최초 1회 2GB 다운로드)을 시작하세요.")).toBeTruthy();
  expect(screen.queryByText(/No API key is set/)).toBeNull();
  useLocale.getState().setLocale("en");
});
