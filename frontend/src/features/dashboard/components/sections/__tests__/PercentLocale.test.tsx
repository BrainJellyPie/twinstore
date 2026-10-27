// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { useLocale } from "@/shared/i18n/i18n";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { CustomerBehavior } from "../CustomerBehavior";
import { PlaybackStatus } from "../PlaybackStatus";

beforeEach(() => useLocale.getState().setLocale("fr"));
afterEach(() => { cleanup(); useSimulationMetricsStore.getState().reset(); useLocale.getState().setLocale("en"); });

it("writes the live conversion and playback progress as percentages in the selected language", () => {
  useSimulationMetricsStore.getState().setMetrics({ entered: 8, paidCount: 3, currentMinute: 600 });
  render(<><CustomerBehavior /><PlaybackStatus minTime={0} maxTime={1000} /></>);
  // French puts a (narrow no-break) space before the percent sign.
  expect(screen.getByText(/^38\s%$/)).toBeTruthy();
  expect(screen.getByText(/^60\s%$/)).toBeTruthy();
  expect(screen.queryByText(/^\d+%$/)).toBeNull();
});
