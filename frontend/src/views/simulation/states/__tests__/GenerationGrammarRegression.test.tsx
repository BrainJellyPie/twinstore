// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useLocale } from "@/shared/i18n/i18n";
import type { GenerationConfirm } from "@/shared/types/domain";
import { GenerationConfirmDialog } from "../GenerationConfirmDialog";
const confirm: GenerationConfirm = {
  model: "synthetic/test-model", local: false, days: 1, visitors_per_day: { "1": 1 },
  all: { per_day: 1, customers: 1, requests: 1, minutes: 1, cost_usd: null },
  sample: { per_day: 1, customers: 1, requests: 1, minutes: 1, cost_usd: null },
};
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });
it.each([
  ["en", 1, "about 1 visitor a day"],
  ["es", 1, "aproximadamente 1 visitante al día"],
  ["fr", 1, "environ 1 visiteur par jour"],
  ["fr", 0, "environ 0 visiteur par jour"],
] as const)("uses the appropriate visitor noun for %s at count %s", (locale, count, expected) => {
  useLocale.getState().setLocale(locale);
  render(<GenerationConfirmDialog confirm={{ ...confirm, visitors_per_day: { "1": count } }} answering={false} error={null} onAnswer={vi.fn()} />);
  expect(screen.getByRole("alertdialog").textContent).toContain(expected);
});
