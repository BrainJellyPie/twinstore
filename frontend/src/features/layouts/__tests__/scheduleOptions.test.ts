import { expect, it } from "vitest";
import { DEFAULT_TEMPLATE_CHOICE, choiceFromGeneration, templateRequest, validTemplateChoice, type TemplateChoice } from "../templateOptions";

it.each([
  { open_hour: 0, close_hour: 24, closed_days: [] },
  { open_hour: 23, close_hour: 24, closed_days: [1, 2, 3, 4, 5, 6] },
  { open_hour: null, close_hour: null, closed_days: null },
  { open_hour: 6, close_hour: 15, closed_days: [6, 7] },
])("keeps valid schedule overrides through save and reuse: %o", (schedule) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, ...schedule };
  expect(validTemplateChoice(choice)).toBe(true);
  const request = templateRequest(choice);
  expect(request).toMatchObject(schedule);
  expect(choiceFromGeneration(request, "saved")).toMatchObject({ ...schedule, sourceSetupId: "saved" });
});

it.each<Partial<TemplateChoice>>([
  { open_hour: -1 }, { open_hour: 24 }, { open_hour: 0.5 }, { open_hour: NaN },
  { close_hour: 0 }, { close_hour: 25 }, { close_hour: 12.5 }, { close_hour: Infinity },
  { open_hour: 12, close_hour: 12 }, { open_hour: 23, close_hour: 6 },
  { closed_days: [0] }, { closed_days: [8] }, { closed_days: [1.5] }, { closed_days: [1, 1] },
  { closed_days: [1, 2, 3, 4, 5, 6, 7] },
])("blocks an invalid schedule before preview/export: %o", (schedule) => {
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, ...schedule })).toBe(false);
});

it("restores defaults when reusing files created before schedule options existed", () => {
  const choice = choiceFromGeneration({ template_id: "office_lobby", seed: 0, currency: "USD" }, "legacy");
  expect(choice).toMatchObject({ open_hour: null, close_hour: null, closed_days: null });
  expect(validTemplateChoice(choice)).toBe(true);
});
