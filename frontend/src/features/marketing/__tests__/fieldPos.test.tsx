// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { importPilot, previewPilotImport, previewPilotPos, type FieldPilot, type PilotPosPreview, type ObservationPreview, type PilotView } from "@/shared/api/fieldPilot";
import { PilotObservationReview } from "../PilotObservationReview";
import { PilotPosReconciliation } from "../PilotPosReconciliation";

vi.mock("@/shared/api/fieldPilot", async (original) => ({ ...await original<typeof import("@/shared/api/fieldPilot")>(), previewPilotPos: vi.fn(), previewPilotImport: vi.fn(), importPilot: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
let qc: QueryClient;
beforeEach(() => { qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } }); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }

const pilot: FieldPilot = {
  pilot_id: "pilot_test", pitch_id: "pit_test", created_at: "now", updated_at: "now", finalized_at: "", revision: 3,
  design: { name: "Tea pilot", eligibility: "Each customer once", outcome_window: "Same visit", seed: 1,
    blocks: [{ staff_id: "s1", shift_id: "am", encounters: 40 }] },
  product: { sku: "tea", name: "Tea", price: 1, currency: "USD", promo: "" },
  variants: [{ name: "A", script: "Hi" }, { name: "B", script: "Hello" }], context: "Tea aisle", product_facts: "", assignments: [],
};
function report(): PilotPosPreview {
  return { pilot_id: "pilot_test", revision: 3, target_sku: "tea", outcome_window: "Same visit", source_sha256: "a".repeat(64),
    source_rows: 2, transactions: 2, linked_assignments: 2, enrolled_without_evidence: 8, proposed_purchases: 1,
    matches: [{ assignment_id: "slot1", transaction_ids: ["tx1"], target_units: 2, status: "proposed_purchase", staff_id: "s1", shift_id: "am", sequence: 1 },
      { assignment_id: "slot2", transaction_ids: ["tx2"], target_units: 1, status: "conflicting_purchase", staff_id: "s1", shift_id: "am", sequence: 2 }],
    candidate_csv: "candidate full sheet", notes: ["Offline fixture only."] };
}
const changes: ObservationPreview = { pilot_id: "pilot_test", revision: 3, review_token: "b".repeat(64),
  summary: { changed_assignments: 1, changed_fields: 1, new_values: 1, corrected_values: 0, cleared_values: 0, removed_enrollments: 0, purchase_reversals: 0 },
  changes: [{ assignment_id: "slot1", staff_id: "s1", shift_id: "am", sequence: 1, arm: "A", field: "purchased", before: null, after: true }] };
function uploadPos() {
  const file = new File(["offline POS fixture"], "pos.csv", { type: "text/csv" });
  fireEvent.change(screen.getByLabelText("Preview POS CSV"), { target: { files: [file] } });
  return file;
}

it("hands all proposals to the existing full-sheet review and saves only after its confirmation", async () => {
  vi.mocked(previewPilotPos).mockResolvedValue(report());
  vi.mocked(previewPilotImport).mockResolvedValue(changes);
  const saved = vi.fn().mockResolvedValue(undefined), active = vi.fn();
  // The component forwards the existing API response without modifying it.
  const updated = { pilot: { ...pilot, revision: 4 } } as PilotView;
  vi.mocked(importPilot).mockResolvedValue(updated);
  render(<PilotObservationReview projectId="p" pilot={pilot} disabled={false} onActive={active} onSaved={saved} />, { wrapper });
  const file = uploadPos();
  await screen.findByText("1 proposed purchases");
  expect(previewPilotPos).toHaveBeenCalledWith("p", "pilot_test", file, 3);
  expect(previewPilotImport).not.toHaveBeenCalled(); expect(importPilot).not.toHaveBeenCalled();
  expect((screen.getByLabelText("Review full observation sheet") as HTMLInputElement).disabled).toBe(true);
  const review = screen.getByRole("button", { name: "Review proposed purchase changes" }) as HTMLButtonElement;
  expect(review.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("POS match filter"), { target: { value: "conflicting_purchase" } });
  fireEvent.click(screen.getByLabelText(/I verified the target SKU/));
  fireEvent.click(review);
  await screen.findByText(/Proposed changes · revision 3/);
  expect(previewPilotImport).toHaveBeenCalledWith("p", "pilot_test", expect.any(File), 3);
  expect(importPilot).not.toHaveBeenCalled();
  expect((screen.getByLabelText("Import reason") as HTMLTextAreaElement).value).toContain(report().source_sha256);
  fireEvent.click(screen.getByLabelText("I reviewed the changes, including corrections and cleared values."));
  fireEvent.click(screen.getByRole("button", { name: "Apply reviewed observations" }));
  await waitFor(() => expect(saved).toHaveBeenCalledWith(updated));
  expect(importPilot).toHaveBeenCalledWith("p", "pilot_test", expect.any(File), 3, changes.review_token, expect.stringContaining(report().source_sha256));
  expect(active).toHaveBeenLastCalledWith(false);
});

it("keeps conflicts and missing matches out of the save path and supports pagination/filtering", async () => {
  const data = report(); data.proposed_purchases = 0;
  data.matches = Array.from({ length: 51 }, (_, i) => ({ assignment_id: `slot${i}`, transaction_ids: [`tx${i}`], target_units: 0,
    status: "no_target_evidence", staff_id: "s1", shift_id: "am", sequence: i + 1 }));
  vi.mocked(previewPilotPos).mockResolvedValue(data);
  const review = vi.fn(), active = vi.fn();
  render(<PilotPosReconciliation projectId="p" pilot={pilot} disabled={false} onActive={active} onReview={review} />, { wrapper });
  uploadPos(); await screen.findByText("Matches 1–50 of 51");
  fireEvent.click(screen.getByRole("button", { name: "Next POS matches" }));
  expect(screen.getByText("Matches 51–51 of 51")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("POS match filter"), { target: { value: "conflicting_purchase" } });
  expect(screen.getByText("No matches in this category.")).toBeTruthy();
  fireEvent.click(screen.getByLabelText(/I verified the target SKU/));
  expect((screen.getByRole("button", { name: "Review proposed purchase changes" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Discard POS preview" }));
  expect(review).not.toHaveBeenCalled(); expect(active).toHaveBeenLastCalledWith(false);
});

it("blocks overlapping file reviews while matching and recovers after server errors", async () => {
  let reject!: (reason: Error) => void;
  vi.mocked(previewPilotPos).mockReturnValue(new Promise((_, fail) => { reject = fail; }));
  const active = vi.fn();
  render(<PilotObservationReview projectId="p" pilot={pilot} disabled={false} onActive={active} onSaved={vi.fn()} />, { wrapper });
  uploadPos(); await screen.findByText(/Matching transactions without saving/);
  expect((screen.getByLabelText("Review full observation sheet") as HTMLInputElement).disabled).toBe(true);
  reject(new Error("One transaction cannot belong to multiple assignments"));
  expect((await screen.findByRole("alert")).textContent).toContain("multiple assignments");
  expect((screen.getByLabelText("Review full observation sheet") as HTMLInputElement).disabled).toBe(false);
  expect(active).toHaveBeenLastCalledWith(false); expect(importPilot).not.toHaveBeenCalled();
});

it("rejects oversized files locally and refuses stale candidate reviews without writing", async () => {
  const active = vi.fn();
  render(<PilotObservationReview projectId="p" pilot={pilot} disabled={false} onActive={active} onSaved={vi.fn()} />, { wrapper });
  fireEvent.change(screen.getByLabelText("Preview POS CSV"), { target: { files: [new File(["x".repeat(2 * 1024 * 1024 + 1)], "large.csv")] } });
  expect(screen.getByRole("alert").textContent).toContain("2 MB"); expect(previewPilotPos).not.toHaveBeenCalled();
  vi.mocked(previewPilotPos).mockResolvedValue(report());
  vi.mocked(previewPilotImport).mockRejectedValue(new Error("The pilot changed or is closed. Reload it"));
  uploadPos(); await screen.findByText("1 proposed purchases");
  fireEvent.click(screen.getByLabelText(/I verified the target SKU/));
  fireEvent.click(screen.getByRole("button", { name: "Review proposed purchase changes" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Reload it");
  expect(importPilot).not.toHaveBeenCalled(); expect(active).toHaveBeenLastCalledWith(false);
});
