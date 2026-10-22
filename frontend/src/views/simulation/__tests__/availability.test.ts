import { expect, it } from "vitest";
import { translate } from "@/shared/i18n/translate";
import { LOCALES } from "@/shared/i18n/messages";
import type { ReadinessReason } from "@/shared/types/domain";
import { reasonLabel } from "../availability";

const REASONS: ReadinessReason[] = ["no_personas", "no_items", "no_layout", "layout_pending", "personas_pending", "no_entrance", "no_exit", "no_counter"];

it.each(LOCALES)("labels every readiness reason distinctly in $code", ({ code }) => {
  const labels = REASONS.map((reason) => reasonLabel(reason, code));
  expect(new Set(labels).size).toBe(REASONS.length);
  for (const label of labels) expect(label.trim()).not.toBe("");
  expect(reasonLabel("no_counter", code)).toBe(translate(code, "readinessNoCounter"));
});

it("keeps the English labels", () => {
  expect(reasonLabel("no_entrance", "en")).toBe("Place at least one entrance");
  expect(reasonLabel("personas_pending", "en")).toBe("Persona generation is in progress");
});
