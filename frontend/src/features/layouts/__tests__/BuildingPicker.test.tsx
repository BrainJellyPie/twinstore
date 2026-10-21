// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BuildingPicker } from "../components/BuildingPicker";
import { buildingPreset, type TemplateChoice } from "../templateOptions";

vi.mock("../components/TemplatePicker", () => ({
  TemplatePicker: ({ value, onChange }: { value: TemplateChoice; onChange: (v: TemplateChoice) => void }) =>
    <div><span>{value.templateId} / width {value.width ?? "default"}</span><button type="button" onClick={() => onChange({ ...value, width: 30 })}>Set floor width</button></div>,
}));
afterEach(cleanup);

function Building() {
  const [floors, setFloors] = useState(() => buildingPreset("wellness"));
  return <BuildingPicker floors={floors} onChange={setFloors} />;
}

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
