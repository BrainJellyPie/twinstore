// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { PilotSensitivityReport } from "@/shared/api/fieldSensitivity";
import { PilotSensitivity } from "../PilotSensitivity";

let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => {
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }

function report(): PilotSensitivityReport {
  return { method: "fixed-block-deletion-v1", pilot_id: "pilot_test", revision: 2, finalized_at: "closed", target_sku: "tea",
    planned_encounters: 40, blocks: 3, difference: 0.1,
    groups: [{ scope: "staff", staff_id: "s1", shift_id: "", removed_blocks: 2, removed_encounters: 30, removed_weight: 0.75,
      remaining_encounters: 10, difference: -0.2, change: -0.3, opposite_sign: true },
    { scope: "staff", staff_id: "s2", shift_id: "", removed_blocks: 1, removed_encounters: 10, removed_weight: 0.25,
      remaining_encounters: 30, difference: 0.2, change: 0.1, opposite_sign: false }],
    summaries: [{ scope: "staff", groups: 2, estimable: 2, minimum: -0.2, maximum: 0.2, max_absolute_change: 0.3, opposite_sign_count: 1 }],
    notes: ["Offline test fixture. Stable signs do not establish causality."] };
}
const props = { projectId: "project_test", pilotId: "pilot_test", revision: 2, eligible: true };

it("does not query while collecting or below target, or before an eligible user requests checks", async () => {
  const view = render(<PilotSensitivity {...props} eligible={false} />, { wrapper });
  expect(screen.getByText(/Do not close early/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Show sensitivity checks" })).toBeNull();
  expect(fetchMock).not.toHaveBeenCalled();
  view.rerender(<PilotSensitivity {...props} />);
  expect(screen.getByRole("button", { name: "Show sensitivity checks" })).toBeTruthy();
  expect(fetchMock).not.toHaveBeenCalled();
});

it("loads the saved revision, displays changes as percentage points and exports all scopes", async () => {
  fetchMock.mockResolvedValue(new Response(JSON.stringify(report())));
  render(<PilotSensitivity {...props} />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Show sensitivity checks" }));
  expect(await screen.findByText(/Locked revision 2/)).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/project_test/staff-pilots/pilot_test/sensitivity?revision=2"), { signal: expect.any(AbortSignal) });
  expect(screen.getByText("+10.00 pp", { selector: "b" })).toBeTruthy();
  expect(screen.getByText("-20.00 pp")).toBeTruthy();
  expect(screen.getByText(/1 of 2 estimable deletions have an opposite sign/)).toBeTruthy();
  const link = screen.getByRole("link", { name: "Export all sensitivity checks CSV" });
  expect(link.getAttribute("href")).toContain("/pilot_test/sensitivity.csv?revision=2");
  expect(screen.getByText(/not confidence intervals/)).toBeTruthy();
  expect(screen.getByText(/Stable signs do not establish causality/)).toBeTruthy();
});

it("represents a sole group as unavailable and an exact zero estimate as zero", async () => {
  const data = report(); data.difference = 0;
  data.groups = data.groups.slice(0, 1).map((group) => ({ ...group, remaining_encounters: 0, difference: null, change: null, opposite_sign: null }));
  data.summaries = data.summaries.map((summary) => ({ ...summary, groups: 1, estimable: 0, minimum: null, maximum: null, max_absolute_change: null, opposite_sign_count: 0 }));
  fetchMock.mockResolvedValue(new Response(JSON.stringify(data)));
  render(<PilotSensitivity {...props} />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Show sensitivity checks" }));
  expect(await screen.findByText("0.00 pp")).toBeTruthy();
  expect(screen.getAllByText("Not estimable")).toHaveLength(3);
  expect(screen.getByText(/comparisons unavailable after deletion: 1/)).toBeTruthy();
});

it("disables reload while pending and shows server failures without a stale report or export", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<PilotSensitivity {...props} />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Show sensitivity checks" }));
  await screen.findByText(/Locked revision 2/);
  let finish!: (response: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  fireEvent.click(screen.getByRole("button", { name: "Reload sensitivity checks" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Reload sensitivity checks" }) as HTMLButtonElement).disabled).toBe(true));
  finish(new Response(JSON.stringify({ detail: "The saved pilot changed. Reload the pilot" }), { status: 409 }));
  expect((await screen.findByRole("alert")).textContent).toContain("saved pilot changed");
  expect(screen.queryByRole("link", { name: "Export all sensitivity checks CSV" })).toBeNull();
  expect(screen.queryByText(/Locked revision 2/)).toBeNull();
});

it("keys requests by pilot and revision instead of reusing the prior result", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  const view = render(<PilotSensitivity {...props} />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Show sensitivity checks" }));
  await screen.findByText(/Locked revision 2/);
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ ...report(), pilot_id: "pilot_other", revision: 3 })));
  view.rerender(<PilotSensitivity {...props} pilotId="pilot_other" revision={3} />);
  await screen.findByText(/Locked revision 3/);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(screen.queryByText(/Locked revision 2/)).toBeNull();
  expect(screen.getByRole("link", { name: "Export all sensitivity checks CSV" }).getAttribute("href")).toContain("pilot_other/sensitivity.csv?revision=3");
});
