// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import * as api from "@/shared/api/client";
import { BASELINE_SCENARIO } from "../../scenarioDefaults";
import { ScenarioEditor } from "../ScenarioEditor";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  getScenarios: vi.fn().mockResolvedValue([]),
  previewScenario: vi.fn().mockResolvedValue({ traffic_by_hour: {}, demand: {} }),
  describeScenario: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const TEXT = "Rainy Friday evening";
const RESULT: api.DescribedScenario = { scenario: { ...BASELINE_SCENARIO, name: "Rainy evening", description: TEXT, weather: "rain" }, effects: {} as api.ScenarioEffects, warnings: ["Old request warning"] };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function mount() {
  const changed = vi.fn();
  function Harness() {
    const [value, setValue] = useState<api.Scenario | null>(null);
    const [project, setProject] = useState("p1");
    const [setup, setSetup] = useState("s1");
    return <>
      <button onClick={() => setProject("p2")}>Switch project</button>
      <button onClick={() => setSetup("s2")}>Switch layout</button>
      <ScenarioEditor value={value} onChange={(next) => { changed(next); setValue(next); }} projectId={project} setupId={setup} />
    </>;
  }
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><Harness /></QueryClientProvider>);
  return { ...view, changed };
}

function begin() {
  fireEvent.change(screen.getByLabelText("Describe the day"), { target: { value: TEXT } });
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
}

it.each(["비 오는 금요일 저녁", "雨の金曜日の夜", "下雨的周五晚上", "Rainy Friday evening", "Viernes por la noche", "Vendredi soir"])("keeps composition Enter in the description: %s", async (text) => {
  vi.mocked(api.describeScenario).mockResolvedValue(RESULT);
  const { changed } = mount();
  const input = screen.getByLabelText("Describe the day");
  fireEvent.change(input, { target: { value: text } });
  for (const flags of [{ isComposing: true }, { keyCode: 229 }]) {
    const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true, ...flags });
    fireEvent(input, event);
    expect(event.defaultPrevented).toBe(false);
  }
  await act(async () => {});
  expect(api.describeScenario).not.toHaveBeenCalled();
  expect(changed).not.toHaveBeenCalled();
});

const EDITS = ["description", "weather", "preset", "project", "layout"] as const;
function edit(kind: typeof EDITS[number]) {
  if (kind === "description") fireEvent.change(screen.getByLabelText("Describe the day"), { target: { value: "Sunny Sunday instead" } });
  if (kind === "weather") {
    fireEvent.click(screen.getByRole("button", { name: "Customize" }));
    fireEvent.change(screen.getByLabelText("Weather"), { target: { value: "snow" } });
  }
  if (kind === "preset") fireEvent.change(screen.getByLabelText("Scenario preset"), { target: { value: "custom" } });
  if (kind === "project") fireEvent.click(screen.getByRole("button", { name: "Switch project" }));
  if (kind === "layout") fireEvent.click(screen.getByRole("button", { name: "Switch layout" }));
}

it.each(EDITS)("does not overwrite a newer %s with a late result", async (kind) => {
  const request = deferred<api.DescribedScenario>();
  vi.mocked(api.describeScenario).mockReturnValue(request.promise);
  const { changed } = mount();
  begin();
  await waitFor(() => expect(api.describeScenario).toHaveBeenCalledTimes(1));
  edit(kind);
  const calls = changed.mock.calls.length;
  await act(async () => { request.resolve(RESULT); await request.promise; });
  expect(changed).toHaveBeenCalledTimes(calls);
  expect(screen.queryByText("Old request warning")).toBeNull();
});

it.each(EDITS)("discards an old failure after changing %s and allows another request", async (kind) => {
  const request = deferred<api.DescribedScenario>();
  vi.mocked(api.describeScenario).mockReturnValue(request.promise);
  mount();
  begin();
  await waitFor(() => expect(api.describeScenario).toHaveBeenCalledTimes(1));
  edit(kind);
  await act(async () => { request.reject(new Error("Failure from the previous request")); });
  expect(screen.queryByRole("alert")).toBeNull();
  expect((screen.getByRole("button", { name: "Set up" }) as HTMLButtonElement).disabled).toBe(false);
});

it("does not update the parent after the editor closes", async () => {
  const request = deferred<api.DescribedScenario>();
  vi.mocked(api.describeScenario).mockReturnValue(request.promise);
  const { changed, unmount } = mount();
  begin();
  await waitFor(() => expect(api.describeScenario).toHaveBeenCalledTimes(1));
  unmount();
  await act(async () => { request.resolve(RESULT); await request.promise; });
  expect(changed).not.toHaveBeenCalled();
});

it("applies only the newest request when two replies arrive in reverse order", async () => {
  const older = deferred<api.DescribedScenario>();
  const newer = deferred<api.DescribedScenario>();
  vi.mocked(api.describeScenario).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
  const { changed } = mount();
  begin();
  await waitFor(() => expect(api.describeScenario).toHaveBeenCalledTimes(1));
  edit("description");
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
  await waitFor(() => expect(api.describeScenario).toHaveBeenCalledTimes(2));
  const result = { ...RESULT, scenario: { ...RESULT.scenario, weather: "clear" as const, description: "Sunny Sunday instead" } };
  await act(async () => { newer.resolve(result); await newer.promise; });
  await act(async () => { older.resolve(RESULT); await older.promise; });
  expect(changed.mock.calls).toEqual([[result.scenario]]);
});
