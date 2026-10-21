// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { BuildingPicker } from "../components/BuildingPicker";
import { choiceFromGeneration, DEFAULT_TEMPLATE_CHOICE, templateRequest, validTemplateChoice, type BuildingFloorChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "urban_cvs", name: "City store", description: "Groceries", store_type: "convenience", grid: [12, 10], racks: 10, skus: 40,
      open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => ({ id: request.template_id, name: "Floor", type: "store",
    grid_size: [request.width ?? 12, request.height ?? 10], design_theme: request.design_theme ?? "classic", design_colors: request.design_colors, weekly_schedule: [], racks: [] }));
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
const initial: BuildingFloorChoice[] = Array.from({ length: 6 }, (_, i) => ({ label: `Floor ${i + 1}`, choice: {
  ...DEFAULT_TEMPLATE_CHOICE, width: 12 + i, currency: i % 2 ? "JPY" : "USD", seed: i, design_theme: i % 2 ? "nordic" : "coastal",
  design_colors: i === 0 ? { wall: "#123456", floor: "#abcdef" } : { accent: "#654321" },
  requirements: `Keep ${i}`, closed_days: [i + 1], table_rotation: i % 2 ? 90 : 0,
} }));
function Building() {
  const [floors, setFloors] = useState(initial);
  return <><BuildingPicker floors={floors} onChange={setFloors} /><output data-testid="floors">{JSON.stringify(floors)}</output></>;
}
async function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><Building /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Custom interior colors · 2 overrides"));
}
const floors = (): BuildingFloorChoice[] => JSON.parse(screen.getByTestId("floors").textContent!);
const color = (label: string) => screen.getByLabelText(label) as HTMLInputElement;

it("changes one floor, follows base design for unset channels and resets overrides independently", async () => {
  await mount();
  expect(color("Wall color").value).toBe("#123456");
  expect(color("Counter color").value).toBe("#c9dde4");
  fireEvent.change(color("Accent color"), { target: { value: "#ff00ff" } });
  fireEvent.change(screen.getByLabelText("Interior design (Realistic view)"), { target: { value: "retro" } });
  expect(color("Counter color").value).toBe("#b3484d");
  expect(color("Wall color").value).toBe("#123456");
  expect(floors().slice(1)).toEqual(initial.slice(1));
  fireEvent.click(screen.getByRole("button", { name: "Reset wall color" }));
  expect(color("Wall color").value).toBe("#f8edda");
  expect(color("Accent color").value).toBe("#ff00ff");
  await waitFor(() => expect(screen.getByRole("img", { name: "Floor plan preview" }).style.backgroundColor).toBe("rgb(171, 205, 239)"));
  fireEvent.click(screen.getByRole("button", { name: "Reset all custom colors" }));
  expect(floors()[0]!.choice.design_colors).toBeNull();
  expect(color("Accent color").value).toBe("#77b8ad");
  expect(floors()[0]!.choice.requirements).toBe("Keep 0");
});

it("copies design and colors to six floors without sharing objects or overwriting other requirements", async () => {
  await mount(); fireEvent.click(screen.getByRole("button", { name: "Apply design to all floors" }));
  floors().forEach((floor, i) => expect(floor).toEqual({ ...initial[i], choice: { ...initial[i]!.choice, design_theme: "coastal", design_colors: initial[0]!.choice.design_colors } }));
  expect((screen.getByRole("button", { name: "Design used on all floors" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "2F · Floor 2" }));
  fireEvent.click(screen.getByText("Custom interior colors · 2 overrides"));
  fireEvent.change(color("Floor color"), { target: { value: "#000000" } });
  expect(floors().map((floor) => floor.choice.design_colors?.floor)).toEqual(["#abcdef", "#000000", "#abcdef", "#abcdef", "#abcdef", "#abcdef"]);
  expect((screen.getByRole("button", { name: "Apply design to all floors" }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Reset all custom colors" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply design to all floors" }));
  expect(floors().every((floor) => floor.choice.design_colors === null)).toBe(true);
});

it("resets all layout options including colors while preserving the brief and adjacent floors", async () => {
  await mount(); fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect(floors()[0]!.choice.design_colors).toBeNull();
  expect(floors()[0]!.choice.design_theme).toBeNull();
  expect(color("Wall color").value).toBe("#f2f0ea");
  expect(floors()[0]!.choice.requirements).toBe("Keep 0");
  expect(floors().slice(1)).toEqual(initial.slice(1));
});

it.each([null, {}, { wall: null }, { floor: "#000000", counter: "#FFFFFF" }])("retains valid colors through request and saved-source reuse: %j", (design_colors) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, design_colors };
  expect(validTemplateChoice(choice)).toBe(true);
  expect(choiceFromGeneration(templateRequest(choice), "source")).toMatchObject({ design_colors, sourceSetupId: "source" });
});
it.each(["#fff", "#123456\n", "red", "#12345678", "#１２３４５６"])("rejects invalid color %j before preview or export", (floor) => {
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, design_colors: { floor } })).toBe(false);
});
