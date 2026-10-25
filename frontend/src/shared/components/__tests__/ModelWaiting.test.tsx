// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { useLocale } from "@/shared/i18n/i18n";
import { ModelWaiting } from "../ModelWaiting";

beforeEach(() => { useLocale.getState().setLocale("en"); vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

it("says what is happening, and after a while that a small model can take minutes", () => {
  render(<ModelWaiting label="Redesigning…" />);
  expect(screen.getByText("Redesigning…")).toBeTruthy();
  expect(screen.queryByText(/can take a few minutes/)).toBeNull();
  act(() => { vi.advanceTimersByTime(16_000); });
  expect(screen.getByText(/A small local model can take a few minutes/)).toBeTruthy();
  expect(screen.getByText("(16 s)").getAttribute("aria-hidden")).toBe("true");
});
