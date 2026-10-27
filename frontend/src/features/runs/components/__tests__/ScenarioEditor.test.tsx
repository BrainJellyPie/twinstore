// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import * as api from "@/shared/api/client";
import { setupWithKey } from "@/features/settings/__tests__/modelSetupWithKey";
import type { Scenario } from "@/shared/api/client";
import { ScenarioEditor } from "../ScenarioEditor";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  getScenarios: vi.fn().mockResolvedValue([]),
  previewScenario: vi.fn().mockResolvedValue({ situation: "Rain.", traffic: 0.85, traffic_by_hour: {}, demand: {}, impulse: 1, dwell: 1.1, walkout: 1, budget: 1, quantity: 1 }),
  describeScenario: vi.fn(),
  getModelSetup: vi.fn(),
}));
vi.mock("@tanstack/react-router", async (original) => ({
  ...await original<typeof import("@tanstack/react-router")>(), Link: ({ children }: { children: React.ReactNode }) => <a href="/settings">{children}</a>,
}));
beforeEach(() => { vi.mocked(api.getModelSetup).mockResolvedValue(setupWithKey); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const TEXT = "Rainy Friday, 1+1 on Pepsi";
const DESCRIBED: Scenario = {
  id: "custom", name: "Rainy deal day", description: TEXT, weather: "rain", temperature_c: 14, season: null,
  day_type: "weekday", only_days: [5], traffic_multiplier: 1, hourly_traffic: {}, crowding: "normal", events: [],
  promotions: [{ target: "Pepsi", kind: "1+1", discount_pct: 20, label: "1+1" }], stockouts: [], budget_multiplier: 1,
  music: "none", lighting: "normal", notes: "",
};

function Harness({ onChange }: { onChange: (s: Scenario | null) => void }) {
  const [value, setValue] = useState<Scenario | null>(null);
  return <ScenarioEditor value={value} onChange={(s) => { setValue(s); onChange(s); }} projectId="p" setupId="s" />;
}

it("sets up a described day, opens the details and shows what did not match", async () => {
  vi.mocked(api.describeScenario).mockResolvedValue({ scenario: DESCRIBED, effects: {} as api.ScenarioEffects,
    warnings: ['No product matches the stock-out "Ice"; it was left out.'] });
  const changed = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}><Harness onChange={changed} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Describe the day"), { target: { value: TEXT } });
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
  await waitFor(() => expect(changed).toHaveBeenCalledWith(DESCRIBED));
  expect(api.describeScenario).toHaveBeenCalledWith({ text: TEXT, project_id: "p", setup_id: "s" });
  expect(screen.getByText(/No product matches the stock-out "Ice"/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Hide details" })).toBeTruthy();
  expect((screen.getByPlaceholderText("product, word or rack") as HTMLInputElement).value).toBe("Pepsi");
  expect(screen.getByRole("option", { name: "Rainy deal day" })).toBeTruthy();
  // Editing a field keeps the described name.
  fireEvent.change(screen.getByRole("slider", { name: "Temperature" }), { target: { value: "30" } });
  expect(changed.mock.lastCall?.[0]?.name).toBe("Rainy deal day");
  // A local event's chip says whether it is on.
  fireEvent.click(screen.getByRole("button", { name: "Payday", pressed: false }));
  expect(screen.getByRole("button", { name: "Payday", pressed: true })).toBeTruthy();
});

it("shows why a day could not be set up", async () => {
  vi.mocked(api.describeScenario).mockRejectedValue(new Error("The situation could not be set up: the model took too long to reply. Try again."));
  render(<QueryClientProvider client={new QueryClient()}><Harness onChange={vi.fn()} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Describe the day"), { target: { value: TEXT } });
  fireEvent.keyDown(screen.getByLabelText("Describe the day"), { key: "Enter" });
  expect((await screen.findByRole("alert")).textContent).toContain("took too long");
});

it("offers model setup when no model can set up a described day", async () => {
  vi.mocked(api.getModelSetup).mockResolvedValue({ cloud_providers: [], local: { state: "stopped", downloaded: true, progress: null } } as unknown as api.ModelSetup);
  vi.mocked(api.describeScenario).mockRejectedValue(new Error("No model API key is set."));
  render(<QueryClientProvider client={new QueryClient()}><Harness onChange={vi.fn()} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Describe the day"), { target: { value: TEXT } });
  fireEvent.keyDown(screen.getByLabelText("Describe the day"), { key: "Enter" });
  expect((await screen.findByRole("alert")).textContent).toBe("No model API key is set.");
  expect(await screen.findByTestId("needs-model")).toBeTruthy();
});

it("does not submit the run dialog's form it sits in", async () => {
  vi.mocked(api.describeScenario).mockResolvedValue({ scenario: DESCRIBED, effects: {} as api.ScenarioEffects, warnings: [] });
  const outer = vi.fn((e: { preventDefault: () => void }) => e.preventDefault());
  render(<QueryClientProvider client={new QueryClient()}>
    <form onSubmit={outer}><Harness onChange={vi.fn()} /></form>
  </QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Describe the day"), { target: { value: TEXT } });
  fireEvent.keyDown(screen.getByLabelText("Describe the day"), { key: "Enter" });
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
  await waitFor(() => expect(api.describeScenario).toHaveBeenCalled());
  expect(outer).not.toHaveBeenCalled();
});

it("sizes presets and the live preview for this layout's store format", async () => {
  vi.mocked(api.describeScenario).mockResolvedValue({ scenario: DESCRIBED, effects: {} as api.ScenarioEffects, warnings: [] });
  render(<QueryClientProvider client={new QueryClient()}><Harness onChange={vi.fn()} /></QueryClientProvider>);
  await waitFor(() => expect(api.getScenarios).toHaveBeenCalledWith({ projectId: "p", setupId: "s" }, expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText("Describe the day"), { target: { value: TEXT } });
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
  await waitFor(() => expect(api.previewScenario).toHaveBeenCalledWith(DESCRIBED, { projectId: "p", setupId: "s" }, expect.any(AbortSignal)));
});
