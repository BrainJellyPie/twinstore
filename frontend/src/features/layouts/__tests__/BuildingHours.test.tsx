// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { BuildingPicker } from "../components/BuildingPicker";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, type BuildingFloorChoice, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));

beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "community_pharmacy", name: "Community pharmacy", description: "Care", store_type: "pharmacy", grid: [14, 12], racks: 12, skus: 50,
      open_hours: [9, 21], closed_days: [7], default_style: "spine", default_design: "minimal", default_dining_tables: 0 },
    { id: "specialty_cafe", name: "Specialty café", description: "Coffee", store_type: "cafe", grid: [18, 14], racks: 20, skus: 40,
      open_hours: [7, 22], closed_days: [6, 7], default_style: "perimeter", default_design: "warm", default_dining_tables: 6 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Preview", type: "convenience", grid_size: [12, 10], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const initial: BuildingFloorChoice[] = [
  { label: "Pharmacy", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "community_pharmacy", width: 30, design_theme: "nordic", currency: "JPY", requirements: "Keep a consultation area", reserved_areas: [{ label: "Consultation", x: 1, y: 1, width: 2, height: 3 }] } },
  { label: "Café", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "specialty_cafe", height: 24, seed: 4, table_mix: { two_seat: 2, four_seat: 1, six_seat: 1 }, dining_tables: 4 } },
];

function Building({ patch = {} }: { patch?: Partial<TemplateChoice> }) {
  const [floors, setFloors] = useState(() => initial.map((floor, index) => ({ ...floor, choice: { ...floor.choice, ...(index === 0 ? patch : {}) } })));
  return <><BuildingPicker floors={floors} onChange={setFloors} /><output data-testid="floors">{JSON.stringify(floors)}</output>
    <output data-testid="shared-array">{String(floors[0]!.choice.closed_days === floors[1]!.choice.closed_days)}</output></>;
}

async function mount(patch: Partial<TemplateChoice> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Building patch={patch} /></QueryClientProvider>);
  fireEvent.click(await screen.findByText("Operating hours · 6 open days"));
}
const floors = (): BuildingFloorChoice[] => JSON.parse(screen.getByTestId("floors").textContent!);
const share = () => screen.getByRole("button", { name: "Apply operating hours to all floors" }) as HTMLButtonElement;

it("copies resolved source defaults across unlike formats and preserves all other choices", async () => {
  await mount();
  expect(screen.getByText(/Applies 09:00–21:00 and 6 open days/)).toBeTruthy();
  fireEvent.click(share());
  expect(floors()).toEqual(initial.map((floor) => ({ ...floor, choice: { ...floor.choice, open_hour: 9, close_hour: 21, closed_days: [7] } })));
  expect(screen.getByTestId("shared-array").textContent).toBe("false");
  expect((screen.getByRole("button", { name: "Operating hours used on all floors" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "2F · Café" }));
  fireEvent.click(screen.getByText("Operating hours · 6 open days"));
  expect((screen.getByLabelText("Opening hour (0–23)") as HTMLInputElement).value).toBe("9");
  fireEvent.click(screen.getByRole("button", { name: "Use format operating hours" }));
  expect(floors()[0]!.choice).toEqual(expect.objectContaining({ open_hour: 9, close_hour: 21, closed_days: [7] }));
  expect(floors()[1]!.choice).toEqual(expect.objectContaining({ open_hour: null, close_hour: null, closed_days: null }));
  expect(screen.getByText(/Applies 07:00–22:00 and 5 open days/)).toBeTruthy();
  fireEvent.click(share());
  expect(floors().map((f) => f.choice.closed_days)).toEqual([[6, 7], [6, 7]]);
  expect(floors().map((f) => f.choice.open_hour)).toEqual([7, 7]);
});

it("resolves partial hours, then permits independent overrides and repeated application", async () => {
  await mount({ open_hour: 6 });
  fireEvent.click(share());
  expect(floors().map((f) => [f.choice.open_hour, f.choice.close_hour])).toEqual([[6, 21], [6, 21]]);
  fireEvent.change(screen.getByLabelText("Closing hour (1–24)"), { target: { value: "24" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Sunday" }));
  expect(floors()[1]!.choice).toEqual(expect.objectContaining({ close_hour: 21, closed_days: [7] }));
  fireEvent.change(screen.getByLabelText("Opening hour (0–23)"), { target: { value: "0" } });
  fireEvent.click(share());
  expect(floors().map((f) => [f.choice.open_hour, f.choice.close_hour, f.choice.closed_days])).toEqual([[0, 24, []], [0, 24, []]]);
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ open_hour: 0, close_hour: 24, closed_days: [] }), expect.any(AbortSignal)));
});

it.each([{ close_hour: 8 }, { open_hour: 21 }, { open_hour: 23, close_hour: 22 }, { open_hour: 2.5 }, { close_hour: 25 }])(
  "blocks invalid effective hours from overwriting other floors: %j", async (patch) => {
    await mount(patch);
    expect(share().disabled).toBe(true);
    fireEvent.click(share());
    expect(floors()[1]).toEqual(initial[1]);
    fireEvent.click(screen.getByRole("button", { name: "Use format operating hours" }));
    expect(share().disabled).toBe(false);
  });

it("does not show building-wide actions on a single layout", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><TemplatePicker value={initial[0]!.choice} onChange={vi.fn()} /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Operating hours · 6 open days"));
  expect(screen.queryByRole("button", { name: /operating hours to all floors/ })).toBeNull();
});

it("shares across six floors and does not silently assign hours to a newly added floor", async () => {
  await mount();
  fireEvent.click(share());
  for (let count = 2; count < 6; count++) fireEvent.click(screen.getByRole("button", { name: "Add floor" }));
  expect((screen.getByRole("button", { name: "Add floor" }) as HTMLButtonElement).disabled).toBe(true);
  expect(floors().slice(2).every((f) => f.choice.open_hour === null)).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "1F · Pharmacy" }));
  fireEvent.click(screen.getByText("Operating hours · 6 open days"));
  expect(share().disabled).toBe(false);
  fireEvent.click(share());
  expect(floors()).toHaveLength(6);
  expect(floors().every((f) => f.choice.open_hour === 9 && f.choice.close_hour === 21)).toBe(true);
  expect(floors().map((f) => f.choice.closed_days)).toEqual(Array.from({ length: 6 }, () => [7]));
});

it("keeps already shared hours when a floor is duplicated or reordered", async () => {
  await mount();
  fireEvent.click(share());
  fireEvent.click(screen.getByRole("button", { name: "Duplicate floor" }));
  fireEvent.click(screen.getByText("Operating hours · 6 open days"));
  expect((screen.getByRole("button", { name: "Operating hours used on all floors" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Move to higher level" }));
  expect(floors().map((f) => f.label)).toEqual(["Pharmacy", "Café", "Pharmacy copy 1"]);
  fireEvent.click(screen.getByText("Operating hours · 6 open days"));
  fireEvent.change(screen.getByLabelText("Closing hour (1–24)"), { target: { value: "23" } });
  expect(floors().map((f) => f.choice.close_hour)).toEqual([21, 21, 23]);
  fireEvent.click(share());
  expect(floors().map((f) => f.choice.close_hour)).toEqual([23, 23, 23]);
});
