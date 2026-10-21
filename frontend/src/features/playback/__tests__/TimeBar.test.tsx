// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TimeBar } from "../components/TimeBar";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore } from "@/stores/simulationStore";

let small = true;
let changed: (() => void) | undefined;
const removed = vi.fn();
beforeEach(() => {
  small = true;
  changed = undefined;
  removed.mockClear();
  vi.stubGlobal("matchMedia", () => ({
    get matches() { return small; },
    addEventListener: (_name: string, listener: () => void) => { changed = listener; },
    removeEventListener: removed,
  }));
  usePlaybackControlStore.getState().reset();
  useSimulationMetricsStore.getState().reset();
  useSimulationStore.getState().reset();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("keeps playback and seeking available in the folded phone panel", () => {
  render(<TimeBar minTime={28800} maxTime={72000} />);
  expect(screen.queryByRole("radio", { name: "Fast" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Play" }));
  expect(usePlaybackControlStore.getState().playing).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Pause" }));
  expect(usePlaybackControlStore.getState().playing).toBe(false);
  fireEvent.change(screen.getByRole("slider", { name: "Scrub through the day" }), { target: { value: "36000" } });
  expect(usePlaybackControlStore.getState().seekTarget).toBe(36000);
  fireEvent.click(screen.getByRole("button", { name: "Expand playback controls" }));
  fireEvent.click(screen.getByRole("radio", { name: "Fast" }));
  expect(usePlaybackControlStore.getState().speed).toBe(600);
  fireEvent.click(screen.getByRole("button", { name: "Collapse playback controls" }));
  expect(screen.queryByRole("radio", { name: "Fast" })).toBeNull();
});

it("adapts its default to screen size and preserves an explicit folding choice", () => {
  small = false;
  const view = render(<TimeBar minTime={28800} maxTime={72000} />);
  expect(screen.getByRole("radio", { name: "Fast" })).toBeTruthy();
  act(() => { small = true; changed?.(); });
  expect(screen.getByRole("button", { name: "Expand playback controls" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Expand playback controls" }));
  act(() => { small = false; changed?.(); });
  act(() => { small = true; changed?.(); });
  expect(screen.getByRole("button", { name: "Collapse playback controls" })).toBeTruthy();
  view.unmount();
  expect(removed).toHaveBeenCalledWith("change", changed);
});

it.each([[28800, 28800], [72000, 28800]])("disables transport for an empty or reversed interval (%s, %s)", (minTime, maxTime) => {
  render(<TimeBar minTime={minTime} maxTime={maxTime} />);
  expect((screen.getByRole("button", { name: "Play" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Skip to closing time" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("slider") as HTMLInputElement).disabled).toBe(true);
  fireEvent.keyDown(window, { code: "Space" });
  expect(usePlaybackControlStore.getState().playing).toBe(false);
});

it.each([[0, 28800, "0%"], [100000, 72000, "100%"]])("clamps out-of-range progress at %s", (minute, value, label) => {
  useSimulationMetricsStore.setState({ currentMinute: minute });
  render(<TimeBar minTime={28800} maxTime={72000} />);
  expect((screen.getByRole("slider") as HTMLInputElement).value).toBe(String(value));
  expect(screen.getByRole("button", { name: "Expand playback controls" }).textContent).toContain(label);
});

it("replays a finished run from its first available day and opening time", () => {
  usePlaybackControlStore.setState({ currentDay: 9, availableDays: [2, 5, 9] });
  useSimulationMetricsStore.setState({ finished: true, currentMinute: 72000 });
  render(<TimeBar minTime={28800} maxTime={72000} />);
  fireEvent.keyDown(window, { code: "Space" });
  expect(usePlaybackControlStore.getState().playing).toBe(false);
  expect(screen.queryByRole("button", { name: "Play" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Replay" }));
  expect(usePlaybackControlStore.getState().currentDay).toBe(2);
  expect(usePlaybackControlStore.getState().seekTarget).toBe(28800);
});

it("navigates sparse days without leaving the available range", () => {
  usePlaybackControlStore.getState().setAvailableDays([2, 5, 9]);
  render(<TimeBar minTime={28800} maxTime={72000} />);
  const previous = screen.getByRole("button", { name: "Previous day" }) as HTMLButtonElement;
  const next = screen.getByRole("button", { name: "Next day" }) as HTMLButtonElement;
  expect(previous.disabled).toBe(true);
  fireEvent.click(next);
  expect(usePlaybackControlStore.getState().currentDay).toBe(5);
  fireEvent.click(next);
  expect(usePlaybackControlStore.getState().currentDay).toBe(9);
  expect(next.disabled).toBe(true);
  fireEvent.click(previous);
  expect(usePlaybackControlStore.getState().currentDay).toBe(5);
});

it.each([false, true])("keeps legacy run features gated when capabilities are %s", (supported) => {
  small = false;
  render(<TimeBar minTime={28800} maxTime={72000} hasDwell={supported} hasRackStats={supported} />);
  expect((screen.getByRole("radio", { name: "Dwell" }) as HTMLButtonElement).disabled).toBe(!supported);
  expect((screen.getByRole("button", { name: "Rack KPIs" }) as HTMLButtonElement).disabled).toBe(!supported);
});

it("keeps the shopper-view exit available while folded", () => {
  small = false;
  useSimulationStore.setState({ shopperView: true });
  render(<TimeBar minTime={28800} maxTime={72000} />);
  expect(screen.getByRole("button", { name: "Expand playback controls" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Exit" }));
  expect(useSimulationStore.getState().shopperView).toBe(false);
  expect(screen.getByRole("button", { name: "Collapse playback controls" })).toBeTruthy();
});

it.each(["input", "textarea", "select", "button"])("does not intercept Space in a %s", (tag) => {
  render(<TimeBar minTime={28800} maxTime={72000} />);
  const control = document.createElement(tag);
  document.body.append(control);
  try {
    fireEvent.keyDown(control, { code: "Space" });
    expect(usePlaybackControlStore.getState().playing).toBe(false);
  } finally { control.remove(); }
});

it("toggles playback only once while Space is held", () => {
  render(<TimeBar minTime={28800} maxTime={72000} />);
  fireEvent.keyDown(window, { code: "Space" });
  fireEvent.keyDown(window, { code: "Space", repeat: true });
  expect(usePlaybackControlStore.getState().playing).toBe(true);
});

it.each(["altKey", "ctrlKey", "metaKey"])("ignores modified Space shortcuts (%s)", (modifier) => {
  render(<TimeBar minTime={28800} maxTime={72000} />);
  fireEvent.keyDown(window, { code: "Space", [modifier]: true });
  expect(usePlaybackControlStore.getState().playing).toBe(false);
});

it("stops responding to shortcuts after unmount", () => {
  const view = render(<TimeBar minTime={28800} maxTime={72000} />);
  view.unmount();
  fireEvent.keyDown(window, { code: "Space" });
  expect(usePlaybackControlStore.getState().playing).toBe(false);
});
