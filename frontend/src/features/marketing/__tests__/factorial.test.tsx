// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { FactorialReport, FactorialSource } from "@/shared/api/factorial";
import { FactorialReview } from "../FactorialReview";

let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
const source: FactorialSource = { available: true, reason: "", source_sha256: "a".repeat(64), price_arms: ["Price"], sign_arms: ["Sign"], combined_arms: ["Both"] };
function report(): FactorialReport {
  return { method: "paired-price-sign-v1", experiment_id: "exp_test", currency: "USD", engine: "rule", model: "", simulation_seed: 1,
    request: { source_sha256: source.source_sha256, price_arm: "Price", sign_arm: "Sign", combined_arm: "Both", metric: "spend" },
    requested_panel: 40, sampled_panel: 40, complete_panel: 40, intervals_available: true, bootstrap_resamples: 4000, bootstrap_seed: 0, family_size: 3,
    cells: [{ cell: "00", arm: "Control", available: 40, mean: 100, changes: [] }],
    contrasts: [{ name: "Price × sign interaction", formula: "11-10-01+00", estimate: 7, ci_low: 7, ci_high: 7 }], rows: [], notes: ["Offline fixture."] };
}
beforeEach(() => { qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
async function selectArms() {
  fireEvent.click(screen.getByRole("button", { name: "Open price × sign analysis" }));
  await screen.findByLabelText("Price-only arm (10)");
  for (const [label, value] of [["Price-only arm (10)", "Price"], ["Sign-only arm (01)", "Sign"], ["Combined arm (11)", "Both"]]) {
    fireEvent.change(screen.getByLabelText(label!), { target: { value } });
  }
}

it("loads only on demand and connects chosen arms and one outcome to the API", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper });
  expect(fetchMock).not.toHaveBeenCalled(); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  expect(await screen.findByText(/40 \/ 40 sampled shoppers/)).toBeTruthy();
  expect(fetchMock.mock.calls[1]![0]).toContain("/exp_test/factorial/preview");
  expect(JSON.parse(fetchMock.mock.calls[1]![1]!.body as string)).toEqual(report().request);
});

it("explains unavailable legacy sources without fabricating an analysis", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ ...source, available: false, reason: "Legacy report has no paired outcomes." })));
  render(<FactorialReview projectId="proj_test" experimentId="exp_old" />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Open price × sign analysis" }));
  expect(await screen.findByText("Legacy report has no paired outcomes.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Calculate paired contrasts" })).toBeNull();
});

it("invalidates the result and export when the outcome changes", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  await screen.findByRole("button", { name: "Export factorial audit CSV" });
  fireEvent.change(screen.getByLabelText("Factorial outcome"), { target: { value: "units" } });
  await waitFor(() => expect(screen.queryByRole("button", { name: "Export factorial audit CSV" })).toBeNull());
});

it("keeps missing cells and unavailable intervals distinct from zero", async () => {
  const data = report(); data.complete_panel = 0; data.intervals_available = false;
  data.cells[0]!.mean = null; data.contrasts[0] = { ...data.contrasts[0]!, estimate: null, ci_low: null, ci_high: null };
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockResolvedValueOnce(new Response(JSON.stringify(data)));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  expect(await screen.findByText(/0 \/ 40 sampled shoppers/)).toBeTruthy();
  expect(screen.getByText(/Intervals withheld/)).toBeTruthy(); expect(screen.getAllByText("Unavailable")).toHaveLength(3);
});

it("preserves small signed contrasts instead of rounding them into zero", async () => {
  const data = report(); data.contrasts[0] = { ...data.contrasts[0]!, estimate: -0.00000005, ci_low: -0.00000005, ci_high: -0.00000005 };
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockResolvedValueOnce(new Response(JSON.stringify(data)));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  expect(await screen.findByText("-0.00000005")).toBeTruthy();
});

it("locks scope inputs during a request and recovers from network failure", async () => {
  let reject!: (error: Error) => void;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  await waitFor(() => expect((screen.getByLabelText("Factorial outcome") as HTMLSelectElement).disabled).toBe(true));
  for (const label of ["Price-only arm (10)", "Sign-only arm (01)", "Combined arm (11)"]) expect((screen.getByLabelText(label) as HTMLSelectElement).disabled).toBe(true);
  reject(new Error("Connection lost"));
  expect((await screen.findByRole("alert")).textContent).toContain("Connection lost");
  expect(screen.queryByRole("button", { name: "Export factorial audit CSV" })).toBeNull();
});

it("discards late preview results after changing the keyed experiment", async () => {
  let finish!: (response: Response) => void;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<FactorialReview key="old" projectId="proj_test" experimentId="exp_old" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  view.rerender(<FactorialReview key="new" projectId="proj_test" experimentId="exp_new" />);
  await act(async () => { finish(new Response(JSON.stringify(report()))); });
  expect(screen.queryByText(/sampled shoppers/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Export factorial audit CSV" })).toBeNull();
});

it("reloads a changed source after a stale request and uses its new hash", async () => {
  const fresh = { ...source, source_sha256: "b".repeat(64) }; const data = report(); data.request.source_sha256 = fresh.source_sha256;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source)))
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Paired source changed; reload." }), { status: 409 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(fresh))).mockResolvedValueOnce(new Response(JSON.stringify(data)));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  expect((await screen.findByRole("alert")).textContent).toContain("source changed");
  fireEvent.click(screen.getByRole("button", { name: "Reload paired source" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Calculate paired contrasts" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  expect(await screen.findByText(/40 \/ 40 sampled shoppers/)).toBeTruthy();
  expect(JSON.parse(fetchMock.mock.calls[3]![1]!.body as string).source_sha256).toBe(fresh.source_sha256);
});

it("surfaces source-load errors and can recover through an explicit reload", async () => {
  fetchMock.mockRejectedValueOnce(new Error("Source unavailable")).mockResolvedValueOnce(new Response(JSON.stringify(source)));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Open price × sign analysis" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Source unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Reload paired source" }));
  await screen.findByLabelText("Price-only arm (10)");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("exports the reviewed request, cleans up blob URLs, and reports deleted sources", async () => {
  const createURL = vi.fn(() => "blob:factorial"); const revokeURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: revokeURL }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockResolvedValueOnce(new Response(JSON.stringify(report())))
    .mockResolvedValueOnce(new Response("audit")).mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Experiment not found" }), { status: 404 }));
  render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export factorial audit CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(JSON.parse(fetchMock.mock.calls[2]![1]!.body as string)).toEqual(report().request);
  expect(fetchMock.mock.calls[2]![0]).toContain("/factorial/export.csv");
  expect((click.mock.contexts[0] as HTMLAnchorElement).download).toBe("exp_test-factorial.csv");
  await waitFor(() => expect(revokeURL).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByRole("button", { name: "Export factorial audit CSV" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Experiment not found");
});

it("does not download an old audit after the experiment view is unmounted", async () => {
  let finish!: (response: Response) => void; const createURL = vi.fn(() => "blob:old");
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: vi.fn() }));
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(source))).mockResolvedValueOnce(new Response(JSON.stringify(report())))
    .mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<FactorialReview projectId="proj_test" experimentId="exp_test" />, { wrapper }); await selectArms();
  fireEvent.click(screen.getByRole("button", { name: "Calculate paired contrasts" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export factorial audit CSV" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  view.unmount(); await act(async () => { finish(new Response("old audit")); });
  expect(createURL).not.toHaveBeenCalled();
});
