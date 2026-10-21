// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BuildingPicker } from "../components/BuildingPicker";
import { buildingPreset, savedBuildingFloors, type TemplateChoice } from "../templateOptions";
import type { Layout } from "../hooks/useLayouts";
import * as api from "@/shared/api/client";

vi.mock("@/shared/api/client", () => ({ validateBuildingPreset: vi.fn() }));

vi.mock("../components/TemplatePicker", () => ({
  TemplatePicker: ({ value, onChange, onApplyDesignToAll, onApplyCurrencyToAll }: {
    value: TemplateChoice; onChange: (v: TemplateChoice) => void;
    onApplyDesignToAll?: (design: NonNullable<TemplateChoice["design_theme"]>) => void; onApplyCurrencyToAll?: (currency: string) => void;
  }) => <div><span>{value.templateId} / width {value.width ?? "default"}</span><span data-testid="floor-currency">{value.currency}</span>
    <span data-testid="floor-design">{value.design_theme ?? "default"}</span>
    <button type="button" onClick={() => onChange({ ...value, width: 30 })}>Set floor width</button>
    <button type="button" onClick={() => onApplyDesignToAll?.("coastal")}>Share coastal design</button>
    <button type="button" onClick={() => onApplyCurrencyToAll?.("JPY")}>Share JPY currency</button></div>,
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function Building({ currency = "USD" }: { currency?: string }) {
  const [floors, setFloors] = useState(() => buildingPreset("wellness", currency));
  return <BuildingPicker floors={floors} onChange={setFloors} defaultCurrency={currency} />;
}

it("switches to the first imported floor and replaces all previous floor labels", async () => {
  render(<Building />);
  fireEvent.click(screen.getByRole("button", { name: /2F/ }));
  vi.mocked(api.validateBuildingPreset).mockResolvedValue({ format: "twinstore-building-options", version: 1, floors: [
    { label: "Books", layout: { template_id: "bookstore", seed: 2, currency: "JPY" } },
    { label: "Coffee", layout: { template_id: "specialty_cafe", seed: 3, currency: "JPY" } },
    { label: "Dining", layout: { template_id: "family_restaurant", seed: 4, currency: "JPY" } },
  ] });
  const file = Object.assign(new File(["{}"], "building.json"), { text: async () => "{}" });
  fireEvent.change(screen.getByLabelText("Import building options file"), { target: { files: [file] } });
  expect((await screen.findByRole("button", { name: "1F · Books" })).getAttribute("aria-pressed")).toBe("true");
  expect(screen.queryByRole("button", { name: /Ground · Pharmacy/ })).toBeNull();
  expect(screen.getByRole("button", { name: "3F · Dining" })).toBeTruthy();
  expect(screen.getByText("bookstore / width default")).toBeTruthy();
  expect(screen.getByTestId("floor-currency").textContent).toBe("JPY");
});

it("keeps each floor's options when switching and editing", () => {
  render(<Building />);
  fireEvent.click(screen.getByRole("button", { name: "Set floor width" }));
  expect(screen.getByText("community_pharmacy / width 30")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /2F/ }));
  expect(screen.getByText("wellness_pharmacy / width default")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Floor label"), { target: { value: "Consultation level" } });
  fireEvent.click(screen.getByRole("button", { name: /1F/ }));
  expect(screen.getByText("community_pharmacy / width 30")).toBeTruthy();
  expect(screen.getByRole("button", { name: /2F · Consultation level/ })).toBeTruthy();
});

it("shares design and currency while keeping each floor's format, dimensions and label", () => {
  render(<Building />);
  fireEvent.click(screen.getByRole("button", { name: "Set floor width" }));
  fireEvent.change(screen.getByLabelText("Floor label"), { target: { value: "Custom ground" } });
  fireEvent.click(screen.getByRole("button", { name: "Share coastal design" }));
  fireEvent.click(screen.getByRole("button", { name: "Share JPY currency" }));
  fireEvent.click(screen.getByRole("button", { name: /2F/ }));
  expect(screen.getByText("wellness_pharmacy / width default")).toBeTruthy();
  expect(screen.getByTestId("floor-design").textContent).toBe("coastal");
  expect(screen.getByTestId("floor-currency").textContent).toBe("JPY");
  fireEvent.click(screen.getByRole("button", { name: "1F · Custom ground" }));
  expect(screen.getByText("community_pharmacy / width 30")).toBeTruthy();
  expect(screen.getByTestId("floor-design").textContent).toBe("coastal");
  expect(screen.getByTestId("floor-currency").textContent).toBe("JPY");
});

it("bounds floor count and flags duplicate labels", () => {
  render(<Building />);
  expect((screen.getByRole("button", { name: "Remove floor" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: /2F/ }));
  fireEvent.change(screen.getByLabelText("Floor label"), { target: { value: "ground · pharmacy" } });
  expect(screen.getByRole("alert").textContent).toContain("unique label");
  for (let i = 0; i < 4; i++) fireEvent.click(screen.getByRole("button", { name: "Add floor" }));
  expect((screen.getByRole("button", { name: "Add floor" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Remove floor" }));
  expect((screen.getByRole("button", { name: "Add floor" }) as HTMLButtonElement).disabled).toBe(false);
});

it("keeps the project's currency when choosing a preset or adding a floor", () => {
  render(<Building currency="KRW" />);
  expect(screen.getByTestId("floor-currency").textContent).toBe("KRW");
  fireEvent.click(screen.getByRole("button", { name: "Department store" }));
  fireEvent.click(screen.getByRole("button", { name: /4F/ }));
  expect(screen.getByTestId("floor-currency").textContent).toBe("KRW");
  fireEvent.click(screen.getByRole("button", { name: "Add floor" }));
  expect(screen.getByTestId("floor-currency").textContent).toBe("KRW");
});

it("starts a campus hub with three distinct store, book and dining floors", () => {
  render(<Building currency="JPY" />);
  fireEvent.click(screen.getByRole("button", { name: "Campus hub" }));
  expect(screen.getByText("campus_cvs / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /2F · Level 2 · Bookstore/ }));
  expect(screen.getByText("bookstore / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /3F · Level 3 · Dining hall/ }));
  expect(screen.getByText("campus_dining_hall / width default")).toBeTruthy();
  expect(screen.getByTestId("floor-currency").textContent).toBe("JPY");
});

it("starts a family essentials center with baby supplies, footwear and dining", () => {
  render(<Building currency="KRW" />);
  fireEvent.click(screen.getByRole("button", { name: "Family essentials center" }));
  expect(screen.getByText("baby_family_store / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /2F · Level 2 · Footwear/ }));
  expect(screen.getByText("shoe_boutique / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /3F · Level 3 · Family dining/ }));
  expect(screen.getByText("family_restaurant / width default")).toBeTruthy();
  expect(screen.getByTestId("floor-currency").textContent).toBe("KRW");
});

it("starts garden, crafts and cafe floors with the project's currency", () => {
  render(<Building currency="JPY" />);
  fireEvent.click(screen.getByRole("button", { name: "Garden, crafts & café" }));
  expect(screen.getByText("garden_center / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /2F · Level 2 · Arts & crafts/ }));
  expect(screen.getByText("art_craft_store / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /3F · Level 3 · Café/ }));
  expect(screen.getByText("specialty_cafe / width default")).toBeTruthy();
  expect(screen.getByTestId("floor-currency").textContent).toBe("JPY");
});

it("combines eyewear, jewelry, music and coffee as independently configurable floors", () => {
  render(<Building currency="JPY" />);
  fireEvent.click(screen.getByRole("button", { name: "Style, sound & café" }));
  expect(screen.getByText("optical_shop / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Set floor width" }));
  fireEvent.click(screen.getByRole("button", { name: /2F · Level 2 · Jewelry/ }));
  expect(screen.getByText("jewelry_boutique / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /3F · Level 3 · Music/ }));
  expect(screen.getByText("music_store / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /4F · Level 4 · Café/ }));
  expect(screen.getByText("specialty_cafe / width default")).toBeTruthy();
  expect(screen.getByTestId("floor-currency").textContent).toBe("JPY");
  fireEvent.click(screen.getByRole("button", { name: /1F · Ground · Eyewear/ }));
  expect(screen.getByText("optical_shop / width 30")).toBeTruthy();
});

it("starts a dining house with independent juice, noodle, sushi and pizza floors", () => {
  render(<Building currency="KRW" />);
  fireEvent.click(screen.getByRole("button", { name: "Dining house" }));
  expect(screen.getByText("juice_bar / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Set floor width" }));
  for (const [label, templateId] of [["2F · Level 2 · Noodles", "noodle_bar"], ["3F · Level 3 · Sushi", "sushi_shop"], ["4F · Level 4 · Pizza", "pizzeria"]]) {
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(screen.getByText(`${templateId} / width default`)).toBeTruthy();
    expect(screen.getByTestId("floor-currency").textContent).toBe("KRW");
  }
  fireEvent.click(screen.getByRole("button", { name: "1F · Ground · Juice bar" }));
  expect(screen.getByText("juice_bar / width 30")).toBeTruthy();
});

it("starts a neighborhood dining center with independently editable specialty floors", () => {
  render(<Building currency="JPY" />);
  fireEvent.click(screen.getByRole("button", { name: "Neighborhood dining center" }));
  expect(screen.getByText("ice_cream_parlor / width default")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Set floor width" }));
  for (const [label, templateId] of [["2F · Level 2 · Salads", "salad_cafe"], ["3F · Level 3 · Burgers", "burger_shop"], ["4F · Level 4 · Korean dining", "korean_restaurant"]]) {
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(screen.getByText(`${templateId} / width default`)).toBeTruthy();
    expect(screen.getByTestId("floor-currency").textContent).toBe("JPY");
  }
  fireEvent.click(screen.getByRole("button", { name: "1F · Ground · Ice cream" }));
  expect(screen.getByText("ice_cream_parlor / width 30")).toBeTruthy();
});

it("moves and duplicates a customized floor without losing its settings", () => {
  render(<Building />);
  fireEvent.click(screen.getByRole("button", { name: "Set floor width" }));
  fireEvent.click(screen.getByRole("button", { name: "Move to higher level" }));
  expect(screen.getByRole("button", { name: "2F · Ground · Pharmacy" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText("community_pharmacy / width 30")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Duplicate floor" }));
  expect(screen.getByRole("button", { name: "3F · Ground · Pharmacy copy 1" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText("community_pharmacy / width 30")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Move to lower level" }));
  expect(screen.getByRole("button", { name: "2F · Ground · Pharmacy copy 1" }).getAttribute("aria-pressed")).toBe("true");
});

const ground: Layout = { id: "ground", name: "Ground store", parentId: null, status: "draft", createdAt: "2026-10-20",
  building: { id: "building", name: "Market", level: 1, label: "Ground", floor_count: 2 },
  generation: { template_id: "community_pharmacy", seed: 0, currency: "JPY", design_theme: "minimal", requirements: "Quiet corner" } };
const upstairs: Layout = { ...ground, id: "upstairs", name: "Upper café", building: { ...ground.building!, level: 2, label: "Café" },
  generation: { template_id: "specialty_cafe", seed: 0, currency: "JPY", dining_tables: 4, width: 20 } };
const latest: Layout = { ...upstairs, id: "latest", name: "Latest café", parentId: upstairs.id, createdAt: "2026-10-21",
  generation: { ...upstairs.generation!, dining_tables: 6 } };

it("restores the selected floor and the latest other floors, while rejecting incomplete buildings", () => {
  const unrelated: Layout = { ...latest, id: "other", building: { ...latest.building!, id: "other_building" }, createdAt: "2026-10-22" };
  const floors = savedBuildingFloors([latest, upstairs, unrelated, ground], ground)!;
  expect(floors.map((floor) => floor.choice.sourceSetupId)).toEqual([ground.id, latest.id]);
  expect(floors[0]!.choice.requirements).toBe("Quiet corner");
  expect(floors[1]!.choice.dining_tables).toBe(6);
  expect(savedBuildingFloors([latest, upstairs, ground], upstairs)![1]!.choice.sourceSetupId).toBe(upstairs.id);
  expect(savedBuildingFloors([ground], ground)).toBeNull();
  expect(savedBuildingFloors([ground, upstairs], { ...upstairs, generation: null })).toBeNull();
});

it("lets a reused floor choose a different saved version and keeps its source when duplicated", () => {
  const changed = vi.fn();
  const floors = savedBuildingFloors([ground, upstairs, latest], ground)!;
  render(<BuildingPicker floors={floors} onChange={changed} sourceLayouts={[ground, upstairs, latest]} />);
  fireEvent.click(screen.getByRole("button", { name: /2F/ }));
  expect((screen.getByLabelText("Saved floor settings") as HTMLSelectElement).value).toBe(latest.id);
  fireEvent.change(screen.getByLabelText("Saved floor settings"), { target: { value: upstairs.id } });
  expect(changed).toHaveBeenLastCalledWith([floors[0], expect.objectContaining({ choice: expect.objectContaining({ sourceSetupId: upstairs.id, dining_tables: 4 }) })]);
  fireEvent.click(screen.getByRole("button", { name: "Duplicate floor" }));
  expect(changed.mock.lastCall![0][2].choice.sourceSetupId).toBe(latest.id);
});
