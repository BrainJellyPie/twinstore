// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { startPitch, type PitchReport } from "@/shared/api/marketing";
import { StaffPitchBuilder } from "../StaffPitchBuilder";
import { StaffPitchReportView } from "../StaffPitchReport";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]) }));
vi.mock("@/shared/api/marketing", async (original) => ({ ...await original<typeof import("@/shared/api/marketing")>(), startPitch: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
beforeEach(() => { vi.mocked(startPitch).mockResolvedValue({ job_id: "pit_test", kind: "pitch", status: "pending", name: "Test", stage: "queued", progress: 0, error: "", created_at: "", finished_at: "" }); });

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{children}</QueryClientProvider>;
}
const products = [{ sku: "tea", name: "Tea", price: 2500, regularPrice: 2500, promo: "", facings: 1, racks: ["r1"] }];
function fill() {
  fireEvent.change(screen.getByLabelText("Script A text"), { target: { value: "Can I help?" } });
  fireEvent.change(screen.getByLabelText("Script B text"), { target: { value: "Would you like to compare the teas?" } });
}

describe("staff script builder", () => {
  it("submits the exact scripts, product, context and seed with a capped call estimate", async () => {
    const started = vi.fn();
    render(<StaffPitchBuilder projectId="p" setupId="s" products={products} currency="KRW" personaCount={25} onStarted={started} />, { wrapper });
    expect((screen.getByRole("button", { name: "Test staff scripts" }) as HTMLButtonElement).disabled).toBe(true);
    fill();
    fireEvent.change(screen.getByLabelText("Encounter context"), { target: { value: "At the tea shelf." } });
    fireEvent.change(screen.getByLabelText("Verified product facts (optional)"), { target: { value: "500 ml bottle" } });
    fireEvent.change(screen.getByLabelText("Random seed"), { target: { value: "7" } });
    expect(screen.getByText(/25 shoppers × 2 scripts = 50 planned model requests/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Test staff scripts" }));
    await waitFor(() => expect(started).toHaveBeenCalled());
    expect(startPitch).toHaveBeenCalledWith("p", expect.objectContaining({
      setup_id: "s", sku: "tea", context: "At the tea shelf.", product_facts: "500 ml bottle", panel: 40, seed: 7,
      variants: [{ name: "Current greeting", script: "Can I help?" }, { name: "Helpful recommendation", script: "Would you like to compare the teas?" }],
    }));
  });

  it("blocks identical scripts, blank or fractional settings and insufficient personas", () => {
    const props = { projectId: "p", setupId: "s", products, currency: "USD", personaCount: 30, onStarted: vi.fn() };
    const view = render(<StaffPitchBuilder {...props} />, { wrapper });
    fill();
    const button = screen.getByRole("button", { name: "Test staff scripts" }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    fireEvent.change(screen.getByLabelText("Script B text"), { target: { value: "  CAN I HELP? " } });
    expect(button.disabled).toBe(true);
    expect(screen.getByRole("alert").textContent).toContain("different wording");
    fill();
    fireEvent.change(screen.getByLabelText("Requested shoppers"), { target: { value: "20.5" } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Requested shoppers"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("Random seed"), { target: { value: "" } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Random seed"), { target: { value: "1" } });
    expect(button.disabled).toBe(false);
    view.rerender(<StaffPitchBuilder {...props} personaCount={19} />);
    expect(button.disabled).toBe(true);
    expect(screen.getByRole("alert").textContent).toContain("at least 20 personas");
  });

  it("shows start errors without navigating to a made-up report", async () => {
    vi.mocked(startPitch).mockRejectedValue(new Error("Choose a configured text model"));
    const started = vi.fn();
    render(<StaffPitchBuilder projectId="p" setupId="s" products={products} currency="USD" personaCount={40} onStarted={started} />, { wrapper });
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Test staff scripts" }));
    expect((await screen.findByRole("alert")).textContent).toContain("configured text model");
    expect(started).not.toHaveBeenCalled();
  });
});

it("reports synthetic units, incomplete pairs, signed differences and saved stimuli", () => {
  const report: PitchReport = {
    pitch_id: "pit_test", name: "Greeting comparison", model: "fake", attempted: 25, pairs: 19, excluded: 6,
    request: { setup_id: "s", sku: "tea", name: "Test", variants: [{ name: "Neutral", script: "Hello." }, { name: "Helpful", script: "Need help?" }],
      context: "At the shelf.", product_facts: "500 ml", panel: 25, seed: 1, model: "fake" },
    product: { sku: "tea", name: "Tea", price: 2500, currency: "KRW", promo: "" },
    comparisons: [{ metric: "purchase_intent", a_mean: 3, b_mean: 2.5, diff: -0.5, ci_low: null, ci_high: null }],
    segments: [], screening_leader: null, recommendation: "No clear screening leader.", seconds: 2,
    answers: [{ respondent: "p0", age_group: "30s", gender: "Female", first_arm: "A", a: null, b: null, error_a: "Unavailable", error_b: "Unavailable" }],
    notes: ["Synthetic screening only."],
  };
  render(<StaffPitchReportView projectId="p" report={report} />);
  expect(screen.getByText(/19 complete pairs \/ 25 attempted/)).toBeTruthy();
  expect(screen.getByText("Insufficient pairs")).toBeTruthy();
  expect(screen.getByText("-0.50")).toBeTruthy();
  expect(screen.getByText(/not observed purchase conversion/)).toBeTruthy();
  expect(screen.getByText("Hello.")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Paired answers CSV" }).getAttribute("href")).toContain("/staff-pitches/pit_test/export.csv");
  expect(screen.getByText(/p0.*excluded pair/)).toBeTruthy();
});
