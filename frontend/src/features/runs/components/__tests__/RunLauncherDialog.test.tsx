// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { RunLauncherDialog, type RunLauncherDialogProps } from "../RunLauncherDialog";

vi.mock("@/shared/api/client", () => ({ getEngines: vi.fn(), getTown: vi.fn(), getModels: vi.fn(), startRun: vi.fn(), estimateRun: vi.fn(), getModelSetup: vi.fn() }));
vi.mock("../ScenarioEditor", () => ({ ScenarioEditor: () => <div>Situation editor</div> }));
vi.mock("../ModelPicker", () => ({ ModelPicker: ({ onChange }: { onChange: (v: { kind: "single"; model: string }) => void }) =>
  <button type="button" onClick={() => onChange({ kind: "single", model: "text-only" })}>Select text model</button> }));

const engines: api.EngineInfo[] = [
  { engine_type: "rule_based", label: "Rules", description: "", uses_llm: false, model: "", default: true },
  { engine_type: "pattern_intent_impulse", label: "LLM", description: "", uses_llm: true, model: "text", default: false },
  { engine_type: "vlm_glance", label: "Vision", description: "", uses_llm: true, model: "vision", default: false },
];
const quick: api.RunEstimate = { customers: 1000, days: 7, per_day: 143, engine: "rule_based", model: "", local: false, model_calls: 0, minutes: 1, cost_usd: null, warn: false };
beforeEach(() => {
  vi.mocked(api.estimateRun).mockResolvedValue(quick);
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getEngines).mockResolvedValue(engines);
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.startRun).mockResolvedValue({ project_id: "p", run_id: "r", setup_id: "s" });
  vi.mocked(api.getModelSetup).mockRejectedValue(new Error("Not needed"));
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

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
  fireEvent.click(screen.getByRole("radio", { name: "All 1,000 customers across all days" }));
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

it.each(LOCALES)("sends stable engine identifiers from the $code launcher", async ({ code }) => {
  useLocale.getState().setLocale(code);
  show({ defaultEngine: "vlm_glance", personaCount: 31 });
  expect(screen.getByRole("dialog").getAttribute("aria-labelledby")).toBeTruthy();
  expect(screen.getByRole("button", { name: translate(code, "runPreview") })).toBeTruthy();
  expect((screen.getByLabelText(translate(code, "sampleSize")) as HTMLInputElement).value).toBe("30");
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ engine_type: "vlm_glance", plan_policy: "vlm", preview: true, max_customers: 30 }));
});

it.each(LOCALES)("blocks an empty sample and explains it in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  show({ defaultEngine: "vlm_glance" });
  fireEvent.change(screen.getByLabelText(translate(code, "sampleSize")), { target: { value: "" } });
  expect(screen.getByRole("alert").textContent).toBe(translate(code, "sampleError", { max: 1000 }));
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
});

it.each(LOCALES)("preserves the finalized-layout preview restriction in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  show({ locked: true, defaultEngine: "rule_based" }); expand();
  expect((screen.getByLabelText(new RegExp(translate(code, "previewRun"))) as HTMLInputElement).disabled).toBe(true);
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ preview: true, engine_type: "rule_based" }));
});

it.each(LOCALES)("explains a zero-persona store in $code without sending a request", async ({ code }) => {
  useLocale.getState().setLocale(code);
  show({ personaCount: 0, defaultEngine: "rule_based" });
  expect(screen.getByRole("status").textContent).toBe(translate(code, "addPersonasHint"));
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
});

it("keeps form edits and selection intact when switching language mid-dialog", async () => {
  show({ defaultEngine: "vlm_glance" }); expand();
  fireEvent.change(screen.getByLabelText("Sample size"), { target: { value: "17" } });
  fireEvent.change(screen.getByLabelText("Seed"), { target: { value: "21" } });
  fireEvent.change(screen.getByLabelText("Replicate"), { target: { value: "3" } });
  act(() => useLocale.getState().setLocale("ko"));
  expect((screen.getByLabelText("표본 고객 수") as HTMLInputElement).value).toBe("17");
  expect(api.startRun).not.toHaveBeenCalled();
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ engine_type: "vlm_glance", max_customers: 17, seed: 21, replicate: 3 }));
});

it("runs on a model that has a key when the server default has none", async () => {
  vi.mocked(api.getEngines).mockResolvedValue(engines.map((e) => e.engine_type === "pattern_intent_impulse"
    ? { ...e, model: "gemini/gemini-3.1-pro-preview", model_ready: false, suggested_model: "anthropic:claude-haiku-5-5" } : e));
  vi.mocked(api.getModels).mockResolvedValue([{ ref: "anthropic:claude-haiku-5-5", label: "Claude Haiku 5.5", vision: true } as api.ModelOption]);
  show({ defaultEngine: "pattern_intent_impulse" });
  expand();
  expect(await screen.findByText(/has no API key, so this run uses anthropic:claude-haiku-5-5/)).toBeTruthy();
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ model: "anthropic:claude-haiku-5-5" })));
});

it("refuses to start on a default model without a key when nothing else has one", async () => {
  vi.mocked(api.getEngines).mockResolvedValue(engines.map((e) => e.engine_type === "pattern_intent_impulse"
    ? { ...e, model: "gemini/gemini-3.1-pro-preview", model_ready: false, suggested_model: "" } : e));
  show();
  fireEvent.click(await screen.findByRole("radio", { name: /^LLM shoppers/ }));
  expect(await screen.findByText(/has no API key. Add one in Settings → Model providers, or use the rule-based preview/)).toBeTruthy();
  await submit();
  expect(api.startRun).not.toHaveBeenCalled();
});

const noKeyLlmDefault = engines.map((e) => e.engine_type === "pattern_intent_impulse"
  ? { ...e, default: true, model: "anthropic/claude-haiku-5-5", model_ready: false, suggested_model: "" } : { ...e, default: false });

it("opens on the rule-based preview when the server default engine cannot run", async () => {
  vi.mocked(api.getEngines).mockResolvedValue(noKeyLlmDefault);
  show();
  await waitFor(() => expect(api.getEngines).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByRole("radio", { name: /^Rule-based preview/ }).getAttribute("aria-checked")).toBe("true"));
  expect(screen.queryByRole("alert")).toBeNull();
  expect((screen.getByRole("button", { name: "Run preview" }) as HTMLButtonElement).disabled).toBe(false);
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ engine_type: "rule_based" })));
});

it("opens on the server default engine when it can run, with a smaller LLM sample", async () => {
  vi.mocked(api.getEngines).mockResolvedValue(engines.map((e) => ({ ...e, default: e.engine_type === "pattern_intent_impulse" })));
  show();
  await waitFor(() => expect(screen.getByRole("radio", { name: /^LLM shoppers/ }).getAttribute("aria-checked")).toBe("true"));
  expect((screen.getByLabelText("Sample size") as HTMLInputElement).value).toBe("150");
});

it("opens on a default engine without a key when another model has one", async () => {
  vi.mocked(api.getEngines).mockResolvedValue(noKeyLlmDefault.map((e) => e.engine_type === "pattern_intent_impulse" ? { ...e, suggested_model: "openai/gpt-6-luna" } : e));
  show();
  await waitFor(() => expect(screen.getByRole("radio", { name: /^LLM shoppers/ }).getAttribute("aria-checked")).toBe("true"));
});

it.each([
  ["disabled", "modelNotReadyLocalOff"], ["off", "modelNotReadyLocalStopped"], ["error", "modelNotReadyLocalStopped"],
  ["downloading", "modelNotReadyLocalPreparing"], ["starting", "modelNotReadyLocalPreparing"], ["ready", "modelNotReadyNoKey"],
] as const)("explains a model that cannot run when the local model is %s", async (state, key) => {
  vi.mocked(api.getEngines).mockResolvedValue(noKeyLlmDefault);
  vi.mocked(api.getModelSetup).mockResolvedValue({ local: { state } } as api.ModelSetup);
  useLocale.getState().setLocale("ko");
  show();
  fireEvent.click(await screen.findByRole("radio", { name: /^LLM 고객/ }));
  expect(await screen.findByText(translate("ko", key, { model: "anthropic/claude-haiku-5-5" }))).toBeTruthy();
  expect(screen.queryByText(/로컬 모델이 준비될 때까지 기다리거나/)).toBeNull();
});

it.each(LOCALES)("names the rule-based engine the same way in the card and the not-ready message in $code", ({ code }) => {
  for (const key of ["modelNotReadyNoKey", "modelNotReadyLocalOff", "modelNotReadyLocalStopped", "modelNotReadyLocalPreparing"] as const) {
    expect(translate(code, key, { model: "m" }).toLowerCase()).toContain(translate(code, "rulePreview").toLowerCase());
  }
});

it("shows no client-side estimate while the form is invalid", async () => {
  show({ defaultEngine: "pattern_intent_impulse" });
  await screen.findByText(/1,000 shoppers over 7 days/);
  fireEvent.change(screen.getByLabelText("Sample size"), { target: { value: "" } });
  expect(screen.queryByText(/shoppers over|LLM calls|server response cache|Checking time and cost/)).toBeNull();
});

it("says the layout stays finalized when previewing a finalized layout", () => {
  show({ locked: true, defaultEngine: "rule_based" });
  expect(screen.getByText(/Preview · the finalized layout stays as it is/)).toBeTruthy();
  expect(screen.queryByText(/layout stays editable/)).toBeNull();
  act(() => useLocale.getState().setLocale("ko"));
  expect(screen.getByText(/미리보기 · 확정된 배치는 그대로 유지/)).toBeTruthy();
});
