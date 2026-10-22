// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { photographShelves } from "../../shelfPhotos";
import { RunLauncherDialog } from "../RunLauncherDialog";

vi.mock("@/shared/api/client", () => ({ getEngines: vi.fn(), getTown: vi.fn(), getModels: vi.fn(), startRun: vi.fn(), estimateRun: vi.fn() }));
vi.mock("../../shelfPhotos", () => ({ photographShelves: vi.fn() }));
vi.mock("../ScenarioEditor", () => ({ ScenarioEditor: () => <div>Situation editor</div> }));
vi.mock("../ModelPicker", () => ({ ModelPicker: () => null }));

const engines: api.EngineInfo[] = [
  { engine_type: "rule_based", label: "Rules", description: "", uses_llm: false, model: "", default: false },
  { engine_type: "vlm_glance", label: "Vision", description: "", uses_llm: true, model: "vision", default: true },
];
const quick: api.RunEstimate = { customers: 40, days: 7, per_day: 6, engine: "rule_based", model: "", local: false, model_calls: 0, minutes: 1, cost_usd: null, warn: false };
beforeEach(() => {
  vi.mocked(api.estimateRun).mockResolvedValue(quick);
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getEngines).mockResolvedValue(engines);
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.startRun).mockResolvedValue({ project_id: "p", run_id: "r", setup_id: "s" });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const onOpenChange = vi.fn();
  render(<QueryClientProvider client={client}><RunLauncherDialog open onOpenChange={onOpenChange} projectId="p" setupId="s" personaCount={40} defaultEngine="vlm_glance" /></QueryClientProvider>);
  const details = document.querySelector("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  return { onOpenChange };
}
async function submit() { await act(async () => { fireEvent.submit(document.querySelector("form")!); }); }

it("runs on the chart by default without photographing anything", async () => {
  show();
  expect(screen.getByRole("button", { name: /^Chart(?! \+)/ }).getAttribute("aria-pressed")).toBe("true");
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ shelf_view: "chart" })));
  expect(photographShelves).not.toHaveBeenCalled();
});

it("photographs the shelves first, shows progress, then starts the photo run", async () => {
  let finish!: () => void;
  vi.mocked(photographShelves).mockImplementation(async (_p, _s, onProgress) => {
    onProgress(0, 3);
    onProgress(2, 3);
    await new Promise<void>((done) => { finish = done; });
    onProgress(3, 3);
    return 3;
  });
  const { onOpenChange } = show();
  fireEvent.click(screen.getByRole("button", { name: /Chart \+ 3D photo/ }));
  await submit();
  await waitFor(() => expect(screen.getByRole("status").textContent).toBe("Photographing shelves 2/3…"));
  expect(api.startRun).not.toHaveBeenCalled();
  expect((screen.getByRole("button", { name: "Photographing shelves 2/3…" }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => finish());
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ shelf_view: "photo_chart", engine_type: "vlm_glance" })));
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  expect(photographShelves).toHaveBeenCalledWith("p", "s", expect.any(Function), expect.any(AbortSignal));
});

it("does not start the run when the shelves cannot be photographed", async () => {
  vi.mocked(photographShelves).mockRejectedValue(new Error("WebGL is not available."));
  show();
  fireEvent.click(screen.getByRole("button", { name: /Chart \+ 3D photo/ }));
  await submit();
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("WebGL is not available."));
  expect(screen.getByRole("alert").textContent).toContain("Choose Chart");
  expect(api.startRun).not.toHaveBeenCalled();
  // Choosing the chart clears the message and runs without photos.
  fireEvent.click(screen.getByRole("button", { name: /^Chart(?! \+)/ }));
  expect(screen.queryByRole("alert")).toBeNull();
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ shelf_view: "chart" })));
});

it("stops photographing when the dialog closes", async () => {
  let seen: AbortSignal | undefined;
  vi.mocked(photographShelves).mockImplementation((_p, _s, _progress, signal) => {
    seen = signal;
    return new Promise((_done, fail) => signal?.addEventListener("abort", () => fail(new DOMException("cancelled", "AbortError"))));
  });
  show();
  fireEvent.click(screen.getByRole("button", { name: /Chart \+ 3D photo/ }));
  await submit();
  await waitFor(() => expect(seen).toBeDefined());
  cleanup();
  expect(seen!.aborted).toBe(true);
  expect(api.startRun).not.toHaveBeenCalled();
});
