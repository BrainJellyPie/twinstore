// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { CapturePage } from "../CapturePage";

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  listCaptures: vi.fn(), getCapture: vi.fn(), getModels: vi.fn(), getSetups: vi.fn(), getProject: vi.fn(),
}));
vi.mock("../ShelfLab", () => ({ BeforeAfter: () => null, ShelfLabPanel: () => null }));
vi.mock("../RivalCard", () => ({ RivalCard: () => null }));
const clients: QueryClient[] = [];
const status: api.CaptureStatus = {
  capture_id: "cap_test", status: "completed", stage: "done", progress: 1, error: "",
  options: { detector: "classic", model: "none", currency: "USD", rack_type: "shelf", label: "Tea" },
  image_name: "shelf.png", image_size: [100, 100], created_at: "", finished_at: "",
  items: 0, facings: 0, gaps: 0, levels: 0, applied_setup_ids: [],
};
const view: api.CaptureView = { status, result: null };
beforeEach(() => {
  vi.mocked(api.listCaptures).mockResolvedValue([status]);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.getSetups).mockResolvedValue([]);
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  client.setQueryData(["projects", "project"], { metadata: { currency: "USD" } });
  render(<QueryClientProvider client={client}><CapturePage projectId="project" /></QueryClientProvider>);
  return client;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

it.each(["Capture no longer exists", "Network connection lost"])("explains an initial load failure and retries the same capture: %s", async (message) => {
  vi.mocked(api.getCapture).mockRejectedValueOnce(new Error(message)).mockResolvedValue(view);
  mount();
  expect((await screen.findByRole("alert")).textContent).toContain(message);
  fireEvent.click(screen.getByRole("button", { name: "Retry capture" }));
  await screen.findByRole("img", { name: "Shelf photo" });
  expect(api.getCapture).toHaveBeenLastCalledWith("project", "cap_test", expect.any(AbortSignal));
  expect(api.getCapture).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("alert")).toBeNull();
});

it("prevents duplicate retries while a recovery request is pending", async () => {
  const pending = deferred<api.CaptureView>();
  vi.mocked(api.getCapture).mockRejectedValueOnce(new Error("Unavailable")).mockReturnValue(pending.promise);
  mount(); await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry capture" }));
  expect((await screen.findByRole("status")).textContent).toContain("Loading capture");
  expect(screen.queryByRole("button", { name: "Retry capture" })).toBeNull();
  expect(api.getCapture).toHaveBeenCalledTimes(2);
  await act(async () => { pending.resolve(view); });
  await screen.findByRole("img", { name: "Shelf photo" });
});

it("keeps loaded capture content visible after a refresh failure and clears the error on retry", async () => {
  vi.mocked(api.getCapture).mockResolvedValue(view);
  const client = mount(); await screen.findByRole("img", { name: "Shelf photo" });
  vi.mocked(api.getCapture).mockRejectedValueOnce(new Error("Refresh failed"));
  await act(async () => { await client.invalidateQueries({ queryKey: ["projects", "project", "captures", "cap_test"] }); });
  expect((await screen.findByRole("alert")).textContent).toContain("Refresh failed");
  expect(screen.getByRole("img", { name: "Shelf photo" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Retry capture" }));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(screen.getByRole("img", { name: "Shelf photo" })).toBeTruthy();
});

it("stops status polling after a failed request until the user retries", async () => {
  vi.mocked(api.getCapture).mockRejectedValue(new Error("Unavailable"));
  mount(); await screen.findByRole("alert");
  const calls = vi.mocked(api.getCapture).mock.calls.length;
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1400)); });
  expect(api.getCapture).toHaveBeenCalledTimes(calls);
});

it("lets the user leave a failed capture without losing the history strip", async () => {
  vi.mocked(api.getCapture).mockRejectedValue(new Error("Unavailable"));
  mount(); await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "New photo" }));
  await screen.findByText("Choose a photo");
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByTitle("shelf.png")).toBeTruthy();
});

it("disables retry while refreshing an already loaded capture", async () => {
  const pending = deferred<api.CaptureView>();
  vi.mocked(api.getCapture).mockResolvedValueOnce(view).mockRejectedValueOnce(new Error("Refresh failed")).mockReturnValue(pending.promise);
  const client = mount(); await screen.findByRole("img", { name: "Shelf photo" });
  await act(async () => { await client.invalidateQueries({ queryKey: ["projects", "project", "captures", "cap_test"] }); });
  fireEvent.click(await screen.findByRole("button", { name: "Retry capture" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Retry capture" }) as HTMLButtonElement).disabled).toBe(true));
  fireEvent.click(screen.getByRole("button", { name: "Retry capture" }));
  expect(api.getCapture).toHaveBeenCalledTimes(3);
  expect(screen.getByRole("img", { name: "Shelf photo" })).toBeTruthy();
  await act(async () => { pending.resolve(view); });
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

it("resumes polling after recovery and stops when the capture finishes", async () => {
  vi.mocked(api.getCapture).mockRejectedValueOnce(new Error("Connection lost"))
    .mockResolvedValueOnce({ status: { ...status, status: "running", stage: "reading" }, result: null }).mockResolvedValue(view);
  const client = mount(); await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry capture" }));
  await waitFor(() => expect(client.getQueryData<api.CaptureView>(["projects", "project", "captures", "cap_test"])?.status.status).toBe("completed"), { timeout: 2500 });
  expect(api.getCapture).toHaveBeenCalledTimes(3);
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 1400)); });
  expect(api.getCapture).toHaveBeenCalledTimes(3);
});

it("ignores the previous photo's recovery result after selecting another capture", async () => {
  const pending = deferred<api.CaptureView>();
  const second: api.CaptureView = { ...view, status: { ...status, capture_id: "cap_second", image_name: "second.png" } };
  vi.mocked(api.listCaptures).mockResolvedValue([status, second.status]);
  vi.mocked(api.getCapture).mockRejectedValueOnce(new Error("Unavailable"))
    .mockImplementation((_pid, cid) => cid === "cap_test" ? pending.promise : Promise.resolve(second));
  mount(); await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry capture" }));
  await waitFor(() => expect(api.getCapture).toHaveBeenCalledTimes(2));
  fireEvent.click(screen.getByTitle("second.png"));
  expect((await screen.findByRole("img", { name: "Shelf photo" })).getAttribute("src")).toContain("cap_second");
  await act(async () => { pending.resolve(view); });
  expect(screen.getByRole("img", { name: "Shelf photo" }).getAttribute("src")).toContain("cap_second");
  expect(screen.queryByRole("alert")).toBeNull();
});
