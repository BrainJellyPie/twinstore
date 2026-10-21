// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { RunLauncherDialog, type RunLauncherDialogProps } from "../RunLauncherDialog";

vi.mock("@/shared/api/client", () => ({ getEngines: vi.fn(), getTown: vi.fn(), startRun: vi.fn() }));
vi.mock("../ScenarioEditor", () => ({ ScenarioEditor: () => <div>Situation editor</div> }));
vi.mock("../ModelPicker", () => ({ ModelPicker: ({ onChange }: { onChange: (v: { kind: "single"; model: string }) => void }) =>
  <button type="button" onClick={() => onChange({ kind: "single", model: "text-only" })}>Select text model</button> }));

const engines: api.EngineInfo[] = [
  { engine_type: "rule_based", label: "Rules", description: "", uses_llm: false, model: "", default: true },
  { engine_type: "pattern_intent_impulse", label: "LLM", description: "", uses_llm: true, model: "text", default: false },
  { engine_type: "vlm_glance", label: "Vision", description: "", uses_llm: true, model: "vision", default: false },
];
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getEngines).mockResolvedValue(engines);
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.startRun).mockResolvedValue({ project_id: "p", run_id: "r", setup_id: "s" });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

function show(props: Partial<RunLauncherDialogProps> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const onOpenChange = vi.fn();
  const view = render(<QueryClientProvider client={client}><RunLauncherDialog open onOpenChange={onOpenChange} projectId="p" setupId="s" personaCount={1000} {...props} /></QueryClientProvider>);
  return { ...view, onOpenChange, client };
}
function expand() { const details = document.querySelector("details")!; details.open = true; fireEvent(details, new Event("toggle")); return details; }
async function submit() { await act(async () => { fireEvent.submit(document.querySelector("form")!); }); }

it("starts a free editable preview with the advanced controls folded", async () => {
  const { onOpenChange } = show({ defaultEngine: "rule_based" });
  expect(document.querySelector("details")!.open).toBe(false);
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ engine_type: "rule_based", preview: true, seed: 0, replicate: 0, max_customers: undefined })));
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
});

it.each([0, 1, 29, 30, 31, 300, 1000])("chooses a small vision sample at the %i-persona boundary", async (personaCount) => {
  show({ defaultEngine: "vlm_glance", personaCount });
  expect((screen.getByLabelText("Sample size") as HTMLInputElement).value).toBe(String(Math.min(30, personaCount)));
  expect((screen.getByRole("button", { name: "Run preview" }) as HTMLButtonElement).disabled).toBe(personaCount === 0);
  if (!personaCount) { await submit(); expect(api.startRun).not.toHaveBeenCalled(); return; }
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ max_customers: personaCount > 30 ? 30 : undefined, plan_policy: "vlm" })));
});

it("uses engine defaults arriving after the dialog opens", async () => {
  let resolve!: (value: api.EngineInfo[]) => void;
  vi.mocked(api.getEngines).mockReturnValue(new Promise((done) => { resolve = done; }));
  show();
  await act(async () => resolve(engines.map((e) => ({ ...e, default: e.engine_type === "vlm_glance" }))));
  await waitFor(() => expect(screen.getByRole("radio", { name: /^Vision shoppers/ }).getAttribute("aria-checked")).toBe("true"));
  expect((screen.getByLabelText("Sample size") as HTMLInputElement).value).toBe("30");
});

it("keeps the user's engine selection when server defaults arrive late", async () => {
  let resolve!: (value: api.EngineInfo[]) => void;
  vi.mocked(api.getEngines).mockReturnValue(new Promise((done) => { resolve = done; }));
  show();
  fireEvent.click(screen.getByRole("radio", { name: /^LLM shoppers/ }));
  await act(async () => resolve(engines.map((e) => ({ ...e, default: e.engine_type === "vlm_glance" }))));
  expect(screen.getByRole("radio", { name: /^LLM shoppers/ }).getAttribute("aria-checked")).toBe("true");
});

it("resets incompatible model choices and sample defaults when switching engines", async () => {
  show({ defaultEngine: "pattern_intent_impulse" });
  expand();
  fireEvent.click(screen.getByRole("button", { name: "Select text model" }));
  fireEvent.click(screen.getByRole("radio", { name: /^Vision shoppers/ }));
  expect((screen.getByLabelText("Sample size") as HTMLInputElement).value).toBe("30");
  fireEvent.click(screen.getByRole("radio", { name: /^Rule-based preview/ }));
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ model: undefined, ensemble: undefined, max_customers: undefined, plan_policy: undefined })));
});

it("keeps advanced edits when folded and makes finalization visible", async () => {
  show({ defaultEngine: "rule_based" });
  const details = expand();
  fireEvent.change(screen.getByLabelText("Seed"), { target: { value: "17" } });
  fireEvent.change(screen.getByLabelText("Replicate"), { target: { value: "2" } });
  fireEvent.click(screen.getByLabelText(/Preview run/));
  details.open = false;
  expect(screen.getByText(/Final run · locks this layout/)).toBeTruthy();
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ seed: 17, replicate: 2, preview: false })));
});

it("never finalizes a locked layout", async () => {
  show({ locked: true }); expand();
  expect((screen.getByLabelText(/Preview run/) as HTMLInputElement).disabled).toBe(true);
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ preview: true })));
});

it.each(["", "0", "-1", "1.5", "1001", "1e100"])("blocks an invalid sample (%s) even if submit is triggered directly", async (value) => {
  show({ defaultEngine: "vlm_glance" });
  fireEvent.change(screen.getByLabelText("Sample size"), { target: { value } });
  await submit();
  expect(api.startRun).not.toHaveBeenCalled();
});

it("shows a start failure and lets the user retry", async () => {
  vi.mocked(api.startRun).mockRejectedValueOnce(new Error("Server unavailable"));
  show({ defaultEngine: "rule_based" }); await submit();
  expect((await screen.findByRole("alert")).textContent).toContain("Server unavailable");
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledTimes(2));
});

it.each([
  ["Seed", ""], ["Seed", "1.5"], ["Seed", "9007199254740992"],
  ["Replicate", ""], ["Replicate", "-1"], ["Replicate", "0.5"], ["Replicate", "1e100"],
])("rejects invalid %s (%s) after the advanced settings are folded", async (label, value) => {
  show({ defaultEngine: "rule_based" });
  const details = expand();
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
  details.open = false;
  expect(screen.getByRole("alert").textContent).toContain("Advanced settings");
  expect((screen.getByRole("button", { name: "Run preview" }) as HTMLButtonElement).disabled).toBe(true);
  await submit();
  expect(api.startRun).not.toHaveBeenCalled();
});

it.each(["-1", "0", "9007199254740991"])("accepts a safe integer seed (%s)", async (seed) => {
  show({ defaultEngine: "rule_based" }); expand();
  fireEvent.change(screen.getByLabelText("Seed"), { target: { value: seed } });
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ seed: Number(seed) }));
});

it("ignores an invalid inactive sample when all customers are chosen", async () => {
  show({ defaultEngine: "vlm_glance" });
  fireEvent.change(screen.getByLabelText("Sample size"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("radio", { name: "All 1,000 personas" }));
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ max_customers: undefined }));
});

it("prevents duplicate submission and disables edits while starting", async () => {
  let resolve!: (value: { project_id: string; run_id: string; setup_id: string }) => void;
  vi.mocked(api.startRun).mockReturnValue(new Promise((done) => { resolve = done; }));
  show({ defaultEngine: "rule_based" }); expand();
  await submit();
  await screen.findByRole("button", { name: "Starting…" });
  expect((screen.getByLabelText("Seed") as HTMLInputElement).closest("fieldset")!.disabled).toBe(true);
  await submit();
  expect(api.startRun).toHaveBeenCalledOnce();
  await act(async () => resolve({ project_id: "p", setup_id: "s", run_id: "r" }));
});
