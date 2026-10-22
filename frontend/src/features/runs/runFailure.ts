import type { RunListItem } from "@/shared/api/client";

/** The newest failed run of a layout, unless a later run of it completed. */
export function latestRunFailure(runs: readonly RunListItem[]): RunListItem | null {
  let failed: RunListItem | null = null;
  let completedAt = "";
  for (const run of runs) {
    if (run.status === "completed" && run.created_at > completedAt) completedAt = run.created_at;
    if (run.status === "failed" && (!failed || run.created_at > failed.created_at)) failed = run;
  }
  return failed && failed.created_at > completedAt ? failed : null;
}

/** The message part of a stored run error ("message\nTraceback …"): up to the traceback or the first blank line. */
export function runFailureMessage(error: string): string {
  const lines = error.split(/\r?\n/);
  const end = lines.findIndex((line) => line.trim() === "" || line.startsWith("Traceback (most recent call last)"));
  return (end === -1 ? lines : lines.slice(0, end)).join("\n").trim();
}
