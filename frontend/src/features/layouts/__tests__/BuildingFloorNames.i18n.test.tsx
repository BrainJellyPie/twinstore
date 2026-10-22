// @vitest-environment jsdom
import { useState } from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LOCALES } from "@/shared/i18n/messages";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { templateName } from "@/shared/i18n/storeLabels";
import { BuildingPicker } from "../components/BuildingPicker";
import { BUILDING_PRESETS, buildingPreset, validBuildingFloors } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ validateBuildingPreset: vi.fn() }));
vi.mock("../components/TemplatePicker", () => ({ TemplatePicker: () => null }));
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

it.each(LOCALES.filter(item => item.code !== "en"))("creates editable preset names without repeating the level in $code", ({ code }) => {
  for (const preset of BUILDING_PRESETS) {
    const floors = buildingPreset(preset.id, "JPY", code);
    expect(validBuildingFloors(floors), preset.id).toBe(true);
    for (const [index, floor] of floors.entries()) {
      const [sourceLabel, id] = preset.floors[index]!;
      expect(floor.label).toBe(templateName(id, sourceLabel, code));
      expect(floor.label).not.toContain(translate(code, "layLevelName", { number: index + 1 }));
      expect(floor.choice).toMatchObject({ templateId: id, currency: "JPY" });
    }
    const previous = floors[1]!.choice.seed;
    floors[0]!.choice.seed = 47;
    expect(floors[1]!.choice.seed).toBe(previous);
  }
});

it.each(LOCALES)("preserves edited and existing names across language changes and floor moves in $code", ({ code }) => {
  useLocale.getState().setLocale(code);
  function Building() {
    const [floors, setFloors] = useState(() => buildingPreset("cafe_shop", "KRW", code));
    return <><BuildingPicker floors={floors} onChange={setFloors} defaultCurrency="KRW" /><output data-testid="floors">{JSON.stringify(floors)}</output></>;
  }
  render(<Building />);
  const name = "1階 · User <Tea> & Café 🛒";
  fireEvent.change(screen.getByLabelText(translate(code, "layFloorLabel")), { target: { value: name } });
  const original = screen.getByTestId("floors").textContent;
  const nextLocale = code === "ja" ? "es" : "ja";
  act(() => useLocale.getState().setLocale(nextLocale));
  expect(screen.getByTestId("floors").textContent).toBe(original);
  expect(screen.getByRole("button", { name: translate(nextLocale, "layNamedFloor", { number: 1, name }) })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: translate(nextLocale, "layMoveHigher") }));
  expect(screen.getByRole("button", { name: translate(nextLocale, "layNamedFloor", { number: 2, name }) })).toBeTruthy();
  const moved = JSON.parse(screen.getByTestId("floors").textContent!);
  expect(moved[1].label).toBe(name);
  expect(moved[1].choice).toEqual(JSON.parse(original!)[0].choice);
});
