// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { getPilot, getPilotCollection, listPilots, type CollectionCounts, type PilotCollectionReport } from "@/shared/api/fieldPilot";
import { FieldPilots } from "../FieldPilots";
import { PilotCollectionChecks } from "../PilotCollectionChecks";

vi.mock("@/shared/api/fieldPilot", async (original) => ({ ...await original<typeof import("@/shared/api/fieldPilot")>(), getPilot: vi.fn(), getPilotCollection: vi.fn(), listPilots: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
let qc: QueryClient;
beforeEach(() => { qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }

function report(): PilotCollectionReport {
  const empty: CollectionCounts = { planned: 10, enrolled: 0, unused: 0, unrecorded: 10, complete_enrolled: 0,
    missing_purchase: 0, missing_delivery: 0, known_delivery: 0, not_delivered: 0, purchase_missing_rate: null, non_delivery_rate: null };
  const a: CollectionCounts = { ...empty, enrolled: 1, unrecorded: 9, missing_purchase: 1, known_delivery: 1, purchase_missing_rate: 1, non_delivery_rate: 0 };
  const b: CollectionCounts = { ...empty, enrolled: 1, unrecorded: 9, missing_delivery: 1, purchase_missing_rate: 0 };
  return { pilot_id: "pilot_test", name: "Collection fixture", revision: 4, updated_at: "2026-10-21T10:00:00Z", finalized_at: "", outcome_window: "Same store visit",
    counts: { ...empty, planned: 40, enrolled: 2, unrecorded: 38, missing_purchase: 1, missing_delivery: 1, known_delivery: 1, purchase_missing_rate: 0.5, non_delivery_rate: 0 },
    recording_gaps: 0, unused_before_enrolled: 0, unrecorded_tail: 38, can_finalize: false, target_completed: false,
    blocks: [{ staff_id: "s1", shift_id: "am", counts: { ...a, planned: 20, unrecorded: 19 }, a, b: empty,
      last_recorded_sequence: 1, recording_gaps: 0, unused_before_enrolled: 0, unrecorded_tail: 19, purchase_missing_gap: null },
    { staff_id: "s2", shift_id: "pm", counts: { ...b, planned: 20, unrecorded: 19 }, a: empty, b,
      last_recorded_sequence: 1, recording_gaps: 0, unused_before_enrolled: 0, unrecorded_tail: 19, purchase_missing_gap: null }],
    tasks: [{ assignment_id: "slot1", staff_id: "s1", shift_id: "am", sequence: 1, arm: "A", issues: ["purchase_unknown"] },
      { assignment_id: "slot2", staff_id: "s2", shift_id: "pm", sequence: 1, arm: "B", issues: ["delivery_unknown"] }],
    guidance: [{ issue: "purchase_unknown", title: "Purchase outcome unknown", action: "Verify after the saved window; do not guess." },
      { issue: "delivery_unknown", title: "Script delivery unknown", action: "Check whether the assigned script was delivered." }], notes: ["Offline fixture only."] };
}

it("opens collection checks without requesting purchase results until explicitly selected", async () => {
  vi.mocked(listPilots).mockResolvedValue([{ pilot_id: "pilot_test", pitch_id: "pit_test", name: "Collection fixture", created_at: "now", finalized_at: "", planned: 40, enrolled: 2 }]);
  vi.mocked(getPilotCollection).mockResolvedValue(report());
  vi.mocked(getPilot).mockRejectedValue(new Error("Results endpoint requested"));
  render(<FieldPilots projectId="p" />, { wrapper });
  fireEvent.click(await screen.findByRole("button", { name: /Collection fixture/ }));
  expect(await screen.findByText("Collection fixture · collection checks")).toBeTruthy();
  expect(getPilot).not.toHaveBeenCalled();
  expect(screen.queryByText("Known-outcome rate")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Observations and results" }));
  await waitFor(() => expect(getPilot).toHaveBeenCalledWith("p", "pilot_test", expect.any(AbortSignal)));
  expect((await screen.findByRole("alert")).textContent).toContain("Results endpoint requested");
});

it("filters staff/shifts and issue types while retaining an export of all checks", async () => {
  vi.mocked(getPilotCollection).mockResolvedValue(report());
  render(<PilotCollectionChecks projectId="p" pilotId="pilot_test" />, { wrapper });
  await screen.findByText("Assignments 1–2 of 2");
  expect(screen.getByText("Verify after the saved window; do not guess.", { exact: false })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Staff / shift filter"), { target: { value: "s2:pm" } });
  expect(screen.getByText("Assignments 1–1 of 1")).toBeTruthy();
  expect(screen.queryByText("Verify after the saved window; do not guess.", { exact: false })).toBeNull();
  fireEvent.change(screen.getByLabelText("Check type"), { target: { value: "purchase_unknown" } });
  expect(screen.getByText(/No follow-up checks match/)).toBeTruthy();
  const href = screen.getByRole("link", { name: "Download all follow-up checks CSV" }).getAttribute("href");
  expect(href).toContain("pilot_test/follow-up.csv");
  expect(href).not.toContain("s2");
});

it("paginates the full checklist and resets the page when filters change", async () => {
  const data = report();
  data.tasks = Array.from({ length: 51 }, (_, i) => ({
    assignment_id: `slot${i}`, staff_id: "s1", shift_id: "am",
    sequence: i + 1, arm: "A", issues: ["purchase_unknown"],
  }));
  vi.mocked(getPilotCollection).mockResolvedValue(data);
  render(<PilotCollectionChecks projectId="p" pilotId="pilot_test" />, { wrapper });
  await screen.findByText("Assignments 1–50 of 51");
  fireEvent.click(screen.getByRole("button", { name: "Next checks" }));
  expect(screen.getByText("Assignments 51–51 of 51")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Check type"), { target: { value: "purchase_unknown" } });
  expect(screen.getByText("Assignments 1–50 of 51")).toBeTruthy();
});

it("distinguishes an untouched tail from a completed plan and preserves unknown rate denominators", async () => {
  const data = report(); data.tasks = [];
  vi.mocked(getPilotCollection).mockResolvedValue(data);
  render(<PilotCollectionChecks projectId="p" pilotId="pilot_test" />, { wrapper });
  await screen.findByText(/No follow-up checks match/);
  expect(screen.getByText(/Some slot statuses or enrolled outcomes still need recording/)).toBeTruthy();
  expect(screen.getByText(/Tail slots may be future assignments/)).toBeTruthy();
  expect(screen.getAllByText("0/0 (Unknown)").length).toBeGreaterThan(0);
  expect(screen.queryByText(/All planned encounters have complete records/)).toBeNull();
});

it("reloads a corrected revision and makes the closed state explicit", async () => {
  const closed = report(); closed.revision = 5; closed.finalized_at = "closed"; closed.tasks = [];
  vi.mocked(getPilotCollection).mockResolvedValueOnce(report()).mockResolvedValueOnce(closed);
  render(<PilotCollectionChecks projectId="p" pilotId="pilot_test" />, { wrapper });
  await screen.findByText(/Saved revision 4/);
  fireEvent.click(screen.getByRole("button", { name: "Reload collection checks" }));
  expect(await screen.findByText(/Saved revision 5/)).toBeTruthy();
  expect(screen.getByText(/Closed and locked. Remaining checks are for review/)).toBeTruthy();
});

it("shows load failures rather than an empty successful checklist", async () => {
  vi.mocked(getPilotCollection).mockRejectedValue(new Error("Field pilot not found"));
  render(<PilotCollectionChecks projectId="p" pilotId="missing" />, { wrapper });
  expect((await screen.findByRole("alert")).textContent).toContain("Field pilot not found");
  expect(screen.queryByText(/No follow-up checks match/)).toBeNull();
});
