// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { BuildingPicker } from "../components/BuildingPicker";
import { choiceFromGeneration, DEFAULT_TEMPLATE_CHOICE, resolveOperatingHours, templateRequest, validTemplateChoice, validWeeklyHours, type BuildingFloorChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
const clients: QueryClient[] = [];
const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const week = () => days.map((_, index) => ({ day: index + 1, is_open: index < 6, open_hour: 9, close_hour: 21 }));
beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "community_pharmacy", name: "Community pharmacy", description: "Care", store_type: "pharmacy", grid: [14, 12], racks: 12, skus: 50,
      open_hours: [9, 21], closed_days: [7], default_style: "spine", default_design: "minimal", default_dining_tables: 0 },
    { id: "specialty_cafe", name: "Specialty café", description: "Coffee", store_type: "cafe", grid: [18, 14], racks: 20, skus: 40,
      open_hours: [7, 22], closed_days: [6, 7], default_style: "perimeter", default_design: "warm", default_dining_tables: 6 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => ({ id: "preview", name: "Preview", type: "store",
    grid_size: [request.width ?? 14, request.height ?? 12], weekly_schedule: request.weekly_hours ?? week(), racks: [] }));
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.restoreAllMocks(); vi.resetAllMocks(); });
const initial: BuildingFloorChoice[] = [
  { label: "Pharmacy", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "community_pharmacy", width: 30, currency: "JPY", design_colors: { wall: "#123456" }, requirements: "Keep consultation" } },
  { label: "Café", choice: { ...DEFAULT_TEMPLATE_CHOICE, templateId: "specialty_cafe", height: 24, seed: 4, table_mix: { two_seat: 2, four_seat: 1, six_seat: 1 }, dining_tables: 4 } },
];
function Building({ starting }: { starting: BuildingFloorChoice[] }) {
  const [floors, setFloors] = useState(starting);
  return <><BuildingPicker floors={floors} onChange={setFloors} /><output data-testid="floors">{JSON.stringify(floors)}</output>
    <output data-testid="shared-week">{String(floors[0]!.choice.weekly_hours?.[0] === floors[1]!.choice.weekly_hours?.[0])}</output></>;
}
async function mount(starting = initial) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><Building starting={starting} /></QueryClientProvider>);
  await screen.findByRole("img", { name: "Floor plan preview" });
  fireEvent.click(screen.getByText("Operating hours · Open days: 6"));
}
const floors = (): BuildingFloorChoice[] => JSON.parse(screen.getByTestId("floors").textContent!);
const toggle = () => fireEvent.click(screen.getByRole("checkbox", { name: "Set hours for each weekday" }));
const input = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const set = (name: string, value: string) => fireEvent.change(input(name), { target: { value } });
const share = () => fireEvent.click(screen.getByRole("button", { name: "Apply operating hours to all floors" }));

it("starts from the effective schedule, copies independent weekday entries and restores shared hours", async () => {
  await mount(); toggle(); expect(floors()[0]!.choice.weekly_hours).toEqual(week());
  set("Monday opening hour", "0"); set("Monday closing hour", "24");
  set("Saturday opening hour", "12"); set("Saturday closing hour", "16");
  expect(input("Sunday opening hour").disabled).toBe(true);
  share(); expect(screen.getByTestId("shared-week").textContent).toBe("false");
  expect(floors()[0]!.choice.weekly_hours).toEqual(floors()[1]!.choice.weekly_hours);
  initial.forEach((floor, index) => {
    const { weekly_hours: _week, open_hour: _open, close_hour: _close, closed_days: _days, ...rest } = floors()[index]!.choice;
    const { weekly_hours: _oldWeek, open_hour: _oldOpen, close_hour: _oldClose, closed_days: _oldDays, ...old } = floor.choice;
    expect(rest).toEqual(old);
  });
  fireEvent.click(screen.getByRole("button", { name: "2F · Café" })); fireEvent.click(screen.getByText("Operating hours · Open days: 6"));
  set("Monday closing hour", "18"); expect(floors()[0]!.choice.weekly_hours?.[0]?.close_hour).toBe(24);
  toggle(); expect(input("Opening hour (0–23)").value).toBe("9"); share();
  expect(floors().every((floor) => floor.choice.weekly_hours === null)).toBe(true);
  expect(floors().map((floor) => floor.choice.closed_days)).toEqual([[7], [7]]);
});

it("retains the last open day, blocks blank and reversed windows, and recovers without React warnings", async () => {
  const errors = vi.spyOn(console, "error").mockImplementation(() => {});
  await mount(); toggle();
  for (const day of days.slice(1)) { const box = screen.getByRole("checkbox", { name: day }) as HTMLInputElement; if (box.checked) fireEvent.click(box); }
  expect((screen.getByRole("checkbox", { name: "Monday" }) as HTMLInputElement).disabled).toBe(true);
  set("Monday closing hour", ""); expect(input("Monday closing hour").value).toBe("");
  expect(screen.getByText(/^Enter whole hours/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Export building options" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Apply operating hours to all floors" }) as HTMLButtonElement).disabled).toBe(true);
  set("Monday closing hour", "9"); expect(screen.getByText(/^Enter whole hours/)).toBeTruthy();
  set("Monday closing hour", "24"); await screen.findByRole("img", { name: "Floor plan preview" });
  expect(screen.queryAllByRole("alert")).toHaveLength(0);
  expect(floors()[0]!.choice.weekly_hours?.filter((day) => day.is_open)).toHaveLength(1);
  expect(errors).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Use format operating hours" }));
  expect(floors()[0]!.choice.weekly_hours).toBeNull(); expect(floors()[0]!.choice.requirements).toBe("Keep consultation");
});

it("keeps individual hours when switching formats whose shared defaults would conflict", async () => {
  await mount([{ ...initial[0]!, choice: { ...initial[0]!.choice, close_hour: 8, weekly_hours: week() } }, initial[1]!]);
  expect(input("Monday closing hour").value).toBe("21");
  fireEvent.click(screen.getByRole("radio", { name: /Specialty café/ }));
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ template_id: "specialty_cafe", weekly_hours: week(), close_hour: 8 }), expect.any(AbortSignal)));
  expect(floors()[0]!.choice.weekly_hours).toEqual(week());
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" })); expect(floors()[0]!.choice.weekly_hours).toBeNull();
});

it.each([[], week().slice(1), [...week(), week()[0]!], week().map((entry) => ({ ...entry, day: 1 })), week().map((entry) => ({ ...entry, is_open: false })), [{ ...week()[0]!, close_hour: 9 }, ...week().slice(1)]].map((weekly_hours) => ({ weekly_hours })))("blocks invalid weeks before preview/export/bulk: %j", ({ weekly_hours }) => {
  expect(validWeeklyHours(weekly_hours)).toBe(false);
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, weekly_hours })).toBe(false);
  expect(resolveOperatingHours({ weekly_hours }, { open_hours: [9, 21] })).toBeNull();
});

it("keeps schedules in file requests and source reuse without confusing inactive shared hours", () => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, open_hour: 23, close_hour: 1, closed_days: [1, 2, 3, 4, 5, 6, 7], weekly_hours: week() };
  expect(validTemplateChoice(choice)).toBe(true);
  expect(resolveOperatingHours(choice, { open_hours: [9, 21] })?.weekly_hours).toEqual(week());
  expect(choiceFromGeneration(templateRequest(choice), "source").weekly_hours).toEqual(week());
  expect(validTemplateChoice({ ...choice, weekly_hours: null })).toBe(false);
});
