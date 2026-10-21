import { expect, it } from "vitest";
import { DEFAULT_TEMPLATE_CHOICE, choiceFromGeneration, templateRequest, validTemplateChoice } from "../templateOptions";

it.each([0, 1, 2, 3])("keeps checkout spacing %i through request and reuse", (checkout_clearance) => {
  const choice = { ...DEFAULT_TEMPLATE_CHOICE, checkout_clearance, checkout_wall: "right" as const, checkouts: 3 };
  expect(validTemplateChoice(choice)).toBe(true);
  const request = templateRequest(choice);
  expect(request.checkout_clearance).toBe(checkout_clearance);
  expect(choiceFromGeneration(request, "saved")).toEqual({ ...choice, sourceSetupId: "saved" });
});

it.each([-1, 4, 1.5, NaN, Infinity])("rejects invalid checkout spacing %s", (checkout_clearance) => {
  expect(validTemplateChoice({ ...DEFAULT_TEMPLATE_CHOICE, checkout_clearance })).toBe(false);
});

it("keeps legacy generation settings adjacent by default", () => {
  expect(choiceFromGeneration({ template_id: "hypermarket", seed: 3, currency: "USD" }, "saved").checkout_clearance).toBe(0);
});
