// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { useLocale } from "@/shared/i18n/i18n";
import { useSimulationStore } from "@/stores/simulationStore";
import { useRealisticSettings } from "../graphicsSettings";
import { usePhotoMode } from "../photoModeStore";
import { RealisticHud } from "../RealisticHud";

beforeEach(() => {
  useLocale.getState().setLocale("en");
  useSimulationStore.getState().reset();
  useSimulationStore.getState().setGraphicsMode("realistic");
  useRealisticSettings.getState().setRealisticReady(true);
  usePhotoMode.getState().stop();
});
afterEach(() => { cleanup(); usePhotoMode.getState().stop(); useRealisticSettings.getState().setRealisticReady(false); });

it("tells assistive technology whether Photo mode is on", () => {
  render(<RealisticHud personaNames={new Map()} showModeSwitch shopperViewActive={false} onFitStore={() => {}} />);
  const photo = screen.getByRole("button", { name: /Photo/ });
  expect(photo.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(photo);
  expect(usePhotoMode.getState().status).not.toBe("off");
  expect(photo.getAttribute("aria-pressed")).toBe("true");
});
