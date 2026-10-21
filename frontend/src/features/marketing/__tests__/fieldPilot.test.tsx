// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { closePilot, createPilot, getPilotImport, importPilot, pilotKeys, previewPilotImport, previewPilotPlan, type ObservationPreview, type PilotPlanningResult, type PilotView } from "@/shared/api/fieldPilot";
import type { PitchReport } from "@/shared/api/marketing";
import { PilotBuilder, PilotResults } from "../FieldPilots";

vi.mock("@/shared/api/fieldPilot", async (original) => ({ ...await original<typeof import("@/shared/api/fieldPilot")>(), createPilot: vi.fn(), importPilot: vi.fn(), closePilot: vi.fn(), previewPilotPlan: vi.fn(), previewPilotImport: vi.fn(), getPilotImport: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const source: PitchReport = {
  pitch_id: "pit_test", name: "Tea scripts", model: "fake", attempted: 20, pairs: 20, excluded: 0,
  request: { setup_id: "s", sku: "tea", name: "Test", variants: [{ name: "Current", script: "Hello" }, { name: "New", script: "Can I help?" }], context: "Tea shelf", product_facts: "", panel: 20, seed: 1, model: "fake" },
  product: { sku: "tea", name: "Tea", price: 2000, currency: "KRW", promo: "" }, comparisons: [], segments: [], screening_leader: null, recommendation: "", answers: [], notes: [], seconds: 0,
};
function result(): PilotView {
  const arm = { planned: 20, enrolled: 2, unused: 0, unrecorded: 18, observed: 1, purchases: 1, missing_outcomes: 1,
    not_delivered: 1, delivery_unknown: 1, observed_rate: 1, missing_bound_low: 0.5, missing_bound_high: 1 };
  return { pilot: { pilot_id: "pilot_test", pitch_id: source.pitch_id, created_at: "now", updated_at: "now", finalized_at: "", revision: 3,
    design: { name: "Real tea", eligibility: "First eligible encounter", outcome_window: "Same visit", seed: 4, blocks: [{ staff_id: "s1", shift_id: "am", encounters: 40 }] },
    product: source.product, variants: source.request.variants, context: source.request.context, product_facts: "", assignments: [],
  }, analysis: { a: { ...arm, arm: "A" }, b: { ...arm, arm: "B", enrolled: 0, observed: 0, purchases: 0, missing_outcomes: 0, observed_rate: null, missing_bound_low: null, missing_bound_high: null },
    blocks: [], target_completed: false, can_finalize: false, inference_ready: false, difference: null, ci_low: null, ci_high: null, interpretation: "Collection is open.", notes: [],
  } };
}
let qc: QueryClient;
beforeEach(() => { qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }

function observationPreview(): ObservationPreview {
  return { pilot_id: "pilot_test", revision: 3, review_token: "a".repeat(64),
    summary: { changed_assignments: 1, changed_fields: 2, new_values: 0, corrected_values: 1, cleared_values: 1, removed_enrollments: 0, purchase_reversals: 1 },
    changes: [{ assignment_id: "slot_1", staff_id: "s1", shift_id: "am", sequence: 1, arm: "A", field: "delivered", before: true, after: null },
      { assignment_id: "slot_1", staff_id: "s1", shift_id: "am", sequence: 1, arm: "A", field: "purchased", before: false, after: true }] };
}

function planningResult(counts = [100]): PilotPlanningResult {
  const total = counts.reduce((a, b) => a + b, 0);
  return { method: "hoeffding-fixed-v1", assumptions: { minimum_effect: 0.2, target_power: 0.8, eligible_per_day: 30, available_days: 14 },
    block_counts: counts, planned_encounters: total, required_encounters: 510, planned_power_lower_bound: total >= 510 ? 0.8 : 0,
    planned_ci_half_width: 0.272, planned_days: Math.ceil(total / 30), required_days: 17, suggested_block_counts: [510], notes: ["Planning assumptions only."] };
}
function enterPlanning() {
  fireEvent.click(screen.getByLabelText("Plan sample size and duration"));
  fireEvent.change(screen.getByLabelText("Minimum effect (percentage points)"), { target: { value: "20" } });
  fireEvent.change(screen.getByLabelText("Eligible encounters per operating day"), { target: { value: "30" } });
  fireEvent.change(screen.getByLabelText("Available operating days"), { target: { value: "14" } });
}

describe("field pilot planning", () => {
  it("saves a precommitted staff/shift plan from the selected script snapshot", async () => {
    vi.mocked(createPilot).mockResolvedValue(result());
    const done = vi.fn();
    render(<PilotBuilder projectId="p" source={source} onCreated={done} />, { wrapper });
    const button = screen.getByRole("button", { name: "Save fixed pilot plan" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Eligible encounters"), { target: { value: "First eligible tea encounter per customer" } });
    fireEvent.change(screen.getByLabelText("Planned encounters 1"), { target: { value: "40" } });
    fireEvent.change(screen.getByLabelText("Allocation seed"), { target: { value: "8" } });
    fireEvent.click(button);
    await waitFor(() => expect(done).toHaveBeenCalledWith("pilot_test"));
    expect(createPilot).toHaveBeenCalledWith("p", "pit_test", expect.objectContaining({ seed: 8, blocks: [{ staff_id: "staff_1", shift_id: "shift_1", encounters: 40 }] }));
  });

  it("blocks odd counts, duplicate blocks and blank seeds", () => {
    render(<PilotBuilder projectId="p" source={source} onCreated={vi.fn()} />, { wrapper });
    fireEvent.change(screen.getByLabelText("Eligible encounters"), { target: { value: "Each customer once" } });
    const button = screen.getByRole("button", { name: "Save fixed pilot plan" }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    fireEvent.change(screen.getByLabelText("Planned encounters 1"), { target: { value: "41" } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Planned encounters 1"), { target: { value: "40" } });
    fireEvent.click(screen.getByRole("button", { name: "Add staff/shift" }));
    fireEvent.change(screen.getByLabelText("Staff alias 2"), { target: { value: "staff_1" } });
    expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Remove last block" }));
    fireEvent.change(screen.getByLabelText("Allocation seed"), { target: { value: "" } });
    expect(button.disabled).toBe(true);
  });
});

describe("observed field results", () => {
  it("preserves unknown outcomes and blocks early closing without displaying effect intervals", () => {
    render(<PilotResults projectId="p" view={result()} />, { wrapper });
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
    expect(screen.queryByText(/conservative 95% interval/)).toBeNull();
    fireEvent.click(screen.getByLabelText("I am ending collection and locking these observations."));
    expect((screen.getByRole("button", { name: "Close and lock pilot" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("link", { name: "Observation sheet CSV" }).getAttribute("href")).toContain("pilot_test/observations.csv");
  });

  it("uploads with the visible revision and preserves cached data on stale-write rejection", async () => {
    const view = result(); qc.setQueryData(pilotKeys.detail("p", "pilot_test"), view);
    vi.mocked(previewPilotImport).mockResolvedValue(observationPreview());
    vi.mocked(importPilot).mockRejectedValue(new Error("The pilot changed in another session. Reload it before importing"));
    render(<PilotResults projectId="p" view={view} />, { wrapper });
    const file = new File(["records"], "observations.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Review full observation sheet"), { target: { files: [file] } });
    await screen.findByText(/Proposed changes/);
    expect(importPilot).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Import reason"), { target: { value: "Verified correction" } });
    fireEvent.click(screen.getByLabelText("I reviewed the changes, including corrections and cleared values."));
    fireEvent.click(screen.getByRole("button", { name: "Apply reviewed observations" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Reload it");
    expect(importPilot).toHaveBeenCalledWith("p", "pilot_test", file, 3, observationPreview().review_token, "Verified correction");
    expect(qc.getQueryData(pilotKeys.detail("p", "pilot_test"))).toEqual(view);
  });

  it("requires deliberate closure and shows locked final results without editing controls", async () => {
    const view = result(); view.analysis.can_finalize = true;
    const closed = result(); closed.pilot.finalized_at = "now"; closed.pilot.revision = 4;
    closed.analysis.inference_ready = true; closed.analysis.difference = 0.2; closed.analysis.ci_low = -0.1; closed.analysis.ci_high = 0.5;
    vi.mocked(closePilot).mockResolvedValue(closed);
    const screenView = render(<PilotResults projectId="p" view={view} />, { wrapper });
    const button = screen.getByRole("button", { name: "Close and lock pilot" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("I am ending collection and locking these observations."));
    fireEvent.click(button);
    await waitFor(() => expect(closePilot).toHaveBeenCalledWith("p", "pilot_test", 3));
    screenView.rerender(<PilotResults projectId="p" view={closed} />);
    expect(screen.getByText(/Closed and locked/)).toBeTruthy();
    expect(screen.getByText(/conservative 95% interval/)).toBeTruthy();
    expect(screen.queryByLabelText("Review full observation sheet")).toBeNull();
    expect(screen.queryByRole("button", { name: "Close and lock pilot" })).toBeNull();
  });
});

describe("observation review and history", () => {
  it("applies the reviewed file and updates the visible pilot cache only after confirmation", async () => {
    const view = result(); qc.setQueryData(pilotKeys.detail("p", "pilot_test"), view);
    qc.setQueryData(pilotKeys.collection("p", "pilot_test"), { revision: 3 });
    vi.mocked(previewPilotImport).mockResolvedValue(observationPreview());
    const saved = result(); saved.pilot.revision = 4;
    vi.mocked(importPilot).mockResolvedValue(saved);
    render(<PilotResults projectId="p" view={view} />, { wrapper });
    const file = new File(["records"], "records.csv");
    fireEvent.change(screen.getByLabelText("Review full observation sheet"), { target: { files: [file] } });
    await screen.findByText(/Proposed changes/);
    expect(previewPilotImport).toHaveBeenCalledWith("p", "pilot_test", file, 3);
    expect(qc.getQueryData(pilotKeys.detail("p", "pilot_test"))).toEqual(view);
    fireEvent.change(screen.getByLabelText("Import reason"), { target: { value: "  Corrected source transcription  " } });
    fireEvent.click(screen.getByLabelText("I reviewed the changes, including corrections and cleared values."));
    fireEvent.click(screen.getByRole("button", { name: "Apply reviewed observations" }));
    await waitFor(() => expect(qc.getQueryData(pilotKeys.detail("p", "pilot_test"))).toEqual(saved));
    expect(importPilot).toHaveBeenCalledWith("p", "pilot_test", file, 3, observationPreview().review_token, "Corrected source transcription");
    await waitFor(() => expect(screen.queryByText(/Proposed changes/)).toBeNull());
    expect(qc.getQueryState(pilotKeys.collection("p", "pilot_test"))?.isInvalidated).toBe(true);
  });

  it("requires a reason and review, blocks closing a pending preview, and can discard without saving", async () => {
    vi.mocked(previewPilotImport).mockResolvedValue(observationPreview());
    const view = result(); view.analysis.can_finalize = true;
    render(<PilotResults projectId="p" view={view} />, { wrapper });
    fireEvent.click(screen.getByLabelText("I am ending collection and locking these observations."));
    const close = screen.getByRole("button", { name: "Close and lock pilot" }) as HTMLButtonElement;
    expect(close.disabled).toBe(false);
    const file = new File(["data"], "observations.csv");
    fireEvent.change(screen.getByLabelText("Review full observation sheet"), { target: { files: [file] } });
    expect(await screen.findByText(/1 known values cleared/)).toBeTruthy();
    expect(close.disabled).toBe(true);
    const apply = screen.getByRole("button", { name: "Apply reviewed observations" }) as HTMLButtonElement;
    fireEvent.click(screen.getByLabelText("I reviewed the changes, including corrections and cleared values."));
    expect(apply.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Import reason"), { target: { value: "Initial capture review" } });
    expect(apply.disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Discard preview" }));
    expect(screen.queryByText(/Proposed changes/)).toBeNull();
    expect(close.disabled).toBe(false);
    expect(importPilot).not.toHaveBeenCalled();
  });

  it("does not offer to save a no-op sheet and resets confirmation when selecting another file", async () => {
    vi.mocked(previewPilotImport).mockResolvedValueOnce(observationPreview()).mockResolvedValueOnce({ ...observationPreview(),
      changes: [], summary: { changed_assignments: 0, changed_fields: 0, new_values: 0, corrected_values: 0, cleared_values: 0, removed_enrollments: 0, purchase_reversals: 0 } });
    render(<PilotResults projectId="p" view={result()} />, { wrapper });
    const input = screen.getByLabelText("Review full observation sheet");
    fireEvent.change(input, { target: { files: [new File(["changed"], "changed.csv")] } });
    await screen.findByText(/Proposed changes/);
    fireEvent.click(screen.getByLabelText("I reviewed the changes, including corrections and cleared values."));
    fireEvent.change(input, { target: { files: [new File(["same"], "same.csv")] } });
    expect(await screen.findByText(/No observation values changed/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Apply reviewed observations" })).toBeNull();
    expect(importPilot).not.toHaveBeenCalled();
  });

  it("leaves observations untouched when preview fails", async () => {
    vi.mocked(previewPilotImport).mockRejectedValue(new Error("Row 2: assigned pilot, staff, shift, sequence and arm cannot be changed"));
    const view = result(); qc.setQueryData(pilotKeys.detail("p", "pilot_test"), view);
    render(<PilotResults projectId="p" view={view} />, { wrapper });
    fireEvent.change(screen.getByLabelText("Review full observation sheet"), { target: { files: [new File(["bad"], "bad.csv")] } });
    expect((await screen.findByRole("alert")).textContent).toContain("cannot be changed");
    expect(importPilot).not.toHaveBeenCalled();
    expect(qc.getQueryData(pilotKeys.detail("p", "pilot_test"))).toEqual(view);
  });

  it("shows saved changes and export after closure and identifies the legacy history boundary", async () => {
    const view = result(); view.pilot.finalized_at = "closed"; view.pilot.history_start_revision = 2;
    const record = { revision: 3, imported_at: "2026-10-21T00:00:00Z", reason: "Corrected from source records", source_sha256: "a".repeat(64), summary: observationPreview().summary };
    view.pilot.import_history = [record];
    vi.mocked(getPilotImport).mockResolvedValue({ record, changes: observationPreview().changes });
    render(<PilotResults projectId="p" view={view} />, { wrapper });
    expect(screen.getByText(/Import history starts after revision 2/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Export import history CSV", hidden: true }).getAttribute("href")).toContain("pilot_test/imports.csv");
    fireEvent.click(screen.getByText("Observation import history (1)"));
    fireEvent.click(screen.getByRole("button", { name: "Review revision 3" }));
    expect(await screen.findByText(/Uploaded CSV SHA-256/)).toBeTruthy();
    expect(screen.getByText("Changes 1–2 of 2")).toBeTruthy();
    expect(screen.queryByLabelText("Review full observation sheet")).toBeNull();
  });
});

describe("sample size and feasibility", () => {
  it("calculates, applies even counts and saves assumptions with the actual design", async () => {
    vi.mocked(previewPilotPlan).mockImplementation(async (_p, _a, counts) => planningResult(counts));
    vi.mocked(createPilot).mockResolvedValue(result());
    render(<PilotBuilder projectId="p" source={source} onCreated={vi.fn()} />, { wrapper });
    fireEvent.change(screen.getByLabelText("Eligible encounters"), { target: { value: "First eligible encounter" } });
    enterPlanning();
    expect(await screen.findByText(/current sample does not meet/)).toBeTruthy();
    expect(screen.getByText("The required sample exceeds the available operating days.")).toBeTruthy();
    expect(previewPilotPlan).toHaveBeenCalledWith("p", planningResult().assumptions, [100], expect.any(AbortSignal));
    fireEvent.click(screen.getByRole("button", { name: "Use recommended counts evenly across these blocks" }));
    expect((screen.getByLabelText("Planned encounters 1") as HTMLInputElement).value).toBe("510");
    expect(await screen.findByText(/current sample meets/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save fixed pilot plan" }));
    await waitFor(() => expect(createPilot).toHaveBeenCalledWith("p", "pit_test", expect.objectContaining({
      planning: planningResult().assumptions, blocks: [{ staff_id: "staff_1", shift_id: "shift_1", encounters: 510 }],
    })));
  });

  it("hides stale calculations after editing assumptions and blocks invalid planning inputs", async () => {
    vi.mocked(previewPilotPlan).mockResolvedValue(planningResult());
    render(<PilotBuilder projectId="p" source={source} onCreated={vi.fn()} />, { wrapper });
    fireEvent.change(screen.getByLabelText("Eligible encounters"), { target: { value: "Each customer once" } });
    enterPlanning();
    await screen.findByText(/Required for the target:/);
    fireEvent.change(screen.getByLabelText("Minimum effect (percentage points)"), { target: { value: "" } });
    expect(screen.queryByText(/Required for the target:/)).toBeNull();
    expect((screen.getByRole("button", { name: "Save fixed pilot plan" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Plan sample size and duration"));
    expect((screen.getByRole("button", { name: "Save fixed pilot plan" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("does not show a capped sufficient sample when requirements exceed capacity", async () => {
    vi.mocked(previewPilotPlan).mockResolvedValue({ ...planningResult(), required_encounters: 50000, required_days: 1667, suggested_block_counts: null });
    render(<PilotBuilder projectId="p" source={source} onCreated={vi.fn()} />, { wrapper });
    enterPlanning();
    expect(await screen.findByText(/No smaller sample is presented as sufficient/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Use recommended counts evenly across these blocks" })).toBeNull();
  });

  it("does not retain an old recommendation while a changed valid assumption is calculating", async () => {
    vi.mocked(previewPilotPlan).mockResolvedValueOnce(planningResult()).mockImplementation(() => new Promise(() => {}));
    render(<PilotBuilder projectId="p" source={source} onCreated={vi.fn()} />, { wrapper });
    enterPlanning();
    await screen.findByText(/Required for the target:/);
    fireEvent.change(screen.getByLabelText("Minimum effect (percentage points)"), { target: { value: "5" } });
    expect(screen.getByText("Calculating sample requirements…")).toBeTruthy();
    expect(screen.queryByText(/Required for the target:/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Use recommended counts evenly across these blocks" })).toBeNull();
  });

  it("shows the saved assessment without offering to resize a collecting pilot", () => {
    const view = result(); view.pilot.planning = planningResult();
    view.pilot.planning.planned_power_lower_bound = 0.999999999;
    render(<PilotResults projectId="p" view={view} />, { wrapper });
    expect(screen.getByText("Saved sample planning assessment")).toBeTruthy();
    expect(screen.getByText(/Planning assumptions: 20.0 pp/)).toBeTruthy();
    expect(screen.getByText(/at least 99.9% power/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Use recommended counts evenly across these blocks" })).toBeNull();
  });

  it("surfaces a failed planning request instead of showing a result", async () => {
    vi.mocked(previewPilotPlan).mockRejectedValue(new Error("Project not found"));
    render(<PilotBuilder projectId="p" source={source} onCreated={vi.fn()} />, { wrapper });
    enterPlanning();
    expect((await screen.findByRole("alert")).textContent).toBe("Project not found");
    expect(screen.queryByText(/Required for the target:/)).toBeNull();
  });
});
