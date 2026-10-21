// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { closePilot, createPilot, importPilot, pilotKeys, type PilotView } from "@/shared/api/fieldPilot";
import type { PitchReport } from "@/shared/api/marketing";
import { PilotBuilder, PilotResults } from "../FieldPilots";

vi.mock("@/shared/api/fieldPilot", async (original) => ({ ...await original<typeof import("@/shared/api/fieldPilot")>(), createPilot: vi.fn(), importPilot: vi.fn(), closePilot: vi.fn() }));
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
    vi.mocked(importPilot).mockRejectedValue(new Error("The pilot changed in another session. Reload it before importing"));
    render(<PilotResults projectId="p" view={view} />, { wrapper });
    const file = new File(["records"], "observations.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Import full observation sheet"), { target: { files: [file] } });
    expect((await screen.findByRole("alert")).textContent).toContain("Reload it");
    expect(importPilot).toHaveBeenCalledWith("p", "pilot_test", file, 3);
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
    expect(screen.queryByLabelText("Import full observation sheet")).toBeNull();
    expect(screen.queryByRole("button", { name: "Close and lock pilot" })).toBeNull();
  });
});
