// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import type { GenerationConfirm } from "@/shared/types/domain";
import { GenerationConfirmDialog } from "../GenerationConfirmDialog";

const confirm: GenerationConfirm = {
  model: "vendor/<Tea> 🛒 {count}", local: false, days: 1, visitors_per_day: { "1": 1 },
  all: { per_day: 1, customers: 1, requests: 1, minutes: 1, cost_usd: null },
  sample: { per_day: 1, customers: 1, requests: 1, minutes: 1, cost_usd: 0.004 },
};
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

it.each(LOCALES)("explains a single visitor and sample copies naturally in $code while preserving the submitted choice", ({ code }) => {
  useLocale.getState().setLocale(code);
  const onAnswer = vi.fn();
  render(<GenerationConfirmDialog confirm={confirm} answering={false} error={null} onAnswer={onAnswer} />);
  const dialog = within(screen.getByRole("alertdialog", { name: translate(code, "genConfirmTitle") }));
  const visitors = translate(code, "visitorADay", { count: 1 });
  expect(dialog.getByText(translate(code, "genConfirmEstimate", { visitors, days: 1 }), { exact: false })).toBeTruthy();
  expect(dialog.getByText(translate(code, "genSampleHint", { count: 1 }), { exact: false })).toBeTruthy();
  expect(dialog.getAllByText(translate(code, "modelCalls", { calls: 1 }), { exact: false })).toHaveLength(2);
  expect(screen.getByRole("alertdialog").textContent).toContain(confirm.model);
  expect(document.querySelector("tea")).toBeNull();
  const sample = dialog.getByText(translate(code, "genWriteSample", { count: 1 })).closest("button")!;
  fireEvent.click(sample);
  expect(onAnswer).toHaveBeenCalledExactlyOnceWith("sample");
  fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" });
  expect(screen.getByRole("alertdialog")).toBeTruthy();
  expect(onAnswer).toHaveBeenCalledOnce();
});

it.each(LOCALES)("keeps a pending generation choice blocked through language changes and preserves diagnostics in $code", ({ code }) => {
  useLocale.getState().setLocale(code);
  const onAnswer = vi.fn();
  const failure = "Original server detail <raw> 原文 {count}";
  const view = render(<GenerationConfirmDialog confirm={confirm} answering error={null} onAnswer={onAnswer} />);
  const next = code === "fr" ? "ko" : "fr";
  act(() => useLocale.getState().setLocale(next));
  for (const button of screen.getAllByRole("button")) {
    expect(button.matches(":disabled")).toBe(true); fireEvent.click(button);
  }
  expect(onAnswer).not.toHaveBeenCalled();
  view.rerender(<GenerationConfirmDialog confirm={confirm} answering={false} error={failure} onAnswer={onAnswer} />);
  expect(screen.getByRole("alert").textContent).toContain(translate(next, "genConfirmFailed"));
  expect(screen.getByRole("alert").textContent).toContain(failure);
  fireEvent.click(screen.getByRole("button", { name: translate(next, "cancel") }));
  expect(onAnswer).toHaveBeenCalledExactlyOnceWith("cancel");
});


it.each(LOCALES)("handles zero, a large count and unavailable daily counts without changing model costs in $code", ({ code }) => {
  useLocale.getState().setLocale(code);
  const view = render(<GenerationConfirmDialog confirm={{ ...confirm, visitors_per_day: { "1": 0 }, all: { ...confirm.all, customers: 0 }, sample: { ...confirm.sample, customers: 0 } }} answering={false} error={null} onAnswer={vi.fn()} />);
  expect(screen.getByRole("alertdialog").textContent).toContain(translate(code, code === "fr" ? "visitorADay" : "visitorsADay", { count: 0 }));
  expect(screen.getByRole("alertdialog").textContent).toContain(translate(code, "costUnknown"));
  expect(screen.getByRole("alertdialog").textContent).toContain(translate(code, "costUnderCent"));
  view.rerender(<GenerationConfirmDialog confirm={{ ...confirm, visitors_per_day: { "1": 1000000 }, all: { ...confirm.all, customers: 1000000 } }} answering={false} error={null} onAnswer={vi.fn()} />);
  expect(screen.getByRole("alertdialog").textContent).toContain(translate(code, "visitorsADay", { count: 1000000 }));
  expect(screen.getByText(translate(code, "genWriteAll", { count: 1000000 }), { normalizer: (text) => text })).toBeTruthy();
  const unavailableCounts: Record<string, number>[] = [{}, { "1": NaN, "2": Infinity }];
  for (const counts of unavailableCounts) {
    view.rerender(<GenerationConfirmDialog confirm={{ ...confirm, visitors_per_day: counts }} answering={false} error={null} onAnswer={vi.fn()} />);
    expect(screen.getByRole("alertdialog").textContent).toContain(translate(code, "visitorADay", { count: 1 }));
    expect(screen.getByRole("alertdialog").textContent).not.toMatch(/NaN|Infinity/);
  }
});
