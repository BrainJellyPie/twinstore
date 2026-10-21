// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { TemplateChoice } from "@/features/layouts/templateOptions";
import type { StoreTemplate } from "@/shared/api/client";
import { CreateStoreWizard } from "../components/CreateStoreWizard";

const { create } = vi.hoisted(() => ({ create: vi.fn() }));
vi.mock("@/shared/mutations/useCreateStore", () => ({ useCreateStore: () => ({ mutateAsync: create, isPending: false, error: null }) }));
vi.mock("@/features/layouts/components/TemplatePicker", () => ({
  TemplatePicker: ({ value, onChange, onTemplateSelected }: { value: TemplateChoice; onChange: (v: TemplateChoice) => void; onTemplateSelected?: (t: StoreTemplate) => void }) =>
    <div><button type="button" onClick={() => {
      onChange({ ...value, templateId: "community_pharmacy", width: 24, design_theme: "minimal" });
      onTemplateSelected?.({ id: "community_pharmacy", name: "Community pharmacy", description: "Care", store_type: "pharmacy", grid: [14, 12], racks: 20, skus: 30, open_hours: [9, 21], default_style: "aisles", default_design: "minimal", default_dining_tables: 0 });
    }}>Choose pharmacy</button><button type="button" onClick={() => onChange({ ...value, width: 99 })}>Invalid size</button></div>,
}));
beforeEach(() => { create.mockResolvedValue({ metadata: { project_id: "proj_new" }, setup: { id: "setup_new" }, personaGenId: "gen_new" }); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function fillStore() {
  fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "My Pharmacy" } });
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "12 Market Street" } });
}

async function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"), { target: { value: "Local residents" } });
  fireEvent.click(screen.getByRole("button", { name: "Create new store" }));
  fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
}

it("creates the selected initial format with the wizard metadata", async () => {
  const created = vi.fn();
  render(<CreateStoreWizard onCreated={created} />);
  fillStore();
  fireEvent.click(screen.getByRole("button", { name: "Choose pharmacy" }));
  await submit();
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ meta: expect.objectContaining({
    name: "My Pharmacy", store_type: "pharmacy", layout: expect.objectContaining({ template_id: "community_pharmacy", width: 24, design_theme: "minimal" }),
  }) })));
  await waitFor(() => expect(created).toHaveBeenCalledWith("proj_new"));
});

it("preserves the empty-layout starting option", async () => {
  render(<CreateStoreWizard />);
  fillStore();
  fireEvent.click(screen.getByRole("checkbox", { name: "Start with a furnished store template" }));
  await submit();
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ meta: expect.objectContaining({ layout: null }) })));
});

it("does not advance with invalid template dimensions", () => {
  render(<CreateStoreWizard />);
  fillStore();
  fireEvent.click(screen.getByRole("button", { name: "Invalid size" }));
  expect((screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled).toBe(true);
  expect(create).not.toHaveBeenCalled();
});
