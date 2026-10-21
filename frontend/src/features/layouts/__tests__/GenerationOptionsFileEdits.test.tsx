// @vitest-environment jsdom
import { useState } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "@/shared/api/client";
import { BuildingPicker } from "../components/BuildingPicker";
import { GenerationOptionsFile } from "../components/GenerationOptionsFile";
import { buildingPreset, choiceFromGeneration, type TemplateChoice } from "../templateOptions";
import type { Layout } from "../hooks/useLayouts";

vi.mock("@/shared/api/client", () => ({ validateLayoutPreset: vi.fn(), validateBuildingPreset: vi.fn() }));
vi.mock("../components/TemplatePicker", () => ({
  TemplatePicker: ({ value, onChange }: { value: TemplateChoice; onChange: (choice: TemplateChoice) => void }) =>
    <GenerationOptionsFile kind="layout" value={value} onChange={onChange} canExport />,
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function BuildingForm() {
  const [floors, setFloors] = useState(() => buildingPreset("cafe_shop"));
  return <>
    <BuildingPicker floors={floors} onChange={setFloors} />
    <output data-testid="floors">{JSON.stringify(floors)}</output>
  </>;
}

it("keeps a floor label edited while imported options are being checked", async () => {
  let complete: ((preset: api.LayoutPreset) => void) | undefined;
  vi.mocked(api.validateLayoutPreset).mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
  render(<BuildingForm />);
  const file = Object.assign(new File(["{}"], "floor.json", { type: "application/json" }), { text: async () => "{}" });
  fireEvent.change(screen.getByLabelText("Import layout options file"), { target: { files: [file] } });
  await waitFor(() => expect(api.validateLayoutPreset).toHaveBeenCalledOnce());
  fireEvent.change(screen.getByLabelText("Floor label"), { target: { value: "Renamed ground floor" } });

  await act(async () => complete?.({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "community_pharmacy", seed: 7, currency: "USD" } }));

  expect((screen.getByLabelText("Floor label") as HTMLInputElement).value).toBe("Renamed ground floor");
  const floors = JSON.parse(screen.getByTestId("floors").textContent ?? "[]") as { label: string; choice: TemplateChoice }[];
  expect(floors[0]?.choice.templateId).toBe("community_pharmacy");
  expect(floors[1]?.choice.templateId).toBe("book_cafe");
});

it("does not apply a deleted first floor's pending import to the floor that moves into its place", async () => {
  let complete: ((preset: api.LayoutPreset) => void) | undefined;
  vi.mocked(api.validateLayoutPreset).mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
  render(<BuildingForm />);
  fireEvent.click(screen.getByRole("button", { name: "Add floor" }));
  fireEvent.click(screen.getByRole("button", { name: /1F · Ground/ }));
  const file = Object.assign(new File(["{}"], "floor.json"), { text: async () => "{}" });
  fireEvent.change(screen.getByLabelText("Import layout options file"), { target: { files: [file] } });
  await waitFor(() => expect(api.validateLayoutPreset).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByRole("button", { name: "Remove floor" }));
  await act(async () => complete?.({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "community_pharmacy", seed: 7, currency: "USD" } }));
  const floors = JSON.parse(screen.getByTestId("floors").textContent ?? "[]") as { label: string; choice: TemplateChoice }[];
  expect(floors).toHaveLength(2);
  expect(floors[0]?.choice.templateId).toBe("book_cafe");
  expect(floors[1]?.choice.templateId).toBe("design_showroom");
});

const versions: Layout[] = [
  { id: "first", name: "First version", parentId: null, status: "draft", createdAt: "2026-10-21",
    generation: { template_id: "community_pharmacy", seed: 0, currency: "USD" } },
  { id: "second", name: "Second version", parentId: "first", status: "draft", createdAt: "2026-10-21",
    generation: { template_id: "bookstore", seed: 1, currency: "JPY" } },
];

function VersionedBuildingForm() {
  const [floors, setFloors] = useState(() => buildingPreset("cafe_shop").map((floor, index) => index === 0
    ? { ...floor, choice: choiceFromGeneration(versions[0]!.generation!, "first") } : floor));
  return <>
    <BuildingPicker floors={floors} onChange={setFloors} sourceLayouts={versions} />
    <output data-testid="floors">{JSON.stringify(floors)}</output>
  </>;
}

it("keeps the saved floor version selected after an earlier import started", async () => {
  let complete: ((preset: api.LayoutPreset) => void) | undefined;
  vi.mocked(api.validateLayoutPreset).mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
  render(<VersionedBuildingForm />);
  const file = Object.assign(new File(["{}"], "floor.json"), { text: async () => "{}" });
  fireEvent.change(screen.getByLabelText("Import layout options file"), { target: { files: [file] } });
  await waitFor(() => expect(api.validateLayoutPreset).toHaveBeenCalledOnce());
  fireEvent.change(screen.getByLabelText("Saved floor settings"), { target: { value: "second" } });
  await act(async () => complete?.({ format: "twinstore-layout-options", version: 1,
    layout: { template_id: "optical_shop", seed: 7, currency: "USD" } }));
  const floors = JSON.parse(screen.getByTestId("floors").textContent ?? "[]") as { label: string; choice: TemplateChoice }[];
  expect(floors[0]?.choice).toMatchObject({ templateId: "bookstore", currency: "JPY", sourceSetupId: "second" });
});
