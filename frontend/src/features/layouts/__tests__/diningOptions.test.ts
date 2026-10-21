import { expect, it } from "vitest";
import { DEFAULT_TEMPLATE_CHOICE, choiceFromGeneration, templateRequest, validTemplateChoice, type TemplateChoice } from "../templateOptions";

it.each([2, 4, 6] as const)("retains %s seats across requests and saved options", (dining_seats) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, dining_seats, dining_tables: 3 };
  expect(validTemplateChoice(choice)).toBe(true);
  const request = templateRequest(choice);
  expect(request.dining_seats).toBe(dining_seats);
  expect(choiceFromGeneration(request, "saved").dining_seats).toBe(dining_seats);
});

it.each([null, 0, 1, 3, 5, 7, 2.5, NaN, Infinity, true, "2"])("blocks malformed table size %s before preview or export", (value) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, dining_seats: value } as unknown as TemplateChoice;
  expect(validTemplateChoice(choice)).toBe(false);
});

it("reuses older options with four seats as the default", () => {
  expect(choiceFromGeneration({ template_id: "specialty_cafe", seed: 0, currency: "USD" }, "legacy").dining_seats).toBe(4);
  expect(choiceFromGeneration({ template_id: "specialty_cafe", seed: 0, currency: "USD" }, "legacy").table_rotation).toBe(0);
});

it.each([0, 90] as const)("retains table rotation %s through requests and reuse", (table_rotation) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, table_rotation };
  expect(validTemplateChoice(choice)).toBe(true);
  expect(choiceFromGeneration(templateRequest(choice), "saved").table_rotation).toBe(table_rotation);
});

it.each([null, -90, 1, 45, 180, 270, 90.5, NaN, Infinity, false, "90"])("blocks malformed table rotation %s", (value) => {
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, table_rotation: value } as unknown as TemplateChoice)).toBe(false);
});
