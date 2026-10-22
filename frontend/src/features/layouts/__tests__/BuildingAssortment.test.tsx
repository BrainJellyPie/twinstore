// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { BuildingPicker } from "../components/BuildingPicker";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, type BuildingFloorChoice, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => {
  const common = { description: "Retail", grid: [16, 12] as [number, number], racks: 10, skus: 40, open_hours: [9, 21] as [number, number], default_style: "aisles" as const, default_design: "classic" as const, default_dining_tables: 0 };
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { ...common, id: "urban_cvs", name: "City store", store_type: "convenience",
      categories: [{ id: "soft_drinks", label: "Drinks" }, { id: "household", label: "Household" }] },
    { ...common, id: "electronics_shop", name: "Electronics", store_type: "electronics",
      categories: [{ id: "electronics", label: "Electronics" }] },
  ]);
  vi.mocked(api.previewStoreTemplate).mockImplementation(async (request) => {
    if (request.template_id === "electronics_shop" && request.excluded_categories?.includes("electronics"))
      throw new Error("Keep at least one product category for this store format.");
    return { id: request.template_id, name: "Floor", type: "store", grid_size: [request.width ?? 16, request.height ?? 12], weekly_schedule: [], racks: [] };
  });
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
function initial(count = 2, patch: Partial<TemplateChoice> = {}): BuildingFloorChoice[] {
  return Array.from({ length: count }, (_, i) => ({ label: `Floor ${i + 1}`, choice: { ...DEFAULT_TEMPLATE_CHOICE,
    templateId: i % 2 ? "electronics_shop" : "urban_cvs", seed: i, width: 16 + i, height: 12 + i,
    currency: i % 2 ? "JPY" : "USD", design_theme: i % 2 ? "nordic" : "coastal", open_hour: 8 + i, close_hour: 22,
    requirements: `Keep floor ${i + 1}`, reserved_areas: [{ label: "Pickup", x: 2, y: 2, width: 2, height: 3 }],
    products_per_category: i ? 5 : 2, category_product_limits: i ? { electronics: 8 } : { soft_drinks: 3, electronics: 1 },
    excluded_categories: i ? [] : ["household"], ...(i === 0 ? patch : {}),
  } }));
}
function Building({ starting }: { starting: BuildingFloorChoice[] }) {
  const [floors, setFloors] = useState(starting);
  return <><BuildingPicker floors={floors} onChange={setFloors} /><output data-testid="floors">{JSON.stringify(floors)}</output>
    <output data-testid="limit-maps">{new Set(floors.map((f) => f.choice.category_product_limits)).size}</output>
    <output data-testid="exclusion-arrays">{new Set(floors.map((f) => f.choice.excluded_categories)).size}</output></>;
}
async function mount(starting = initial()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><Building starting={starting} /></QueryClientProvider>);
  await screen.findByRole("radio", { name: /^City store/ });
  fireEvent.click(screen.getByText(/^Product categories/));
}
const floors = (): BuildingFloorChoice[] => JSON.parse(screen.getByTestId("floors").textContent!);
const apply = () => screen.getByRole("button", { name: "Apply assortment to all floors" }) as HTMLButtonElement;
async function closeReview() {
  fireEvent.click(within(screen.getByRole("dialog", { name: "Review building floors" })).getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull());
}

it.each([2, 6])("shares only assortment fields across %i floors and keeps later edits independent", async (count) => {
  const before = initial(count); await mount(before); expect(floors()).toEqual(before);
  fireEvent.click(apply()); await screen.findByText(`Floor previews ready: ${count}/${count}`);
  const source = before[0]!.choice;
  expect(floors()).toEqual(before.map((f) => ({ ...f, choice: { ...f.choice, seed: source.seed,
    products_per_category: source.products_per_category, category_product_limits: source.category_product_limits, excluded_categories: source.excluded_categories } })));
  expect(screen.getByTestId("limit-maps").textContent).toBe(String(count));
  expect(screen.getByTestId("exclusion-arrays").textContent).toBe(String(count));
  await closeReview();
  expect((screen.getByRole("button", { name: "Assortment used on all floors" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "2F · Floor 2" }));
  fireEvent.click(screen.getByText(/^Product categories/));
  fireEvent.change(screen.getByLabelText("Products for Electronics"), { target: { value: "4" } });
  expect(floors().map((f) => f.choice.category_product_limits?.electronics)).toEqual(Array.from({ length: count }, (_, i) => i === 1 ? 4 : 1));
  expect(apply().disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Shuffle assortment (#0)" }));
  expect(floors().map((f) => f.choice.seed)).toEqual(Array.from({ length: count }, (_, i) => i === 1 ? 1 : 0));
});

it("reviews an excluded-only floor and recovers that floor without changing the source", async () => {
  await mount(initial(2, { excluded_categories: ["electronics"] })); fireEvent.click(apply());
  const review = screen.getByRole("dialog", { name: "Review building floors" });
  expect(await within(review).findByText(/Keep at least one product category/)).toBeTruthy();
  fireEvent.click(within(review).getByRole("button", { name: "Edit floor 2" }));
  await waitFor(() => expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull());
  fireEvent.click(screen.getByText(/^Product categories/));
  fireEvent.click(screen.getByRole("button", { name: "Restore all product categories" }));
  expect(floors().map((f) => f.choice.excluded_categories)).toEqual([["electronics"], []]);
  fireEvent.click(screen.getByRole("button", { name: "Review all floors" }));
  await screen.findByText("Floor previews ready: 2/2");
});

it.each<Partial<TemplateChoice>>([
  { products_per_category: 0 }, { category_product_limits: { soft_drinks: 17 } }, { seed: Number.MAX_SAFE_INTEGER + 1 },
])("holds invalid assortment values without replacing other floors: %o", async (patch) => {
  const before = initial(2, patch); await mount(before); expect(apply().disabled).toBe(true); fireEvent.click(apply());
  expect(floors()[1]).toEqual(before[1]); expect(screen.queryByRole("dialog", { name: "Review building floors" })).toBeNull();
});
it("does not show a building action on an individual layout", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><TemplatePicker value={initial()[0]!.choice} onChange={vi.fn()} /></QueryClientProvider>);
  await screen.findByRole("radio", { name: /^City store/ }); fireEvent.click(screen.getByText(/^Product categories/));
  expect(screen.queryByRole("button", { name: /assortment to all floors/ })).toBeNull();
});

it("leaves a newly added floor at its own defaults until assortment is applied again", async () => {
  await mount(); fireEvent.click(apply()); await screen.findByText("Floor previews ready: 2/2"); await closeReview();
  fireEvent.click(screen.getByRole("button", { name: "Add floor" }));
  expect(floors()[2]!.choice).toMatchObject({ products_per_category: null, category_product_limits: {}, excluded_categories: [], seed: 0 });
  fireEvent.click(screen.getByRole("button", { name: "1F · Floor 1" }));
  fireEvent.click(screen.getByText(/^Product categories/));
  expect(apply().disabled).toBe(false);
  fireEvent.click(apply()); await screen.findByText("Floor previews ready: 3/3");
  expect(floors()[2]!.choice).toMatchObject({ products_per_category: 2, category_product_limits: { soft_drinks: 3, electronics: 1 }, excluded_categories: ["household"] });
});


it("keeps directly entered seeds independent until shared across floors", async () => {
  await mount();
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: "-42" } });
  fireEvent.click(screen.getByRole("button", { name: "2F · Floor 2" }));
  expect((screen.getByLabelText("Assortment seed") as HTMLInputElement).value).toBe("1");
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: String(Number.MAX_SAFE_INTEGER) } });
  expect(floors().map((floor) => floor.choice.seed)).toEqual([-42, Number.MAX_SAFE_INTEGER]);
  fireEvent.click(screen.getByRole("button", { name: "1F · Floor 1" }));
  expect((screen.getByLabelText("Assortment seed") as HTMLInputElement).value).toBe("-42");
  fireEvent.click(screen.getByText(/^Product categories/));
  fireEvent.click(apply()); await screen.findByText("Floor previews ready: 2/2");
  expect(floors().map((floor) => floor.choice.seed)).toEqual([-42, -42]);
  expect(floors().map((floor) => floor.choice.width)).toEqual([16, 17]);
  await closeReview();
});

it("blocks sharing invalid seed text and recovers after correction without changing another floor", async () => {
  await mount(); const other = floors()[1];
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: "9007199254740990.1" } });
  expect(apply().disabled).toBe(true); fireEvent.click(apply());
  expect(floors()[1]).toEqual(other);
  expect((screen.getByRole("button", { name: "Export building options" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: "-42" } });
  expect(apply().disabled).toBe(false);
  expect(floors()[1]).toEqual(other);
});
