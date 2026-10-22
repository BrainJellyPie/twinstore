// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { RunListItem } from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { useRuns } from "@/shared/queries/useRuns";
import { LastRunFailure } from "../LastRunFailure";

vi.mock("@/shared/queries/useRuns", () => ({ useRuns: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); useLocale.getState().setLocale("en"); });

const run = (setup_id: string, run_id: string, status: string, created_at: string, error = ""): RunListItem =>
  ({ run_id, project_id: "p", setup_id, status, created_at, total_customers: 1, error });
const traceback = "\nTraceback (most recent call last):\n  File \"engine.py\", line 1\nRuntimeError: boom";
// Runs as the backend lists them per layout: layout A's latest run failed, layout B's last run completed.
const runsBySetup: Record<string, RunListItem[]> = {
  A: [run("A", "a2", "failed", "2026-10-22T10:00:00", `LLM provider rejected the key${traceback}`), run("A", "a1", "completed", "2026-10-21T10:00:00")],
  B: [run("B", "b2", "completed", "2026-10-22T11:00:00"), run("B", "b1", "failed", "2026-10-20T10:00:00", "Old failure")],
};
function mockRuns(runs = runsBySetup) {
  vi.mocked(useRuns).mockImplementation((_pid, sid) => ({ data: runs[sid] ?? [] }) as unknown as ReturnType<typeof useRuns>);
}

it.each(LOCALES)("shows a stored failure for its own layout only, without the traceback, in $code", ({ code }) => {
  useLocale.getState().setLocale(code); mockRuns();
  const { rerender } = render(<LastRunFailure projectId="p" setupId="A" />);
  expect(screen.getByText(translate(code, "lastRunFailed", { message: "LLM provider rejected the key" }))).toBeTruthy();
  expect(document.body.textContent).not.toContain("Traceback");
  rerender(<LastRunFailure projectId="p" setupId="B" />);
  expect(document.body.textContent).toBe("");
  expect(useRuns).toHaveBeenLastCalledWith("p", "B");
});

it("shows a multi-line message in full behind an expand toggle when it is long", () => {
  const message = ["Simulation input is invalid:", ...Array.from({ length: 5 }, (_, i) => `  rack_${i}: price must be at least 0`)].join("\n");
  mockRuns({ A: [run("A", "a1", "failed", "2026-10-22T10:00:00", `${message}${traceback}`)] });
  render(<LastRunFailure projectId="p" setupId="A" />);
  const text = screen.getByText((_, el) => el?.tagName === "P" && el.textContent === translate("en", "lastRunFailed", { message }));
  expect(text.className).toContain("line-clamp-3");
  const toggle = screen.getByRole("button", { name: "Show full message" });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(toggle);
  expect(text.className).not.toContain("line-clamp-3");
  expect(screen.getByRole("button", { name: "Show less" }).getAttribute("aria-expanded")).toBe("true");
});

it("keeps short messages unclamped and explains a failure without details", () => {
  mockRuns({ A: [run("A", "a1", "failed", "2026-10-22T10:00:00", "Out of memory")], B: [run("B", "b1", "failed", "2026-10-22T10:00:00", traceback)] });
  const { rerender } = render(<LastRunFailure projectId="p" setupId="A" />);
  expect(screen.getByText("Last run failed: Out of memory").className).not.toContain("line-clamp");
  expect(screen.queryByRole("button")).toBeNull();
  rerender(<LastRunFailure projectId="p" setupId="B" />);
  expect(screen.getByText("Last run failed.")).toBeTruthy();
});
