// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { photographShelves } from "../../shelfPhotos";
import { RunLauncherDialog, type RunLauncherDialogProps } from "../RunLauncherDialog";

vi.mock("@/shared/api/client", () => ({ getEngines: vi.fn(), getTown: vi.fn(), getModels: vi.fn(), startRun: vi.fn(), estimateRun: vi.fn() }));
vi.mock("../../shelfPhotos", () => ({ photographShelves: vi.fn() }));
vi.mock("../ScenarioEditor", () => ({ ScenarioEditor: () => <div>Situation editor</div> }));
vi.mock("../ModelPicker", () => ({ ModelPicker: () => null }));

const engines: api.EngineInfo[] = [
  { engine_type: "rule_based", label: "Rules", description: "", uses_llm: false, model: "", default: true },
  { engine_type: "pattern_intent_impulse", label: "LLM", description: "", uses_llm: true, model: "text", default: false },
  { engine_type: "vlm_glance", label: "Vision", description: "", uses_llm: true, model: "vision", default: false },
];
const quick: api.RunEstimate = { customers: 140, days: 7, per_day: 20, engine: "rule_based", model: "", local: false, model_calls: 0, minutes: 0.3, cost_usd: null, warn: false };
const costly: api.RunEstimate = {
  customers: 3640, days: 7, per_day: 520, engine: "pattern_intent_impulse", model: "anthropic/claude-haiku-5-5", local: false,
  model_calls: 10920, minutes: 25, cost_usd: 1.8, warn: true,
};
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getEngines).mockResolvedValue(engines);
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.startRun).mockResolvedValue({ project_id: "p", run_id: "r", setup_id: "s" });
  vi.mocked(api.estimateRun).mockResolvedValue(quick);
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

function show(props: Partial<RunLauncherDialogProps> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const onOpenChange = vi.fn();
  render(<QueryClientProvider client={client}><RunLauncherDialog open onOpenChange={onOpenChange} projectId="p" setupId="s" personaCount={140} defaultEngine="rule_based" {...props} /></QueryClientProvider>);
  return { onOpenChange };
}
async function submit() { await act(async () => { fireEvent.submit(document.querySelector("form")!); }); }

it("shows the customers as a total over the days with time and cost, from the same body the run sends", async () => {
  show();
  expect(await screen.findByText("140 shoppers over 7 days (about 20 a day) · about 1 min, no model calls")).toBeTruthy();
  expect(screen.getByRole("radio", { name: "All 140 customers across all days" })).toBeTruthy();
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledOnce());
  const sent = vi.mocked(api.startRun).mock.calls[0]![2];
  expect(api.estimateRun).toHaveBeenCalledWith("p", "s", sent, expect.any(AbortSignal));
});

it("runs a quick choice directly without asking", async () => {
  const { onOpenChange } = show();
  await screen.findByText(/140 shoppers over 7 days/);
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ engine_type: "rule_based" })));
  expect(screen.queryByRole("alertdialog")).toBeNull();
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
});

it("asks before a long or costly run and starts it only on Run anyway", async () => {
  vi.mocked(api.estimateRun).mockResolvedValue(costly);
  const { onOpenChange } = show({ defaultEngine: "pattern_intent_impulse", personaCount: 3640 });
  expect(await screen.findByText("3,640 shoppers over 7 days (about 520 a day) · about 25 min · about $1.80")).toBeTruthy();
  await submit();
  const warning = await screen.findByRole("alertdialog", { name: "This run is long or costly" });
  expect(api.startRun).not.toHaveBeenCalled();
  expect(warning.textContent).toContain("3,640 shoppers over 7 days (about 520 a day)");
  expect(warning.textContent).toContain("anthropic/claude-haiku-5-5");
  expect(warning.textContent).toContain("10,920");
  expect(warning.textContent).toContain("about 25 min");
  expect(warning.textContent).toContain("about $1.80");
  expect(warning.textContent).toContain("rule-based preview");
  fireEvent.click(within(warning).getByRole("button", { name: "Run anyway" }));
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ engine_type: "pattern_intent_impulse" })));
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
});

it("goes back to the settings without starting anything", async () => {
  vi.mocked(api.estimateRun).mockResolvedValue(costly);
  const { onOpenChange } = show({ defaultEngine: "pattern_intent_impulse", personaCount: 3640 });
  await screen.findByText(/about \$1\.80/);
  await submit();
  fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Go back" }));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(api.startRun).not.toHaveBeenCalled();
  expect(onOpenChange).not.toHaveBeenCalled();
  expect((screen.getByRole("button", { name: "Run preview" }) as HTMLButtonElement).disabled).toBe(false);
});

it("waits for an estimate it does not have yet before deciding", async () => {
  let resolve!: (value: api.RunEstimate) => void;
  vi.mocked(api.estimateRun).mockReturnValue(new Promise((done) => { resolve = done; }));
  show({ defaultEngine: "pattern_intent_impulse", personaCount: 3640 });
  await submit();
  expect((screen.getByRole("button", { name: "Checking time and cost…" }) as HTMLButtonElement).disabled).toBe(true);
  expect(api.startRun).not.toHaveBeenCalled();
  await act(async () => resolve(costly));
  expect(await screen.findByRole("alertdialog")).toBeTruthy();
  expect(api.startRun).not.toHaveBeenCalled();
});

it("does not block the run when the estimate fails", async () => {
  vi.mocked(api.estimateRun).mockRejectedValue(new Error("Estimate unavailable"));
  show();
  await waitFor(() => expect(api.estimateRun).toHaveBeenCalled());
  await waitFor(() => expect(screen.queryByText(translate("en", "checkingEstimate"))).toBeNull());
  expect(screen.queryByText("Instant — 140 customers, no API cost.")).toBeNull();
  expect(screen.queryByText(/shoppers over/)).toBeNull();
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledOnce());
  expect(screen.queryByRole("alertdialog")).toBeNull();
});

it.each([400, 404])("hides the estimate line when there is nothing to estimate (%i) and still runs", async (status) => {
  vi.mocked(api.estimateRun).mockRejectedValue(new ApiError("No customers yet", status));
  show();
  await waitFor(() => expect(api.estimateRun).toHaveBeenCalled());
  await waitFor(() => expect(screen.queryByText("Instant — 140 customers, no API cost.")).toBeNull());
  expect(screen.queryByText(/shoppers over/)).toBeNull();
  await submit();
  await waitFor(() => expect(api.startRun).toHaveBeenCalledOnce());
});

it("photographs the shelves only after a costly photo run is confirmed", async () => {
  vi.mocked(api.estimateRun).mockResolvedValue({ ...costly, engine: "vlm_glance" });
  vi.mocked(photographShelves).mockResolvedValue(3);
  show({ defaultEngine: "vlm_glance", personaCount: 30 });
  const details = document.querySelector("details")!; details.open = true; fireEvent(details, new Event("toggle"));
  fireEvent.click(screen.getByRole("button", { name: /Chart \+ 3D photo/ }));
  await submit();
  const warning = await screen.findByRole("alertdialog");
  expect(photographShelves).not.toHaveBeenCalled();
  fireEvent.click(within(warning).getByRole("button", { name: "Run anyway" }));
  await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ shelf_view: "photo_chart" })));
  expect(photographShelves).toHaveBeenCalledOnce();
});

it("asks in Korean", async () => {
  useLocale.getState().setLocale("ko");
  vi.mocked(api.estimateRun).mockResolvedValue(costly);
  show({ defaultEngine: "pattern_intent_impulse", personaCount: 3640 });
  expect(await screen.findByText("7일간 고객 3,640명 (하루 약 520명) · 약 25분 · 약 $1.80")).toBeTruthy();
  await submit();
  const warning = await screen.findByRole("alertdialog", { name: "오래 걸리거나 비용이 드는 실행입니다" });
  expect(within(warning).getByRole("button", { name: "그래도 실행" })).toBeTruthy();
  expect(within(warning).getByRole("button", { name: "돌아가기" })).toBeTruthy();
});
