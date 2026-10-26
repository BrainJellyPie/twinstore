// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { BASELINE_SCENARIO } from "../../scenarioDefaults";
import { RunLauncherDialog } from "../RunLauncherDialog";

vi.mock("@/shared/api/client", () => ({ getEngines: vi.fn(), getLayoutOperations: vi.fn(), getTown: vi.fn(), getModels: vi.fn(), startRun: vi.fn(), estimateRun: vi.fn(), getModelSetup: vi.fn() }));
// The situation chosen in the editor: a custom day the user has not named, the ordinary-day preset, or a named one.
vi.mock("../ScenarioEditor", () => ({ ScenarioEditor: ({ onChange }: { onChange: (s: api.Scenario) => void }) => <>
  <button type="button" onClick={() => onChange({ ...BASELINE_SCENARIO, weather: "rain" })}>Custom day</button>
  <button type="button" onClick={() => onChange({ ...BASELINE_SCENARIO, id: "baseline", name: "Ordinary day" })}>Ordinary day preset</button>
  <button type="button" onClick={() => onChange({ ...BASELINE_SCENARIO, name: "Rainy Friday" })}>Named day</button>
</> }));

beforeEach(() => {
  vi.mocked(api.getLayoutOperations).mockResolvedValue({ operations: null });
  vi.mocked(api.getEngines).mockResolvedValue([{ engine_type: "rule_based", label: "Rules", description: "", uses_llm: false, model: "", default: true }]);
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.estimateRun).mockReturnValue(new Promise(() => {}));
  vi.mocked(api.getModelSetup).mockReturnValue(new Promise(() => {}));
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); vi.unstubAllGlobals(); });

it("names the chosen situation in the selected language unless the user named it", async () => {
  useLocale.getState().setLocale("ko");
  render(<QueryClientProvider client={new QueryClient()}><RunLauncherDialog open onOpenChange={vi.fn()} projectId="p" setupId="s" personaCount={10} /></QueryClientProvider>);
  const summary = () => document.querySelector("p[aria-live=polite]")!.textContent;
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Custom day" })));
  expect(summary()).toContain("직접 설정한 상황");
  fireEvent.click(screen.getByRole("button", { name: "Ordinary day preset" }));
  expect(summary()).not.toContain("Ordinary day");
  fireEvent.click(screen.getByRole("button", { name: "Named day" }));
  expect(summary()).toContain("Rainy Friday");
});
