// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
let client: QueryClient;
const format: api.StoreTemplate = { id: "fashion_boutique", name: "Boutique", description: "", store_type: "fashion", grid: [22, 18], racks: 0, skus: 0, open_hours: [9, 18], default_style: "aisles", default_design: "classic", default_dining_tables: 0 };
beforeEach(() => {
  useLocale.getState().setLocale("en");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Boutique", type: "fashion", grid_size: [22, 18], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); client.clear(); vi.resetAllMocks(); });
function mount(patch: Partial<TemplateChoice> = {}) {
  const onChange = vi.fn();
  render(<QueryClientProvider client={client}><TemplatePicker value={{ ...DEFAULT_TEMPLATE_CHOICE, templateId: format.id, ...patch }} onChange={onChange} /></QueryClientProvider>);
  return onChange;
}
it("uses confirmed preview dimensions while formats are still loading instead of a temporary 12×10 grid", async () => {
  vi.mocked(api.getStoreTemplates).mockReturnValue(new Promise(() => {}));
  let resolve!: (store: Awaited<ReturnType<typeof api.previewStoreTemplate>>) => void;
  vi.mocked(api.previewStoreTemplate).mockReturnValue(new Promise(done => { resolve = done; }));
  const onChange = mount();
  const add = screen.getByRole("button", { name: "Add reserved area" });
  expect(add.matches(":disabled")).toBe(true);
  fireEvent.click(add); expect(onChange).not.toHaveBeenCalled();
  await act(async () => resolve({ id: "preview", name: "Boutique", type: "fashion", grid_size: [22, 18], weekly_schedule: [], racks: [] }));
  await waitFor(() => expect(add.matches(":disabled")).toBe(false));
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "pickup" } });
  fireEvent.click(add);
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ reserved_areas: [{ label: "Pickup", x: 2, y: 14, width: 3, height: 2 }] }));
});
it("keeps explicit dimensions usable when the format list fails, but does not invent a missing dimension", async () => {
  vi.mocked(api.getStoreTemplates).mockRejectedValue(new Error("Formats unavailable"));
  vi.mocked(api.previewStoreTemplate).mockReturnValue(new Promise(() => {}));
  const onChange = mount({ width: 8, height: 6 });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ reserved_areas: [{ label: "Reserved area 1", x: 2, y: 2, width: 3, height: 3 }] }));
  cleanup();
  mount({ width: 8 });
  expect(screen.getByRole("button", { name: "Add reserved area" }).matches(":disabled")).toBe(true);
});

it("does not reuse the previous format's preview size while a different format is loading", async () => {
  vi.mocked(api.getStoreTemplates).mockReturnValue(new Promise(() => {}));
  let resolve!: (store: Awaited<ReturnType<typeof api.previewStoreTemplate>>) => void;
  vi.mocked(api.previewStoreTemplate).mockResolvedValueOnce({ id: "first", name: "Boutique", type: "fashion", grid_size: [22, 18], weekly_schedule: [], racks: [] })
    .mockImplementation(() => new Promise(done => { resolve = done; }));
  const onChange = vi.fn();
  const component = (templateId: string) => <QueryClientProvider client={client}><TemplatePicker value={{ ...DEFAULT_TEMPLATE_CHOICE, templateId }} onChange={onChange} /></QueryClientProvider>;
  const view = render(component(format.id));
  await screen.findByRole("img", { name: "Floor plan preview" });
  expect(screen.getByRole("button", { name: "Add reserved area" }).matches(":disabled")).toBe(false);
  view.rerender(component("book_cafe"));
  expect(screen.getByRole("button", { name: "Add reserved area" }).matches(":disabled")).toBe(true);
  await act(async () => resolve({ id: "second", name: "Cafe", type: "cafe", grid_size: [8, 6], weekly_schedule: [], racks: [] }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Add reserved area" }).matches(":disabled")).toBe(false));
  fireEvent.change(screen.getByLabelText("Area starting point"), { target: { value: "pickup" } });
  fireEvent.click(screen.getByRole("button", { name: "Add reserved area" }));
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ templateId: "book_cafe", reserved_areas: [{ label: "Pickup", x: 2, y: 2, width: 3, height: 2 }] }));
});
