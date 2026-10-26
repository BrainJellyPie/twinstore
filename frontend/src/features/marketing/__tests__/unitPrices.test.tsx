// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { UnitPriceReport } from "@/shared/api/unitPrices";
import { UnitPrices } from "../UnitPrices";

let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => { qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } }); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
function report(): UnitPriceReport {
  return { method: "observed-unit-prices-v1", scope: { focal_retailer: "ours", as_of: "2026-10-21", max_age_days: 7 }, source_sha256: "a".repeat(64), notes: ["Offline fixture"],
    rows: [{ inputs: { offer_id: "tea", comparison_group: "tea", retailer: "ours", observed_on: "2026-10-21", currency: "USD", pack_count: 2, quantity_per_pack: "250", unit: "g", price_minor: 300, availability: "in_stock", terms: "public" }, basis: "kg", quantity_in_basis: "0.5", unit_price_minor: "600", unit_price_exact: "600", flags: [] }],
    comparisons: [{ comparison_group: "tea", currency: "USD", basis: "kg", focal_count: 1, competitor_count: 0, competitor_retailers: 0, focal_min_minor: "600", competitor_min_minor: null, gap_minor: null, gap_exact: null, gap_percent: null, relation: "unavailable", focal_offer_ids: ["tea"], competitor_offers: [] }] };
}
function fill(file = new File(["fixture input"], "offers.csv")) {
  fireEvent.change(screen.getByLabelText("Focal retailer ID"), { target: { value: "ours" } });
  fireEvent.change(screen.getByLabelText("As-of date"), { target: { value: "2026-10-21" } });
  fireEvent.change(screen.getByLabelText("Observed offers CSV"), { target: { files: [file] } });
}

it("requires a scope and file, sends exact inputs and shows missing comparisons", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<UnitPrices projectId="project_test" />, { wrapper });
  const button = screen.getByRole("button", { name: "Compare observed offers" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); expect(fetchMock).not.toHaveBeenCalled(); fill(); fireEvent.click(button);
  const summary = await screen.findByText(/1 \/ 1 offers qualify/);
  expect(document.activeElement).toBe(summary);
  expect(screen.getAllByText("Unavailable")).toHaveLength(3);
  const [url, init] = fetchMock.mock.calls[0]!; const body = init?.body as FormData;
  expect(url).toContain("/project_test/unit-prices/preview"); expect(body.get("focal_retailer")).toBe("ours");
  expect(body.get("as_of")).toBe("2026-10-21"); expect(body.get("max_age_days")).toBe("7");
  expect((body.get("file") as File).name).toBe("offers.csv");
});

it("clears review and export after a scope change", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<UnitPrices projectId="project_test" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Compare observed offers" }));
  expect(await screen.findByRole("button", { name: "Export unit-price audit CSV" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Maximum observation age (days)"), { target: { value: "0" } });
  expect(screen.queryByRole("button", { name: "Export unit-price audit CSV" })).toBeNull();
  expect(screen.queryByText(/offers qualify/)).toBeNull();
});

it("bounds age, file size, identifiers and cancels a file without a request", () => {
  render(<UnitPrices projectId="project_test" />, { wrapper }); fill();
  const button = screen.getByRole("button", { name: "Compare observed offers" }) as HTMLButtonElement;
  for (const age of ["-1", "366", "1.5", ""]) {
    fireEvent.change(screen.getByLabelText("Maximum observation age (days)"), { target: { value: age } });
    expect(button.disabled).toBe(true);
  }
  for (const age of ["0", "365"]) {
    fireEvent.change(screen.getByLabelText("Maximum observation age (days)"), { target: { value: age } }); expect(button.disabled).toBe(false);
  }
  fill(new File([new Uint8Array(2 * 1024 * 1024)], "limit.csv")); expect(button.disabled).toBe(false);
  fill(new File([new Uint8Array(2 * 1024 * 1024 + 1)], "large.csv")); expect(button.disabled).toBe(true);
  expect(screen.getByRole("alert").textContent).toContain("2 MB");
  fill(); expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.change(screen.getByLabelText("Focal retailer ID"), { target: { value: " ours" } }); expect(button.disabled).toBe(true);
  fill(); fireEvent.change(screen.getByLabelText("Observed offers CSV"), { target: { files: [] } }); expect(button.disabled).toBe(true);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("locks input during a request and recovers from network failure", async () => {
  let reject!: (error: Error) => void;
  fetchMock.mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  render(<UnitPrices projectId="project_test" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Compare observed offers" }));
  await waitFor(() => expect((screen.getByLabelText("Observed offers CSV") as HTMLInputElement).disabled).toBe(true));
  for (const label of ["Focal retailer ID", "As-of date", "Maximum observation age (days)"]) expect((screen.getByLabelText(label) as HTMLInputElement).disabled).toBe(true);
  reject(new Error("Connection lost")); expect((await screen.findByRole("alert")).textContent).toContain("Can't reach TwinStore");
  expect((screen.getByLabelText("Observed offers CSV") as HTMLInputElement).disabled).toBe(false);
  expect(screen.queryByRole("button", { name: "Export unit-price audit CSV" })).toBeNull();
});

it("retains tiny signed gaps as text and explains excluded rows", async () => {
  const data = report(); data.rows[0]!.flags = ["conditional_offer", "future"];
  data.comparisons[0]!.gap_minor = "-1.234e-12"; data.comparisons[0]!.relation = "below";
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(data)));
  render(<UnitPrices projectId="project_test" />, { wrapper }); fill(); fireEvent.click(screen.getByRole("button", { name: "Compare observed offers" }));
  expect(await screen.findByText("-1.234e-12")).toBeTruthy();
  expect(screen.getByText("below")).toBeTruthy(); expect(screen.getByText("Conditional / member offer; Future observation")).toBeTruthy();
});

it("discards late results when switching the keyed project view", async () => {
  let finish!: (response: Response) => void; fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<UnitPrices key="a" projectId="a" />, { wrapper }); fill();
  fireEvent.click(screen.getByRole("button", { name: "Compare observed offers" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce()); view.rerender(<UnitPrices key="b" projectId="b" />);
  finish(new Response(JSON.stringify(report())));
  await waitFor(() => expect((screen.getByLabelText("Observed offers CSV") as HTMLInputElement).disabled).toBe(false));
  expect(screen.queryByText(/offers qualify/)).toBeNull();
  expect((screen.getByLabelText("Focal retailer ID") as HTMLInputElement).value).toBe("");
});

function downloads() {
  const createURL = vi.fn(() => "blob:offers"); const revokeURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: revokeURL }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  return { createURL, revokeURL, click };
}

it("exports the reviewed bytes and scope with source hash and cleans download URLs", async () => {
  const { click, revokeURL } = downloads(); fetchMock.mockResolvedValueOnce(new Response("headers"));
  render(<UnitPrices projectId="project_test" />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Download offer template" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
  expect((click.mock.contexts[0] as HTMLAnchorElement).download).toBe("offer-template.csv");
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockResolvedValueOnce(new Response("audit"));
  fill(); fireEvent.click(screen.getByRole("button", { name: "Compare observed offers" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export unit-price audit CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(2));
  const [url, init] = fetchMock.mock.calls[2]!; const body = init?.body as FormData;
  expect(url).toContain("/unit-prices/export.csv"); expect(body.get("source_sha256")).toBe("a".repeat(64));
  expect(body.get("as_of")).toBe("2026-10-21"); expect(body.get("focal_retailer")).toBe("ours"); expect(body.get("max_age_days")).toBe("7");
  expect((body.get("file") as File).name).toBe("offers.csv");
  expect((click.mock.contexts[1] as HTMLAnchorElement).download).toBe("unit-price-audit.csv");
  await waitFor(() => expect(revokeURL).toHaveBeenCalledTimes(2));
});

it("does not download an export that arrives after unmount", async () => {
  const { click } = downloads(); let finish!: (response: Response) => void;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<UnitPrices projectId="a" />, { wrapper }); fill(); fireEvent.click(screen.getByRole("button", { name: "Compare observed offers" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export unit-price audit CSV" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const pending = qc.getMutationCache().getAll().find((m) => m.state.status === "pending")!;
  view.unmount(); finish(new Response("audit"));
  await waitFor(() => expect(pending.state.status).toBe("success")); expect(click).not.toHaveBeenCalled();
});

it("surfaces a stale-source export failure and clears it on new input", async () => {
  const { click } = downloads();
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Offer source changed" }), { status: 409 }));
  render(<UnitPrices projectId="project_test" />, { wrapper }); fill(); fireEvent.click(screen.getByRole("button", { name: "Compare observed offers" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export unit-price audit CSV" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Offer source changed"); expect(click).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Observed offers CSV"), { target: { files: [new File(["changed"], "changed.csv")] } });
  expect(screen.queryByRole("alert")).toBeNull(); expect(screen.queryByText(/offers qualify/)).toBeNull();
});
