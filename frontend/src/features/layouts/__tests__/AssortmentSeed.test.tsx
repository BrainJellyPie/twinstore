// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn(), validateLayoutPreset: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([{ id: "urban_cvs", name: "City store", description: "Groceries", store_type: "convenience",
    grid: [12, 10], racks: 10, skus: 40, open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0 }]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Preview", type: "convenience", grid_size: [24, 18], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
function Picker({ seed }: { seed: number }) {
  const [value, onChange] = useState<TemplateChoice>({ ...DEFAULT_TEMPLATE_CHOICE, seed, width: 24, height: 18, currency: "JPY", requirements: "Keep pickup space" });
  return <><TemplatePicker value={value} onChange={onChange} /><output data-testid="seed">{String(value.seed)}</output>
    <button onClick={() => onChange({ ...value, seed: -7 })}>Restore saved seed</button></>;
}
async function mount(seed = 0) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><Picker seed={seed} /></QueryClientProvider>);
  await screen.findByRole("radio", { name: /^Urban convenience store/ });
  await screen.findByRole("img", { name: "Floor plan preview" });
}

it.each([
  ["-9007199254740991", Number.MIN_SAFE_INTEGER], ["-42", -42], ["-1", -1], ["0", 0], ["-0", -0],
  ["1", 1], [" +00042 ", 42], ["9007199254740990", Number.MAX_SAFE_INTEGER - 1], ["9007199254740991", Number.MAX_SAFE_INTEGER],
])("previews exact whole-number seed %s without changing other options", async (text, seed) => {
  await mount(2);
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: text } });
  expect((screen.getByLabelText("Assortment seed") as HTMLInputElement).value).toBe(text);
  expect(screen.getByLabelText("Assortment seed").getAttribute("aria-invalid")).toBe("false");
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ seed, width: 24, height: 18, currency: "JPY" }), expect.any(AbortSignal)));
  await waitFor(() => expect((screen.getByRole("button", { name: "Export options" }) as HTMLButtonElement).disabled).toBe(false));
});

it.each(["", " ", "-", "+", "1.5", "1e3", "0x10", "NaN", "Infinity", "9007199254740992", "-9007199254740992", "9007199254740991.1", "9007199254740990.1", "9".repeat(400), "12 3", "--1", "−1"])("keeps invalid seed text %s visible and blocks preview/export until corrected", async (text) => {
  await mount(); const count = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: text } });
  expect((screen.getByLabelText("Assortment seed") as HTMLInputElement).value).toBe(text);
  expect(screen.getByLabelText("Assortment seed").getAttribute("aria-invalid")).toBe("true");
  expect(screen.getByText("Enter a whole-number seed within the supported range.").getAttribute("role")).toBe("alert");
  expect((screen.getByRole("button", { name: "Shuffle assortment" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Export options" }) as HTMLButtonElement).disabled).toBe(true);
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(count);
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: "42" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(expect.objectContaining({ seed: 42 }), expect.any(AbortSignal)));
  expect(screen.queryByText("Enter a whole-number seed within the supported range.")).toBeNull();
});

it("stops shuffling at the safe upper bound and resumes after a direct edit", async () => {
  await mount(Number.MAX_SAFE_INTEGER - 1);
  fireEvent.click(screen.getByRole("button", { name: `Shuffle assortment (#${Number.MAX_SAFE_INTEGER - 1})` }));
  const shuffle = screen.getByRole("button", { name: `Shuffle assortment (#${Number.MAX_SAFE_INTEGER})` }) as HTMLButtonElement;
  expect(shuffle.disabled).toBe(true); fireEvent.click(shuffle);
  expect(screen.getByTestId("seed").textContent).toBe(String(Number.MAX_SAFE_INTEGER));
  expect(screen.getByLabelText("Assortment seed").getAttribute("aria-invalid")).toBe("false");
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: String(Number.MIN_SAFE_INTEGER) } });
  fireEvent.click(screen.getByRole("button", { name: `Shuffle assortment (#${Number.MIN_SAFE_INTEGER})` }));
  expect(screen.getByTestId("seed").textContent).toBe(String(Number.MIN_SAFE_INTEGER + 1));
});

it("replaces an invalid draft when resetting or restoring saved settings", async () => {
  await mount(); fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: "-" } });
  fireEvent.click(screen.getByRole("button", { name: "Restore saved seed" }));
  expect((screen.getByLabelText("Assortment seed") as HTMLInputElement).value).toBe("-7");
  fireEvent.change(screen.getByLabelText("Assortment seed"), { target: { value: "1.1" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Assortment seed") as HTMLInputElement).value).toBe("0");
  expect(screen.queryByText("Enter a whole-number seed within the supported range.")).toBeNull();
});
