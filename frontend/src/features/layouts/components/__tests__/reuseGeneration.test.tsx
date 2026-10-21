// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AddLayoutDialog } from "../AddLayoutDialog";
import type { Layout } from "../../hooks/useLayouts";
import type { TemplateChoice } from "../../templateOptions";

const mutation = vi.hoisted(() => ({ isPending: false, isError: false, error: null, reset: vi.fn(), mutate: vi.fn() }));
vi.mock("../../hooks/useCreateLayout", () => ({ useCreateLayout: () => mutation }));
vi.mock("../TemplatePicker", () => ({ TemplatePicker: ({ value, onChange }: { value: TemplateChoice; onChange: (v: TemplateChoice) => void }) => <div>
  <span data-testid="settings">{JSON.stringify(value)}</span>
  <button type="button" onClick={() => onChange({ ...value, dining_tables: 5 })}>Use five tables</button>
</div> }));
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn(); });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

const source: Layout = { id: "setup_cafe", name: "Garden café", parentId: null, status: "locked", createdAt: "2026-10-21",
  generation: { template_id: "book_cafe", source_setup_id: "older_parent", name: "Previous name", seed: 12, currency: "JPY",
    width: 24, height: 18, style: "free_flow", shelf_direction: "vertical", aisle_width: 4, max_shelf_run: 8, dining_tables: 3, table_clearance: 2, seating_zone: "right", checkout_placement: "near_entrance", exit_position: "right",
    design_theme: "botanical", requirements: "Quiet reading corner",
    reserved_areas: [{ label: "Reading nook", x: 3, y: 3, width: 2, height: 4 }] } };

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
}

it("restores a saved brief and options, then submits a linked alternative with the user's changes", () => {
  render(<AddLayoutDialog open onOpenChange={vi.fn()} projectId="p" parentSetupId={source.id} layouts={[source]} defaultCurrency="JPY" />, { wrapper });
  fireEvent.click(screen.getByLabelText("Generate a store from a template"));
  fireEvent.click(screen.getByRole("button", { name: "Reuse options from Garden café" }));
  expect(JSON.parse(screen.getByTestId("settings").textContent!)).toMatchObject({
    sourceSetupId: source.id, templateId: "book_cafe", width: 24, height: 18, seed: 12, currency: "JPY",
    requirements: "Quiet reading corner", design_theme: "botanical", dining_tables: 3, seating_zone: "right", checkout_placement: "near_entrance",
    reserved_areas: source.generation!.reserved_areas, shelf_direction: "vertical", aisle_width: 4, max_shelf_run: 8, table_clearance: 2, exit_position: "right",
  });
  fireEvent.click(screen.getByRole("button", { name: "Use five tables" }));
  fireEvent.change(screen.getByLabelText("Layout name"), { target: { value: "More café seating" } });
  fireEvent.click(screen.getByRole("button", { name: "Add layout" }));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({
    name: "More café seating", source: expect.objectContaining({ kind: "template", sourceSetupId: source.id,
      dining_tables: 5, seating_zone: "right", checkout_placement: "near_entrance", requirements: "Quiet reading corner", currency: "JPY",
      reserved_areas: source.generation!.reserved_areas, shelf_direction: "vertical", aisle_width: 4, max_shelf_run: 8, table_clearance: 2, exit_position: "right" }),
  }), expect.any(Object));
});

it("clears an old source link when the dialog is reopened", () => {
  const props = { onOpenChange: vi.fn(), projectId: "p", parentSetupId: source.id, layouts: [source] };
  const view = render(<AddLayoutDialog {...props} open />, { wrapper });
  fireEvent.click(screen.getByLabelText("Generate a store from a template"));
  fireEvent.click(screen.getByRole("button", { name: "Reuse options from Garden café" }));
  view.rerender(<AddLayoutDialog {...props} open={false} />);
  view.rerender(<AddLayoutDialog {...props} open />);
  fireEvent.click(screen.getByLabelText("Generate a store from a template"));
  expect(JSON.parse(screen.getByTestId("settings").textContent!)).not.toHaveProperty("sourceSetupId");
});

it("submits a separate building whose floors retain their individual source links", () => {
  const ground: Layout = { ...source, id: "ground", name: "Garden shop", generation: { template_id: "florist", seed: 0, currency: "JPY" },
    building: { id: "building", name: "Garden house", level: 1, label: "Shop", floor_count: 2 } };
  const upper: Layout = { ...source, building: { ...ground.building!, level: 2, label: "Café" } };
  render(<AddLayoutDialog open onOpenChange={vi.fn()} projectId="p" parentSetupId={upper.id} layouts={[ground, upper]} defaultCurrency="JPY" />, { wrapper });
  fireEvent.click(screen.getByLabelText("Multi-floor store"));
  fireEvent.click(screen.getByRole("button", { name: "Reuse building options from Garden house" }));
  expect((screen.getByLabelText("Building name") as HTMLInputElement).value).toBe("Garden house alternative");
  fireEvent.click(screen.getByRole("button", { name: /2F · Café/ }));
  fireEvent.click(screen.getByRole("button", { name: "Use five tables" }));
  fireEvent.click(screen.getByRole("button", { name: "Move to lower level" }));
  fireEvent.click(screen.getByTestId("add-layout-submit"));
  expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({ name: "Garden house alternative",
    source: { kind: "building", floors: [
      { label: "Café", choice: expect.objectContaining({ sourceSetupId: upper.id, dining_tables: 5, requirements: "Quiet reading corner" }) },
      { label: "Shop", choice: expect.objectContaining({ sourceSetupId: ground.id, templateId: "florist" }) },
    ] },
  }), expect.any(Object));
});
