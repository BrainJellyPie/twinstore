import { expect, it } from "vitest";

import type { RunListItem } from "@/shared/api/client";
import { latestRunFailure, runFailureMessage } from "../runFailure";

const run = (run_id: string, status: string, created_at: string, error = ""): RunListItem =>
  ({ run_id, project_id: "p", setup_id: "s", status, created_at, total_customers: 1, error });

it("returns the newest failure only when no later run completed", () => {
  const old = run("old", "failed", "2026-10-20T10:00:00", "old error");
  const done = run("done", "completed", "2026-10-21T10:00:00");
  const recent = run("recent", "failed", "2026-10-22T10:00:00", "new error");
  expect(latestRunFailure([done, old, recent])?.run_id).toBe("recent");
  expect(latestRunFailure([old, done])).toBeNull();
  expect(latestRunFailure([old])?.run_id).toBe("old");
  expect(latestRunFailure([done, run("live", "running", "2026-10-23T10:00:00")])).toBeNull();
  expect(latestRunFailure([])).toBeNull();
});

it.each([
  ["Model refused\nTraceback (most recent call last):\n  File \"x.py\"\nValueError: bad", "Model refused"],
  ["3 validation errors\n  price: must be >= 0\n  name: required\nTraceback (most recent call last):\n  ...", "3 validation errors\n  price: must be >= 0\n  name: required"],
  ["Rate limited\r\n\r\nRetry later\nTraceback (most recent call last):", "Rate limited"],
  ["Plain message", "Plain message"],
  ["\nTraceback (most recent call last):\nKeyError: 'x'", ""],
  ["", ""],
])("keeps the whole message part of %j", (error, expected) => {
  expect(runFailureMessage(error)).toBe(expected);
});
