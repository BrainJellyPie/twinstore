// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/starterFill";
import { ApiError } from "@/shared/api/errors";
import { StarterFill } from "../StarterFill";
import { starterCategoryLabel } from "@/shared/i18n/catalogCategories";
import { starterRackReason } from "../starterRackReason";
import { LOCALES, type Locale, type MessageKey } from "@/shared/i18n/messages";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { useSimulationStore } from "@/stores/simulationStore";

vi.mock("@/shared/api/starterFill", () => ({ getStarterCatalog: vi.fn(), autoSelectStarterProducts: vi.fn(), previewStarterFill: vi.fn(), saveStarterFill: vi.fn() }));
const product = { sku: "茶🌿", name: "My local tea", price: 231, regular_price: 299, promo: "2 + 1", image_url: "/tea.png" };
const catalog: api.StarterCatalog = { source_sha256: "a".repeat(64), currency: "USD", categories: [
  { key: "home_coffee_tea", label: "Coffee & tea", products: [product] },
  { key: "water_sports", label: "Water & sports drinks", products: [{ ...product, sku: "zero", price: 0 }] },
], racks: [
  { id: "棚_1", name: "Café 🌿", type: "fridge", available_slots: 8, suggested_category: "home_coffee_tea", reason: null },
  { id: "stocked", name: "Existing", type: "shelf", available_slots: 0, suggested_category: null, reason: "Already contains products; kept unchanged", reason_code: "occupied" },
  { id: "locked", name: "Locked", type: "fridge", available_slots: 0, suggested_category: null, reason: "No accessible, unlocked product face", reason_code: "no_accessible_face" },
] };
const report: api.StarterPreview = { placements_added: 8, new_skus: 0, reused_skus: 1,
  racks: [{ id: "棚_1", name: "Café 🌿", category: "home_coffee_tea", slots_added: 8, placements_added: 8, products: [product], reused_skus: [product.sku] }] };
const automatic: api.StarterRequest = { source_sha256: catalog.source_sha256, currency: "USD", products_per_slot: 2,
  assignments: [{ rack_id: "棚_1", category: "home_coffee_tea", skus: [product.sku] }] };
let qc: QueryClient;
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  useLocale.getState().setLocale("en");
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.mocked(api.getStarterCatalog).mockResolvedValue(catalog);
  vi.mocked(api.autoSelectStarterProducts).mockResolvedValue(automatic);
  vi.mocked(api.previewStarterFill).mockResolvedValue(report);
  vi.mocked(api.saveStarterFill).mockResolvedValue({ setup_id: "setup_stocked", placements_added: 8 });
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); vi.unstubAllGlobals(); useSimulationStore.getState().reset(); useLocale.getState().setLocale("en"); });
async function open(locale: Locale = "en", manual = true) {
  useLocale.getState().setLocale(locale);
  render(<QueryClientProvider client={qc}><StarterFill pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: t("starterEntry") }));
  await screen.findByLabelText(t("starterManualMode"));
  if (manual) fireEvent.click(screen.getByLabelText(t("starterManualMode")));
}
async function preview() {
  fireEvent.click(screen.getByRole("button", { name: t("starterSelectShown") }));
  fireEvent.click(screen.getByRole("button", { name: t("starterPreview") }));
  await screen.findByRole("button", { name: t("starterSave") });
}
it.each(LOCALES)("fills, reviews, saves and opens in $label without translating stored product identities", async ({ code }) => {
  await open(code);
  expect(screen.getByText(t("starterExamples", { editor: t("bulkTitle") }))).toBeTruthy();
  expect(screen.getByText(t("copyReasonOccupied"))).toBeTruthy();
  expect(screen.getByText(t("starterNoFace"))).toBeTruthy();
  expect(screen.getByRole("checkbox", { name: t("starterSelectRack", { rack: "stocked" }) }).matches(":disabled")).toBe(true);
  fireEvent.change(screen.getByLabelText(t("starterCategoryToApply")), { target: { value: "home_coffee_tea" } });
  expect(screen.getByText(t("starterReferenceProducts", { category: starterCategoryLabel("home_coffee_tea", "Coffee & tea", code) }))).toBeTruthy();
  await preview();
  const region = screen.getByRole("region", { name: t("starterPreviewRegion") });
  expect(region.textContent).toContain("My local tea");
  expect(region.textContent).toContain(t("starterExistingValues"));
  expect(region.textContent).not.toMatch(/\{(?:count|racks|placements|name)\}/);
  fireEvent.click(screen.getByRole("button", { name: t("starterSave") }));
  fireEvent.click(await screen.findByRole("button", { name: t("starterOpen") }));
  expect(useSimulationStore.getState().selectedSetupId).toBe("setup_stocked");
  expect(vi.mocked(api.saveStarterFill).mock.calls[0]![2]).toEqual({ source_sha256: catalog.source_sha256, currency: "USD",
    assignments: [{ rack_id: "棚_1", category: "home_coffee_tea" }], products_per_slot: 2, request_id: expect.stringMatching(/^[a-f0-9]{32}$/) });
  expect(api.autoSelectStarterProducts).not.toHaveBeenCalled();
});
it("retains a translated accent-insensitive search and hidden choices when changing languages", async () => {
  await open("fr");
  fireEvent.change(screen.getByLabelText(t("starterSearch")), { target: { value: "refrigerateur cafe" } });
  fireEvent.click(screen.getByRole("button", { name: t("starterSelectShown") }));
  act(() => useLocale.getState().setLocale("ja"));
  expect((screen.getByLabelText(t("starterSearch")) as HTMLInputElement).value).toBe("refrigerateur cafe");
  expect((screen.getByLabelText(t("starterSelectRack", { rack: "棚_1" })) as HTMLInputElement).checked).toBe(true);
  fireEvent.change(screen.getByLabelText(t("starterSearch")), { target: { value: "absent" } });
  expect(screen.getByText(t("starterNoMatch"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("starterPreview") }));
  await screen.findByRole("button", { name: t("starterSave") });
  expect(vi.mocked(api.previewStarterFill).mock.calls[0]![2].assignments).toEqual([{ rack_id: "棚_1", category: "home_coffee_tea" }]);
});
it("retranslates pending model selection and save failure without losing requirements or retry identity", async () => {
  let finish!: (value: api.StarterRequest) => void;
  let fail!: (error: Error) => void;
  vi.mocked(api.autoSelectStarterProducts).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  vi.mocked(api.saveStarterFill).mockReturnValueOnce(new Promise((_resolve, reject) => { fail = reject; }));
  await open("en", false);
  const requirement = "  茶とコーヒー 🌿 — no alcohol  ";
  fireEvent.change(screen.getByLabelText(t("starterRequirements")), { target: { value: requirement } });
  fireEvent.click(screen.getByRole("button", { name: t("starterAutoPreview") }));
  await waitFor(() => expect(api.autoSelectStarterProducts).toHaveBeenCalledTimes(1));
  act(() => useLocale.getState().setLocale("ko"));
  expect((screen.getByLabelText(t("starterRequirements")) as HTMLTextAreaElement).value).toBe(requirement);
  expect(screen.getByRole("button", { name: t("starterChoosing") }).matches(":disabled")).toBe(true);
  await act(async () => finish(automatic));
  fireEvent.click(await screen.findByRole("button", { name: t("starterSave") }));
  await waitFor(() => expect(api.saveStarterFill).toHaveBeenCalledTimes(1));
  act(() => useLocale.getState().setLocale("fr"));
  expect(screen.getByRole("button", { name: t("starterSaving") }).matches(":disabled")).toBe(true);
  await act(async () => fail(new ApiError("Currency changed", 409)));
  await screen.findByText(t("requestConflict"));
  act(() => useLocale.getState().setLocale("zh"));
  expect(screen.getByText(t("requestConflict"))).toBeTruthy();
  expect(screen.getByText(t("copyUncertain"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("starterRetrySave") }));
  await screen.findByRole("button", { name: t("starterOpen") });
  expect(vi.mocked(api.saveStarterFill).mock.calls[1]![2]).toEqual(vi.mocked(api.saveStarterFill).mock.calls[0]![2]);
  expect(vi.mocked(api.autoSelectStarterProducts).mock.calls[0]![2].requirements).toBe(requirement.trim());
  expect(vi.mocked(api.saveStarterFill).mock.calls[0]![2].assignments).toEqual(automatic.assignments);
});
it("retranslates validation and missing-layout recovery instead of retaining the old language", async () => {
  vi.mocked(api.getStarterCatalog).mockRejectedValueOnce(new ApiError("Missing source", 404)).mockResolvedValue({ ...catalog, racks: [{ ...catalog.racks[0]!, suggested_category: null }] });
  useLocale.getState().setLocale("es");
  render(<QueryClientProvider client={qc}><StarterFill pid="p" sid="s" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: t("starterEntry") }));
  await screen.findByText(t("requestMissing"));
  act(() => useLocale.getState().setLocale("ja"));
  expect(screen.getByText(t("requestMissing"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("starterRetry") }));
  fireEvent.click(await screen.findByLabelText(t("starterManualMode")));
  fireEvent.click(screen.getByRole("button", { name: t("starterSelectShown") }));
  fireEvent.click(screen.getByRole("button", { name: t("starterPreview") }));
  await screen.findByText(t("starterChooseCategoryEach"));
  act(() => useLocale.getState().setLocale("ko"));
  expect(screen.getByText(t("starterChooseCategoryEach"))).toBeTruthy();
  expect(api.previewStarterFill).not.toHaveBeenCalled();
  expect(api.saveStarterFill).not.toHaveBeenCalled();
});
it("preserves unknown category and reason labels, and supports old reason-only servers", () => {
  for (const { code } of LOCALES) {
    expect(starterRackReason({ ...catalog.racks[0]!, reason: "No accessible, unlocked product face" }, code)).toBe(translate(code, "starterNoFace"));
    expect(starterRackReason({ ...catalog.racks[0]!, reason: "New wording", reason_code: "occupied" }, code)).toBe(translate(code, "copyReasonOccupied"));
    expect(starterRackReason({ ...catalog.racks[0]!, reason: "Future rule", reason_code: "__proto__" }, code)).toBe("Future rule");
    expect(starterCategoryLabel("__proto__", "User category", code)).toBe("User category");
    expect(starterCategoryLabel("future_key", "品類 🍵", code)).toBe("品類 🍵");
  }
});
it("shows English category labels in a KRW store without rewriting Korean product names", async () => {
  vi.mocked(api.getStarterCatalog).mockResolvedValue({ ...catalog, currency: "KRW", categories: [
    { key: "water_sports", label: "생수·스포츠음료", products: [{ ...product, name: "우리 생수", price: 0 }] },
  ] });
  await open();
  const category = screen.getByLabelText(t("starterCategoryToApply"));
  expect(category.textContent).toContain("Water & sports drinks");
  expect(category.textContent).not.toContain("생수·스포츠음료");
  fireEvent.change(category, { target: { value: "water_sports" } });
  expect(screen.getByText(/우리 생수/).textContent).toContain("₩0");
});
it("names the actual translated product editor in the price-review instructions", async () => {
  await open("fr");
  const notice = screen.getByText(/Les produits génériques/);
  expect(notice.textContent).toContain(t("bulkTitle"));
});

it.each(LOCALES)("keeps new category IDs intact in a KRW store in $code", async ({ code }) => {
  const keys = ["cycling_maintenance", "swimming_gear", "climbing_accessories", "desk_organization",
    "aquarium_decor", "bird_supplies", "home_lighting", "bathroom_accessories", "home_linen",
    "dinnerware", "food_storage", "pet_grooming", "hair_accessories", "woodcraft_supplies",
    "ceramic_craft_supplies", "gift_wrapping",
    "baby_feeding", "baby_bath", "toy_vehicles", "plush_toys", "educational_toys", "puzzle_games", "model_building_supplies", "miniature_painting",
    "facial_skincare", "makeup_accessories", "nail_grooming", "shaving_grooming", "tea_brewing_tools", "baking_decorating", "pantry_organization", "shoe_care",
    "yoga_pilates", "running_accessories", "fishing_tackle", "leathercraft", "seed_starting", "plant_propagation", "candle_care", "camp_repair",
    "pet_walking", "car_detailing", "composting_tools", "watering_irrigation", "embroidery", "knitting_crochet", "paper_crafting", "food_gift_packaging"];
  const originalProduct = { ...product, name: "원본 상품 🌿", price: 123400 };
  vi.mocked(api.getStarterCatalog).mockResolvedValue({ ...catalog, currency: "KRW",
    categories: keys.map(key => ({ key, label: `API label ${key}`, products: [originalProduct] })),
    racks: keys.map(key => ({ ...catalog.racks[0]!, id: `rack_${key}`, suggested_category: key })),
  });
  vi.mocked(api.previewStarterFill).mockResolvedValue({ placements_added: keys.length * 8, new_skus: 0, reused_skus: 1,
    racks: keys.map(key => ({ ...report.racks[0]!, id: `rack_${key}`, category: key, products: [originalProduct] })),
  });
  await open(code);
  const select = screen.getByLabelText(t("starterCategoryToApply")) as HTMLSelectElement;
  expect(Array.from(select.options).map(option => option.value).filter(Boolean)).toEqual(keys);
  expect(select.textContent).not.toContain("API label");
  fireEvent.click(screen.getByRole("button", { name: t("starterSelectShown") }));
  fireEvent.click(screen.getByRole("button", { name: t("starterPreview") }));
  await screen.findByRole("button", { name: t("starterSave") });
  expect(vi.mocked(api.previewStarterFill).mock.lastCall?.[2]).toEqual({
    source_sha256: catalog.source_sha256, currency: "KRW", products_per_slot: 2,
    assignments: keys.map(key => ({ rack_id: `rack_${key}`, category: key })),
  });
  expect(screen.getByRole("region", { name: t("starterPreviewRegion") }).textContent).toContain(originalProduct.name);
  expect(api.autoSelectStarterProducts).not.toHaveBeenCalled();
});
