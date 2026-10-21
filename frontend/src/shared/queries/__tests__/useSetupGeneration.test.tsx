// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import * as api from "@/shared/api/client";
import type { GenerationListItem, GenerationStatus } from "@/shared/types/domain";
import { useSetupGeneration } from "../useSetupGeneration";
import { queryKeys } from "../keys";

vi.mock("@/shared/api/client", () => ({ getSetupGenerations: vi.fn(), getGenerationStatus: vi.fn(), regeneratePersona: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => { vi.mocked(api.getSetupGenerations).mockResolvedValue([]); });
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.resetAllMocks(); });
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (error: Error) => void; const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; }); return { promise, resolve, reject }; }
const job = (patch: Partial<GenerationListItem> = {}): GenerationListItem => ({ gen_id: "raw-generation", setup_id: "raw-layout", kind: "persona", status: "failed", error: "Generation failed", progress: null, created_at: null, updated_at: null, ...patch });
function mount(initialGenId?: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { ...renderHook(({ pid, sid, gen }) => useSetupGeneration(pid, sid, gen), { wrapper, initialProps: { pid: "raw-project", sid: "raw-layout", gen: initialGenId } }), invalidate };
}

it("retries a history read failure with GET only and coalesces rapid retry clicks", async () => {
  const pending = deferred<GenerationListItem[]>();
  vi.mocked(api.getSetupGenerations).mockRejectedValueOnce(new Error("History offline")).mockReturnValueOnce(pending.promise);
  const { result } = mount(); await waitFor(() => expect(result.current.error).toBe("History offline"));
  act(() => { result.current.retry(); result.current.retry(); });
  expect(api.regeneratePersona).not.toHaveBeenCalled(); expect(api.getSetupGenerations).toHaveBeenCalledTimes(2);
  await act(async () => pending.resolve([]));
  expect(result.current.phase).toBe("idle"); expect(result.current.error).toBeNull(); expect(result.current.retrying).toBe(false);
});

it("does not start generation before the initial history read completes", async () => {
  const pending = deferred<GenerationListItem[]>(); vi.mocked(api.getSetupGenerations).mockReturnValue(pending.promise);
  const { result } = mount(); act(() => result.current.retry());
  expect(api.regeneratePersona).not.toHaveBeenCalled();
  await act(async () => pending.resolve([]));
  vi.mocked(api.regeneratePersona).mockResolvedValue({ gen_id: "new-personas" }); vi.mocked(api.getGenerationStatus).mockReturnValue(new Promise(() => {}));
  act(() => result.current.retry()); await waitFor(() => expect(api.regeneratePersona).toHaveBeenCalledOnce());
  expect(api.regeneratePersona).toHaveBeenCalledWith("raw-project", "raw-layout");
});

it.each(["layout", "persona"] as const)("reloads a failed %s progress read without restarting or deleting generation", async (kind) => {
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job({ kind, status: "running" })]);
  vi.mocked(api.getGenerationStatus).mockRejectedValueOnce(new Error("Status offline")).mockResolvedValueOnce(job({ kind, status: "running", error: null }));
  const { result } = mount(); await waitFor(() => expect(result.current.error).toBe("Status offline"));
  act(() => result.current.retry()); await waitFor(() => expect(result.current.phase).toBe(kind));
  expect(api.getGenerationStatus).toHaveBeenCalledTimes(2); expect(api.getGenerationStatus).toHaveBeenLastCalledWith("raw-project", "raw-layout", "raw-generation");
  expect(api.regeneratePersona).not.toHaveBeenCalled(); expect(result.current.error).toBeNull();
});

it("reads an explicit initial generation ID instead of leaving it idle", async () => {
  vi.mocked(api.getGenerationStatus).mockResolvedValue(job({ status: "completed", error: null }));
  const { result } = mount("initial/raw-id"); await waitFor(() => expect(result.current.phase).toBe("completed"));
  expect(api.getGenerationStatus).toHaveBeenCalledWith("raw-project", "raw-layout", "initial/raw-id"); expect(api.getSetupGenerations).not.toHaveBeenCalled();
});

it("coalesces actual failed-persona retries and ignores retry while already running", async () => {
  const pending = deferred<{ gen_id: string }>(); vi.mocked(api.getSetupGenerations).mockResolvedValue([job()]);
  vi.mocked(api.regeneratePersona).mockReturnValue(pending.promise); vi.mocked(api.getGenerationStatus).mockReturnValue(new Promise(() => {}));
  const { result } = mount(); await waitFor(() => expect(result.current.phase).toBe("failed"));
  act(() => { result.current.retry(); result.current.retry(); }); expect(api.regeneratePersona).toHaveBeenCalledOnce();
  await act(async () => pending.resolve({ gen_id: "new-personas" }));
  act(() => result.current.retry()); expect(api.regeneratePersona).toHaveBeenCalledOnce(); expect(result.current.kind).toBe("persona");
});

it("preserves the unsupported layout-regeneration guard for a real job failure", async () => {
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job({ kind: "layout" })]); const { result } = mount();
  await waitFor(() => expect(result.current.phase).toBe("failed")); expect(() => result.current.retry()).toThrow(/Layout regeneration is not supported/);
  expect(api.regeneratePersona).not.toHaveBeenCalled();
});

it.each(["history", "status", "retry"] as const)("ignores a late %s response after switching layout in the same hook", async (source) => {
  const history = deferred<GenerationListItem[]>(), status = deferred<GenerationStatus>(), retry = deferred<{ gen_id: string }>();
  vi.mocked(api.getSetupGenerations).mockImplementation(async (_pid, sid) => sid === "new-layout" ? [] : source === "history" ? history.promise : [job({ status: source === "status" ? "running" : "failed" })]);
  vi.mocked(api.getGenerationStatus).mockReturnValue(status.promise); vi.mocked(api.regeneratePersona).mockReturnValue(retry.promise);
  const { result, rerender, invalidate } = mount();
  if (source === "retry") { await waitFor(() => expect(result.current.phase).toBe("failed")); act(() => result.current.retry()); }
  if (source === "status") await waitFor(() => expect(api.getGenerationStatus).toHaveBeenCalled());
  rerender({ pid: "raw-project", sid: "new-layout", gen: undefined }); await waitFor(() => expect(result.current.phase).toBe("idle"));
  await act(async () => { history.resolve([job()]); status.resolve(job({ status: "completed" })); retry.resolve({ gen_id: "old-retry" }); });
  expect(result.current.phase).toBe("idle"); expect(result.current.currentGenId).toBeNull(); expect(result.current.error).toBeNull();
  expect(invalidate).not.toHaveBeenCalled(); expect(api.getGenerationStatus).not.toHaveBeenCalledWith("raw-project", "new-layout", "old-retry");
});

it("ignores late retry rejection after unmount", async () => {
  const pending = deferred<{ gen_id: string }>(); vi.mocked(api.getSetupGenerations).mockResolvedValue([job()]); vi.mocked(api.regeneratePersona).mockReturnValue(pending.promise);
  const { result, unmount, invalidate } = mount(); await waitFor(() => expect(result.current.phase).toBe("failed"));
  act(() => result.current.retry()); unmount(); await act(async () => pending.reject(new Error("Late error")));
  expect(invalidate).not.toHaveBeenCalled();
});

it("follows a completed layout to personas and refreshes only the matching project and layout", async () => {
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job({ kind: "layout", status: "completed", progress: { next_gen_id: "next-personas" } })]);
  vi.mocked(api.getGenerationStatus).mockResolvedValue(job({ kind: "persona", status: "completed", error: null }));
  const { result, invalidate } = mount(); await waitFor(() => expect(result.current.phase).toBe("completed"));
  expect(result.current.currentGenId).toBe("next-personas"); expect(api.getGenerationStatus).toHaveBeenCalledWith("raw-project", "raw-layout", "next-personas");
  expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.project("raw-project") }); expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.setup("raw-project", "raw-layout") });
});

it("keeps repeated history errors on the read-only recovery path until history is known", async () => {
  vi.mocked(api.getSetupGenerations).mockRejectedValueOnce(new Error("First outage")).mockRejectedValueOnce("Second outage").mockResolvedValueOnce([job()]);
  const { result } = mount(); await waitFor(() => expect(result.current.error).toBe("First outage"));
  expect(result.current.errorSource).toBe("status"); act(() => result.current.retry());
  await waitFor(() => expect(result.current.error).toBe("Second outage")); act(() => result.current.retry());
  await waitFor(() => expect(result.current.error).toBe("Generation failed")); expect(result.current.errorSource).toBe("generation");
  expect(api.regeneratePersona).not.toHaveBeenCalled();
});

it("keeps a failed generation POST retryable without labeling it a status read failure", async () => {
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job()]); vi.mocked(api.regeneratePersona).mockRejectedValueOnce(new Error("Cannot start customers"));
  const { result } = mount(); await waitFor(() => expect(result.current.phase).toBe("failed")); act(() => result.current.retry());
  await waitFor(() => expect(result.current.error).toBe("Cannot start customers"));
  expect(result.current.errorSource).toBe("generation"); expect(result.current.retrying).toBe(false);
});

it("reconciles a completed layout without an automatic customer task", async () => {
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job({ kind: "layout", status: "completed", progress: null })]);
  const { result, invalidate } = mount(); await waitFor(() => expect(result.current.loadingStatus).toBe(false));
  expect(result.current.phase).toBe("idle"); expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.setup("raw-project", "raw-layout") });
  expect(api.regeneratePersona).not.toHaveBeenCalled(); expect(api.getGenerationStatus).not.toHaveBeenCalled();
});

it("ignores a late progress-reload rejection after switching projects with the same layout ID", async () => {
  const pending = deferred<GenerationListItem[]>(); vi.mocked(api.getSetupGenerations).mockRejectedValueOnce(new Error("Offline")).mockReturnValueOnce(pending.promise).mockResolvedValueOnce([]);
  const { result, rerender } = mount(); await waitFor(() => expect(result.current.errorSource).toBe("status")); act(() => result.current.retry());
  rerender({ pid: "another-project", sid: "raw-layout", gen: undefined }); await waitFor(() => expect(result.current.loadingStatus).toBe(false));
  await act(async () => pending.reject(new Error("Old retry failed"))); expect(result.current.phase).toBe("idle"); expect(result.current.error).toBeNull();
  expect(api.regeneratePersona).not.toHaveBeenCalled();
});

it("polls at the normal interval without overlapping an unresolved status request", async () => {
  vi.useFakeTimers();
  try {
    const pending = deferred<GenerationStatus>(); vi.mocked(api.getSetupGenerations).mockResolvedValue([job({ status: "running" })]);
    vi.mocked(api.getGenerationStatus).mockResolvedValueOnce(job({ status: "running" })).mockReturnValueOnce(pending.promise);
    const { result } = mount(); await act(async () => {}); await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(api.getGenerationStatus).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(2999)); expect(api.getGenerationStatus).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(1)); expect(api.getGenerationStatus).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTimeAsync(12000)); act(() => result.current.retry());
    expect(api.getGenerationStatus).toHaveBeenCalledTimes(2); expect(api.regeneratePersona).not.toHaveBeenCalled();
    await act(async () => pending.resolve(job({ status: "completed", error: null }))); expect(result.current.phase).toBe("completed");
  } finally { vi.useRealTimers(); }
});
