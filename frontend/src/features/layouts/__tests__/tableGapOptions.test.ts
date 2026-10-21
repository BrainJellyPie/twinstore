import { expect, it } from "vitest";
import { applyLayoutPriority, DEFAULT_TEMPLATE_CHOICE, LAYOUT_PRIORITIES, choiceFromGeneration, templateRequest, validTemplateChoice, type TemplateChoice } from "../templateOptions";

it.each([[1, 4], [4, 1], [null, 3], [2, null], [null, null]])("preserves independent gaps %s/%s through saved options", (x, y) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, table_clearance: 2, table_clearance_x: x, table_clearance_y: y };
  expect(validTemplateChoice(choice)).toBe(true);
  expect(templateRequest(choice)).toMatchObject({ table_clearance: 2, table_clearance_x: x, table_clearance_y: y });
  expect(choiceFromGeneration(templateRequest(choice), "saved")).toMatchObject({ table_clearance_x: x, table_clearance_y: y });
});
it.each(["table_clearance_x", "table_clearance_y"] as const)("rejects malformed %s values before preview and export", (field) => {
  for (const value of [0, -1, 5, 1.5, NaN, Infinity, true, false, "2"]) {
    expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, [field]: value } as unknown as TemplateChoice)).toBe(false);
  }
});
it("defaults older saved options to inherited spacing", () => {
  expect(choiceFromGeneration({ template_id: "specialty_cafe", seed: 0, currency: "USD" }, "legacy"))
    .toMatchObject({ table_clearance: 1, table_clearance_x: null, table_clearance_y: null });
});
it.each(["wide", "capacity", "compact_cafe", "family_dining", "mixed_parties"])("restores shared spacing when applying priority %s", (id) => {
  const priority = LAYOUT_PRIORITIES.find((entry) => entry.id === id)!;
  expect(priority).toBeTruthy();
  const choice = applyLayoutPriority({ ...DEFAULT_TEMPLATE_CHOICE, width: 32, table_clearance_x: 4, table_clearance_y: 1 }, priority);
  expect(choice).toMatchObject({ width: 32, table_clearance_x: null, table_clearance_y: null });
  expect(choice.table_clearance).toBe(priority.options.table_clearance);
});
it.each(["open", "takeaway", "service_points"])("retains spacing while the %s priority turns off seating", (id) => {
  const choice = applyLayoutPriority({ ...DEFAULT_TEMPLATE_CHOICE, table_clearance_x: 4, table_clearance_y: 1 }, LAYOUT_PRIORITIES.find((entry) => entry.id === id)!);
  expect(choice).toMatchObject({ dining_tables: 0, table_clearance_x: 4, table_clearance_y: 1 });
});
