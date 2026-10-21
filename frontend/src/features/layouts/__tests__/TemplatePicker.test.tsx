// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE } from "../templateOptions";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));

function Picker() {
  const [value, onChange] = useState(DEFAULT_TEMPLATE_CHOICE);
  return <TemplatePicker value={value} onChange={onChange} />;
}

beforeEach(() => {
  vi.mocked(api.getStoreTemplates).mockResolvedValue([
    { id: "urban_cvs", name: "City store", description: "Daily groceries", store_type: "convenience", grid: [12, 10], racks: 10, skus: 40, open_hours: [0, 24], default_style: "aisles", default_design: "classic", default_dining_tables: 0 },
    { id: "community_pharmacy", name: "Community pharmacy", description: "First aid and wellness", store_type: "pharmacy", grid: [14, 12], racks: 12, skus: 50, open_hours: [9, 21], default_style: "spine", default_design: "minimal", default_dining_tables: 0 },
  ]);
  vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Preview", type: "convenience", grid_size: [12, 10], weekly_schedule: [], racks: [] });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Picker /></QueryClientProvider>);
}

it("filters formats and sends selected requirements to the preview", async () => {
  mount();
  await screen.findByRole("button", { name: /Community pharmacy/ });
  fireEvent.change(screen.getByLabelText("Find a store format"), { target: { value: "pharmacy" } });
  expect(screen.queryByRole("button", { name: /City store/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Community pharmacy/ }));
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "showroom" } });
  fireEvent.change(screen.getByLabelText("Checkout counters"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "28" } });
  await waitFor(() => expect(api.previewStoreTemplate).toHaveBeenLastCalledWith(
    expect.objectContaining({ template_id: "community_pharmacy", style: "showroom", checkouts: 3, width: 28 }), expect.any(AbortSignal),
  ));
});

it("does not request an invalid size and resets options without losing the brief", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  const calls = vi.mocked(api.previewStoreTemplate).mock.calls.length;
  fireEvent.change(screen.getByLabelText("Width (8–40 cells)"), { target: { value: "99" } });
  expect(screen.getByRole("status").textContent).toContain("valid grid size");
  expect(api.previewStoreTemplate).toHaveBeenCalledTimes(calls);
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "Quiet corner" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset layout options" }));
  expect((screen.getByLabelText("Additional design brief") as HTMLTextAreaElement).value).toBe("Quiet corner");
  await screen.findByRole("img", { name: "Floor plan preview" });
});

it("shows preview errors instead of a stale successful plan", async () => {
  mount();
  await screen.findByRole("img", { name: "Floor plan preview" });
  vi.mocked(api.previewStoreTemplate).mockRejectedValue(new Error("Preview failed"));
  fireEvent.change(screen.getByLabelText("Layout pattern"), { target: { value: "spine" } });
  await screen.findByRole("alert");
  expect(screen.queryByRole("img", { name: "Floor plan preview" })).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("Preview failed");
});
