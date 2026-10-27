// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PriceCheckReport } from "@/shared/api/priceChecks";
import { PriceChecks } from "../PriceChecks";

let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => { qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } }); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
function report(): PriceCheckReport {
  const label = { check_id: "a", sku: "tea", pack_reference: "box", checked_on: "2026-10-21", currency: "USD", price_minor: 200, terms: "public" as const };
  return { method: "observed-price-checks-v1", scope: { store_ref: "ours", audit_date: "2026-10-21" }, source_sha256: "a".repeat(64), notes: ["Offline fixture"], label_count: 1, checkout_count: 1, excluded_count: 0,
    rows: [{ check_id: "a", label, checkout: { ...label, price_minor: 190 }, difference_minor: -10, relation: "checkout_lower", flags: [] }],
    totals: [{ currency: "USD", comparable: 1, higher: 0, lower: 1, equal: 0, positive_difference_minor: 0, negative_difference_minor: -10, net_difference_minor: -10 }] };
}
function fill() {
  fireEvent.change(screen.getByLabelText("Store reference"), { target: { value: "ours" } });
  fireEvent.change(screen.getByLabelText("Audit date"), { target: { value: "2026-10-21" } });
  for (const name of ["Label", "Checkout"]) fireEvent.change(screen.getByLabelText(`${name} observations CSV`), { target: { files: [new File([name], `${name}.csv`)] } });
}

it("connects two exact input files and scope to the API and displays signed differences", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<PriceChecks projectId="p" />, { wrapper });
  const button = screen.getByRole("button", { name: "Review price checks" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); fill(); fireEvent.click(button);
  const summary = await screen.findByText(/1 \/ 1 checks comparable/);
  expect(document.activeElement).toBe(summary);  // the result opens below the button; focus takes the reader there
  expect(screen.getByText("Checkout lower")).toBeTruthy(); expect(screen.getAllByText("-10")).toHaveLength(3);
  const [url, init] = fetchMock.mock.calls[0]!; const body = init?.body as FormData;
  expect(url).toContain("/p/price-checks/preview"); expect(body.get("store_ref")).toBe("ours"); expect(body.get("audit_date")).toBe("2026-10-21");
  expect((body.get("labels") as File).name).toBe("Label.csv"); expect((body.get("checkouts") as File).name).toBe("Checkout.csv");
});

it("keeps each file error until that file is corrected", () => {
  render(<PriceChecks projectId="p" />, { wrapper }); fill();
  const big = new File([new Uint8Array(2 * 1024 * 1024 + 1)], "large.csv");
  fireEvent.change(screen.getByLabelText("Label observations CSV"), { target: { files: [big] } });
  expect(screen.getByRole("alert").textContent).toContain("Label CSV exceeds 2 MB");
  fireEvent.change(screen.getByLabelText("Checkout observations CSV"), { target: { files: [new File(["corrected"], "c.csv")] } });
  expect(screen.getByRole("alert").textContent).toContain("Label CSV exceeds 2 MB");
  expect((screen.getByRole("button", { name: "Review price checks" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Label observations CSV"), { target: { files: [new File(["ok"], "l.csv")] } });
  expect(screen.queryByRole("alert")).toBeNull(); expect(fetchMock).not.toHaveBeenCalled();
});

it("accepts the byte limit, rejects larger files and requires both files and complete scope", () => {
  render(<PriceChecks projectId="p" />, { wrapper }); fill();
  const button = screen.getByRole("button", { name: "Review price checks" }) as HTMLButtonElement;
  for (const name of ["Label", "Checkout"]) {
    fireEvent.change(screen.getByLabelText(`${name} observations CSV`), { target: { files: [new File([new Uint8Array(2 * 1024 * 1024)], "limit.csv")] } });
    expect(button.disabled).toBe(false);
    fireEvent.change(screen.getByLabelText(`${name} observations CSV`), { target: { files: [] } }); expect(button.disabled).toBe(true); fill();
  }
  for (const store of ["", " ours", "x".repeat(121)]) { fireEvent.change(screen.getByLabelText("Store reference"), { target: { value: store } }); expect(button.disabled).toBe(true); }
  fill(); fireEvent.change(screen.getByLabelText("Audit date"), { target: { value: "" } }); expect(button.disabled).toBe(true);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("clears stale output on either file or scope change", async () => {
  fetchMock.mockImplementation(async () => new Response(JSON.stringify(report())));
  render(<PriceChecks projectId="p" />, { wrapper }); fill();
  for (const label of ["Store reference", "Audit date", "Label observations CSV", "Checkout observations CSV"]) {
    fireEvent.click(screen.getByRole("button", { name: "Review price checks" })); await screen.findByRole("button", { name: "Export price-check audit CSV" });
    fireEvent.change(screen.getByLabelText(label), { target: label.endsWith("CSV") ? { files: [new File(["new"], "new.csv")] } : { value: label === "Audit date" ? "2026-10-20" : "new-store" } });
    expect(screen.queryByRole("button", { name: "Export price-check audit CSV" })).toBeNull(); expect(screen.queryByText(/checks comparable/)).toBeNull();
  }
});

it("shows unavailable observations and every exclusion without inventing zero totals", async () => {
  const result = report(); result.excluded_count = 1; result.checkout_count = 0; result.totals = [];
  result.rows[0] = { ...result.rows[0]!, checkout: null, difference_minor: null, relation: "unavailable", flags: ["missing_checkout", "outside_audit_date", "terms_unverified"] };
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(result)));
  render(<PriceChecks projectId="p" />, { wrapper }); fill(); fireEvent.click(screen.getByRole("button", { name: "Review price checks" }));
  expect(await screen.findByText(/No comparable pairs/)).toBeTruthy(); expect(screen.getByText("Missing observation")).toBeTruthy();
  expect(screen.getByText("Missing checkout; Outside audit date; Conditional or unknown terms")).toBeTruthy();
});

it("locks inputs while pending and recovers from network failure without export", async () => {
  let fail!: (error: Error) => void; fetchMock.mockReturnValueOnce(new Promise((_resolve, reject) => { fail = reject; }));
  render(<PriceChecks projectId="p" />, { wrapper }); fill(); fireEvent.click(screen.getByRole("button", { name: "Review price checks" }));
  await waitFor(() => expect((screen.getByLabelText("Store reference") as HTMLInputElement).disabled).toBe(true));
  for (const label of ["Audit date", "Label observations CSV", "Checkout observations CSV"]) expect((screen.getByLabelText(label) as HTMLInputElement).disabled).toBe(true);
  fail(new Error("Connection lost")); expect((await screen.findByRole("alert")).textContent).toContain("Can't reach TwinStore");
  expect((screen.getByLabelText("Store reference") as HTMLInputElement).disabled).toBe(false);
  expect(screen.queryByRole("button", { name: "Export price-check audit CSV" })).toBeNull();
});

function downloads() {
  const createURL = vi.fn(() => "blob:checks"); const revokeURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: revokeURL }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  return { click, revokeURL };
}

it("downloads template and exports the reviewed files, scope and digest", async () => {
  const { click, revokeURL } = downloads(); fetchMock.mockResolvedValueOnce(new Response("header"));
  render(<PriceChecks projectId="p" />, { wrapper }); fireEvent.click(screen.getByRole("button", { name: "Download price-check template" }));
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockResolvedValueOnce(new Response("audit"));
  fill(); fireEvent.click(screen.getByRole("button", { name: "Review price checks" })); fireEvent.click(await screen.findByRole("button", { name: "Export price-check audit CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(2));
  const [url, init] = fetchMock.mock.calls[2]!; const body = init?.body as FormData;
  expect(url).toContain("/price-checks/export.csv"); expect(body.get("source_sha256")).toBe("a".repeat(64));
  expect(body.get("store_ref")).toBe("ours"); expect(body.get("audit_date")).toBe("2026-10-21");
  expect((body.get("labels") as File).name).toBe("Label.csv"); expect((body.get("checkouts") as File).name).toBe("Checkout.csv");
  expect((click.mock.contexts[1] as HTMLAnchorElement).download).toBe("price-check-audit.csv");
  await waitFor(() => expect(revokeURL).toHaveBeenCalledTimes(2));
});

it("does not download an export arriving after navigation", async () => {
  const { click } = downloads(); let finish!: (response: Response) => void;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<PriceChecks key="a" projectId="a" />, { wrapper }); fill(); fireEvent.click(screen.getByRole("button", { name: "Review price checks" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export price-check audit CSV" })); await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const pending = qc.getMutationCache().getAll().find((m) => m.state.status === "pending")!;
  view.rerender(<PriceChecks key="b" projectId="b" />); finish(new Response("audit"));
  await waitFor(() => expect(pending.state.status).toBe("success")); expect(click).not.toHaveBeenCalled();
  expect(screen.queryByText(/checks comparable/)).toBeNull(); expect((screen.getByLabelText("Store reference") as HTMLInputElement).value).toBe("");
});

it("does not show late preview results in a new project", async () => {
  let finish!: (response: Response) => void; fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<PriceChecks key="a" projectId="a" />, { wrapper }); fill(); fireEvent.click(screen.getByRole("button", { name: "Review price checks" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce()); const pending = qc.getMutationCache().getAll()[0]!;
  view.rerender(<PriceChecks key="b" projectId="b" />); finish(new Response(JSON.stringify(report())));
  await waitFor(() => expect(pending.state.status).toBe("success")); expect(screen.queryByText(/checks comparable/)).toBeNull();
});

it("reports a stale export or template failure without a download", async () => {
  const { click } = downloads(); fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Project not found" }), { status: 404 }));
  render(<PriceChecks projectId="p" />, { wrapper }); fireEvent.click(screen.getByRole("button", { name: "Download price-check template" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Project not found");
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Sources or scope changed" }), { status: 409 }));
  fill(); fireEvent.click(screen.getByRole("button", { name: "Review price checks" })); fireEvent.click(await screen.findByRole("button", { name: "Export price-check audit CSV" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Sources or scope changed"); expect(click).not.toHaveBeenCalled();
});

it("says what the review still needs while it cannot run, including spaces around the store reference", () => {
  render(<PriceChecks projectId="p" />, { wrapper });
  const needs = /To review, fill in the store reference/;
  expect(screen.getByText(needs)).toBeTruthy();
  fill();
  expect(screen.queryByText(needs)).toBeNull();
  fireEvent.change(screen.getByLabelText("Store reference"), { target: { value: " ours" } });
  expect(screen.getByText(needs)).toBeTruthy();
});
