// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { PilotEconomicsReport, PilotEconomicsRequest } from "@/shared/api/fieldEconomics";
import { PilotEconomics } from "../PilotEconomics";

let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => {
  qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
const props = { projectId: "project_test", pilotId: "pilot_test", revision: 2, currency: "KRW", eligible: true };
const assumptions: PilotEconomicsRequest = { revision: 2, currency: "KRW", contribution_per_conversion_minor: 1000,
  labor_per_hour_minor: 3600, seconds_per_encounter_a: 0, seconds_per_encounter_b: 60, eligible_encounters_per_day: 100 };
function report(): PilotEconomicsReport {
  return { method: "fixed-pilot-cost-scenario-v1", pilot_id: "pilot_test", finalized_at: "closed", target_sku: "tea",
    planned_encounters: 40, assumptions, conversion_difference: 1, conversion_ci_low: 0.5, conversion_ci_high: 1,
    incremental_labor_minor: 60, break_even_difference: 0.06,
    per_encounter: { estimate_minor: 940, low_minor: 440, high_minor: 940 },
    per_day: { estimate_minor: 94000, low_minor: 44000, high_minor: 94000 }, notes: ["Offline fixture only."] };
}
const labels = ["Contribution per converted encounter (minor units)", "Loaded labor cost per hour (minor units)",
  "Average staff seconds per assigned encounter · A", "Average staff seconds per assigned encounter · B", "Assumed eligible encounters per day"];
function fill(values = ["1000", "3600", "0", "60", "100"]) {
  labels.forEach((label, index) => fireEvent.change(screen.getByLabelText(label), { target: { value: values[index] } }));
}

it("gates open or incomplete pilots and never invents cost inputs", () => {
  const view = render(<PilotEconomics {...props} eligible={false} />, { wrapper });
  expect(screen.getByText(/Do not close early/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Calculate cost scenario" })).toBeNull();
  view.rerender(<PilotEconomics {...props} />);
  labels.forEach((label) => expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe(""));
  expect((screen.getByRole("button", { name: "Calculate cost scenario" }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("sends explicit costs with currency and revision and clears results after any edit", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<PilotEconomics {...props} />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Calculate cost scenario" }));
  expect(await screen.findByText(/Locked revision 2/)).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/project_test/staff-pilots/pilot_test/economics"), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(assumptions),
  });
  expect(screen.getByText("6 pp")).toBeTruthy();
  expect(screen.getByText(/not prediction intervals for realized daily profit/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(labels[4]!), { target: { value: "200" } });
  expect(screen.queryByText(/Locked revision 2/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Export cost scenario CSV" })).toBeNull();
});

it("accepts explicit zero assumptions while rejecting blank, fractional and excessive values", async () => {
  render(<PilotEconomics {...props} />, { wrapper }); fill(["0", "0", "0", "0", "0"]);
  const button = screen.getByRole("button", { name: "Calculate cost scenario" }) as HTMLButtonElement;
  expect(button.disabled).toBe(false);
  for (const invalid of ["", "1.5", "1000000001"]) {
    fireEvent.change(screen.getByLabelText(labels[0]!), { target: { value: invalid } });
    expect(button.disabled).toBe(true);
  }
  fill(["0", "0", "0", "0", "0"]);
  const zero = report(); zero.break_even_difference = null;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(zero)));
  fireEvent.click(button);
  expect(await screen.findByText("Undefined at zero contribution")).toBeTruthy();
});

it("locks inputs during calculation and surfaces stale-revision errors without a result", async () => {
  let finish!: (response: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  render(<PilotEconomics {...props} />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Calculate cost scenario" }));
  await waitFor(() => expect((screen.getByLabelText(labels[0]!) as HTMLInputElement).disabled).toBe(true));
  finish(new Response(JSON.stringify({ detail: "The saved pilot revision changed" }), { status: 409 }));
  expect((await screen.findByRole("alert")).textContent).toContain("revision changed");
  expect(screen.queryByRole("button", { name: "Export cost scenario CSV" })).toBeNull();
  expect((screen.getByLabelText(labels[0]!) as HTMLInputElement).disabled).toBe(false);
});

it("downloads the successful scenario snapshot and releases its URL", async () => {
  const createURL = vi.fn(() => "blob:cost-scenario"); const revokeURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: revokeURL }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockResolvedValueOnce(new Response("scenario,csv"));
  render(<PilotEconomics {...props} />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Calculate cost scenario" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export cost scenario CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(fetchMock).toHaveBeenLastCalledWith(expect.stringContaining("/pilot_test/economics.csv"), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(assumptions),
  });
  const anchor = click.mock.contexts[0] as HTMLAnchorElement;
  expect(anchor.download).toBe("pilot_test-cost-scenario-r2.csv");
  expect(anchor.href).toBe("blob:cost-scenario");
  await waitFor(() => expect(revokeURL).toHaveBeenCalledWith("blob:cost-scenario"));
});

it("reports export failures and preserves an unclipped break-even threshold", async () => {
  const data = report(); data.break_even_difference = 2;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(data)))
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Source no longer available" }), { status: 404 }));
  render(<PilotEconomics {...props} />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Calculate cost scenario" }));
  expect(await screen.findByText("200 pp")).toBeTruthy();
  expect(screen.getByText(/outside the possible/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Export cost scenario CSV" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Source no longer available");
});
