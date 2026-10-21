// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ProtocolPlan, ProtocolView } from "@/shared/api/protocols";
import { Protocols } from "../Protocols";

const ID = `protocol_${"a".repeat(32)}`;
const PLAN: ProtocolPlan = { title: "Shelf study", evidence_type: "synthetic", question: "Hypothesis", population: "Saved cohort", design: "Paired design", primary_outcome: "Any purchase", analysis_unit: "Shopper", planned_sample_size: 60, exclusions_and_missing: "No imputation", stopping_rule: "Fixed sample", analysis_plan: "Paired contrasts" };
let current: ProtocolView | undefined; let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
function view(plan = PLAN): ProtocolView {
  return { ledger: { format_version: "protocol-ledger-v1", project_id: "project_test", protocol_id: ID,
    revisions: [{ revision: 1, recorded_at: "2026-10-21T00:00:00Z", reason: "Initial plan", data_stage: "not_collected", plan, previous_sha256: null, sha256: "a".repeat(64) }] },
    reviews: [{ revision: 1, changes: [{ field: "planned_sample_size", before: null, after: plan.planned_sample_size }] }],
    head_sha256: "a".repeat(64), changed_from_original: [], planned_sample_delta: 0, revisions_with_results_seen: 0, notes: ["Offline fixture, not external preregistration."] };
}
function listing() { return { protocols: current ? [{ protocol_id: ID, title: current.ledger.revisions[current.ledger.revisions.length - 1]!.plan.title, revision: current.ledger.revisions.length, data_stage: current.ledger.revisions[current.ledger.revisions.length - 1]!.data_stage, evidence_type: "synthetic", updated_at: "2026-10-21T00:00:00Z" }] : [], unavailable_ids: [] }; }
function response(value: unknown) { return new Response(JSON.stringify(value)); }
async function normalFetch(url: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const path = String(url);
  if (init?.method === "POST") {
    const req = JSON.parse(String(init.body)) as { plan: ProtocolPlan; data_stage: "not_collected"; reason?: string };
    if (!path.endsWith("/amendments")) current = view(req.plan);
    else {
      const previous = current!.ledger.revisions[0]!;
      current = { ...current!, ledger: { ...current!.ledger, revisions: [previous, { ...previous, revision: 2, plan: req.plan, reason: req.reason!, previous_sha256: previous.sha256, sha256: "b".repeat(64) }] },
        reviews: [...current!.reviews, { revision: 2, changes: [{ field: "planned_sample_size", before: 60, after: req.plan.planned_sample_size }] }],
        head_sha256: "b".repeat(64), changed_from_original: ["planned_sample_size"], planned_sample_delta: req.plan.planned_sample_size - 60 };
    }
    return response(current);
  }
  if (path.includes("export.json") || path.includes("changes.csv")) return new Response("export fixture");
  return response(path.endsWith("/protocols") ? listing() : current);
}
beforeEach(() => {
  current = undefined; qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  fetchMock.mockImplementation(normalFetch); vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
function fill(declareStage = true) {
  const fields = { "Protocol title": "Shelf study", "Research question / hypothesis": "Hypothesis", "Population and sampling": "Saved cohort", "Design and assignment": "Paired design", "Primary outcome and window": "Any purchase", "Independent analysis unit": "Shopper", "Exclusions and missing data": "No imputation", "Stopping and interim review rule": "Fixed sample", "Analysis and multiplicity plan": "Paired contrasts", "Planned independent units": "60" };
  for (const [label, value] of Object.entries(fields)) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  if (declareStage) fireEvent.change(screen.getByLabelText("Declared data stage"), { target: { value: "not_collected" } });
}
async function openSaved() {
  current = view(); render(<Protocols projectId="project_test" />, { wrapper });
  fireEvent.click(await screen.findByRole("button", { name: /Shelf study · r1/ }));
  await screen.findByRole("button", { name: "Record amendment" });
}

it("records an explicit complete original plan through the API and shows the saved history", async () => {
  render(<Protocols projectId="project_test" />, { wrapper }); fireEvent.click(screen.getByRole("button", { name: "New protocol" }));
  expect((screen.getByRole("button", { name: "Record original plan" }) as HTMLButtonElement).disabled).toBe(true);
  fill(); fireEvent.click(screen.getByRole("button", { name: "Record original plan" }));
  expect(await screen.findByRole("button", { name: "Record amendment" })).toBeTruthy();
  const [url, init] = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!;
  const req = JSON.parse(String(init?.body)) as { plan: ProtocolPlan; request_id: string; data_stage: string };
  expect(url).toContain("/project_test/protocols"); expect(req.plan).toEqual(PLAN); expect(req.request_id).toMatch(/^[0-9a-f]{32}$/);
  expect(req.data_stage).toBe("not_collected"); expect(screen.getByText(/Original declared stage: Data not collected/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Export saved history JSON" })).toBeTruthy();
});

it("requires a changed plan and reason, then submits the viewed head and renders the amendment", async () => {
  await openSaved(); const button = screen.getByRole("button", { name: "Record amendment" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Planned independent units"), { target: { value: "80" } }); expect(button.disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Export saved changes CSV" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Amendment reason"), { target: { value: "Recruitment change" } }); fireEvent.click(button);
  expect(await screen.findByText(/Planned-unit change from original: 20/)).toBeTruthy();
  const [, init] = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/amendments"))!;
  expect(JSON.parse(String(init?.body))).toMatchObject({ expected_head: "a".repeat(64), reason: "Recruitment change", plan: { planned_sample_size: 80 } });
  expect((screen.getByLabelText("Amendment reason") as HTMLTextAreaElement).value).toBe("");
});

function later(base: ProtocolView, revision: number, count: number): ProtocolView {
  const last = base.ledger.revisions[base.ledger.revisions.length - 1]!;
  return { ...base, ledger: { ...base.ledger, revisions: [...base.ledger.revisions, { ...last, revision, plan: { ...last.plan, planned_sample_size: count }, reason: "Changed target", previous_sha256: last.sha256, sha256: String(revision).repeat(64) }] },
    reviews: [...base.reviews, { revision, changes: [{ field: "planned_sample_size", before: last.plan.planned_sample_size, after: count }] }],
    head_sha256: String(revision).repeat(64), planned_sample_delta: count - 60, changed_from_original: ["planned_sample_size"] };
}

it("does not replace a newly loaded revision with an older delayed save response", async () => {
  await openSaved(); const second = later(current!, 2, 80); const third = later(second, 3, 100);
  let slowReads = false;
  let finish!: (response: Response) => void;
  fetchMock.mockImplementation((url, init) => {
    if (init?.method === "POST") return new Promise((resolve) => { finish = resolve; });
    if (slowReads && String(url).endsWith(ID)) return new Promise((resolve) => setTimeout(() => resolve(response(current)), 30));
    return normalFetch(url, init);
  });
  fireEvent.change(screen.getByLabelText("Planned independent units"), { target: { value: "80" } });
  fireEvent.change(screen.getByLabelText("Amendment reason"), { target: { value: "Change" } });
  fireEvent.click(screen.getByRole("button", { name: "Record amendment" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  current = third;
  fireEvent.click(screen.getByRole("button", { name: "Reload saved version (discard draft)" }));
  expect(await screen.findByText("Amend saved protocol · revision 3")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Protocol title"), { target: { value: "Unsubmitted follow-up" } });
  const pending = qc.getMutationCache().getAll().find((m) => m.state.status === "pending")!;
  slowReads = true; finish(response(second)); await waitFor(() => expect(pending.state.status).toBe("success"));
  expect(screen.getByText("Amend saved protocol · revision 3")).toBeTruthy();
  expect((screen.getByLabelText("Planned independent units") as HTMLInputElement).value).toBe("100");
  expect((screen.getByLabelText("Protocol title") as HTMLInputElement).value).toBe("Unsubmitted follow-up");
});

it("bounds empty, zero, negative, fractional and excessive sample targets", () => {
  render(<Protocols projectId="project_test" />, { wrapper }); fireEvent.click(screen.getByRole("button", { name: "New protocol" })); fill();
  const button = screen.getByRole("button", { name: "Record original plan" }) as HTMLButtonElement;
  for (const value of ["", "0", "-1", "1.5", "1000001"]) {
    fireEvent.change(screen.getByLabelText("Planned independent units"), { target: { value } }); expect(button.disabled).toBe(true);
  }
  for (const value of ["1", "1000000"]) {
    fireEvent.change(screen.getByLabelText("Planned independent units"), { target: { value } }); expect(button.disabled).toBe(false);
  }
  fireEvent.change(screen.getByLabelText("Analysis and multiplicity plan"), { target: { value: " \n" } }); expect(button.disabled).toBe(true);
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
});

it("locks inputs during a save and retains the same creation ID for an uncertain retry", async () => {
  let reject!: (error: Error) => void;
  fetchMock.mockImplementation((url, init) => init?.method === "POST" ? new Promise((_resolve, fail) => { reject = fail; }) : normalFetch(url, init));
  render(<Protocols projectId="project_test" />, { wrapper }); fireEvent.click(screen.getByRole("button", { name: "New protocol" })); fill();
  fireEvent.click(screen.getByRole("button", { name: "Record original plan" }));
  await waitFor(() => expect(screen.getByLabelText("Protocol title").closest("fieldset")?.disabled).toBe(true));
  const first = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")![1]!.body;
  reject(new Error("Connection lost")); expect((await screen.findByRole("alert")).textContent).toContain("Connection lost");
  fetchMock.mockImplementation(normalFetch); fireEvent.click(screen.getByRole("button", { name: "Record original plan" }));
  await screen.findByRole("button", { name: "Record amendment" });
  const bodies = fetchMock.mock.calls.filter(([, init]) => init?.method === "POST").map(([, init]) => init!.body);
  expect(bodies).toEqual([first, first]);
});

it("keeps a conflicting draft and requires an explicit reload instead of overwriting", async () => {
  await openSaved();
  fetchMock.mockImplementation((url, init) => init?.method === "POST" ? Promise.resolve(new Response(JSON.stringify({ detail: "Protocol changed in another session" }), { status: 409 })) : normalFetch(url, init));
  fireEvent.change(screen.getByLabelText("Planned independent units"), { target: { value: "80" } });
  fireEvent.change(screen.getByLabelText("Amendment reason"), { target: { value: "Change" } }); fireEvent.click(screen.getByRole("button", { name: "Record amendment" }));
  expect((await screen.findByRole("alert")).textContent).toContain("changed in another session");
  expect((screen.getByLabelText("Planned independent units") as HTMLInputElement).value).toBe("80");
  current = later(current!, 2, 90); fireEvent.click(screen.getByRole("button", { name: "Reload saved version (discard draft)" }));
  await screen.findByText("Amend saved protocol · revision 2");
  expect((screen.getByLabelText("Planned independent units") as HTMLInputElement).value).toBe("90");
});

it("does not switch selection when an abandoned create response arrives", async () => {
  let finish!: (response: Response) => void;
  fetchMock.mockImplementation((url, init) => init?.method === "POST" ? new Promise((resolve) => { finish = resolve; }) : normalFetch(url, init));
  render(<Protocols projectId="project_test" />, { wrapper }); fireEvent.click(screen.getByRole("button", { name: "New protocol" })); fill();
  fireEvent.click(screen.getByRole("button", { name: "Record original plan" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  const pending = qc.getMutationCache().getAll().find((m) => m.state.status === "pending")!;
  fireEvent.click(screen.getByRole("button", { name: "New protocol" }));
  current = view(); finish(response(current)); await waitFor(() => expect(pending.state.status).toBe("success"));
  expect(screen.getByRole("button", { name: "Record original plan" })).toBeTruthy();
  expect((screen.getByLabelText("Protocol title") as HTMLInputElement).value).toBe("");
});

function downloads() {
  const createURL = vi.fn(() => "blob:protocol"); const revokeURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: revokeURL }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  return { click, revokeURL };
}

it("exports only the saved head in both formats and cleans object URLs", async () => {
  const { click, revokeURL } = downloads(); await openSaved();
  fireEvent.click(screen.getByRole("button", { name: "Export saved history JSON" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole("button", { name: "Export saved changes CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(2));
  const urls = fetchMock.mock.calls.map(([url]) => String(url));
  expect(urls).toContain(`http://localhost:8000/api/projects/project_test/protocols/${ID}/export.json?head=${"a".repeat(64)}`);
  expect(urls).toContain(`http://localhost:8000/api/projects/project_test/protocols/${ID}/changes.csv?head=${"a".repeat(64)}`);
  await waitFor(() => expect(revokeURL).toHaveBeenCalledTimes(2));
});

it("does not download a late export after project navigation", async () => {
  const { click } = downloads(); current = view();
  const rendered = render(<Protocols key="a" projectId="a" />, { wrapper });
  fireEvent.click(await screen.findByRole("button", { name: /Shelf study · r1/ })); await screen.findByRole("button", { name: "Export saved history JSON" });
  let finish!: (response: Response) => void;
  fetchMock.mockImplementation((url, init) => String(url).includes("export.json") ? new Promise((resolve) => { finish = resolve; }) : normalFetch(url, init));
  fireEvent.click(screen.getByRole("button", { name: "Export saved history JSON" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  const pending = qc.getMutationCache().getAll().find((m) => m.state.status === "pending")!;
  rendered.rerender(<Protocols key="b" projectId="b" />); finish(new Response("export"));
  await waitFor(() => expect(pending.state.status).toBe("success")); expect(click).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Record amendment" })).toBeNull();
});

it("explains incomparable sample counts and disables backward data stages", async () => {
  current = later(view(), 2, 80); current.planned_sample_delta = null;
  current.ledger.revisions[1]!.plan.analysis_unit = "Store"; current.ledger.revisions[1]!.data_stage = "results_seen";
  render(<Protocols projectId="project_test" />, { wrapper });
  fireEvent.click(await screen.findByRole("button", { name: /Shelf study · r2/ }));
  expect(await screen.findByText(/sample delta is unavailable because/)).toBeTruthy();
  expect(screen.getByText(/Planned-unit change from original: Unavailable/)).toBeTruthy();
  const select = screen.getByLabelText("Declared data stage") as HTMLSelectElement;
  expect(select.options[1]!.disabled).toBe(true); expect(select.options[2]!.disabled).toBe(true);
});

it("reports unavailable histories and failed exports without producing a download", async () => {
  const { click } = downloads(); current = view();
  fetchMock.mockImplementation((url, init) => String(url).endsWith("/protocols") ? Promise.resolve(response({ ...listing(), unavailable_ids: ["protocol_broken"] })) : normalFetch(url, init));
  render(<Protocols projectId="project_test" />, { wrapper });
  expect((await screen.findByRole("alert")).textContent).toContain("protocol_broken");
  fireEvent.click(await screen.findByRole("button", { name: /Shelf study · r1/ })); await screen.findByRole("button", { name: "Export saved history JSON" });
  fetchMock.mockImplementation((url, init) => String(url).includes("export.json") ? Promise.resolve(new Response(JSON.stringify({ detail: "Protocol changed since the displayed version" }), { status: 409 })) : normalFetch(url, init));
  fireEvent.click(screen.getByRole("button", { name: "Export saved history JSON" }));
  await waitFor(() => expect(screen.getAllByRole("alert").some((e) => e.textContent?.includes("changed since"))).toBe(true));
  expect(click).not.toHaveBeenCalled();
});

it("requires an explicit data-stage declaration instead of assuming unseen outcomes", () => {
  render(<Protocols projectId="project_test" />, { wrapper }); fireEvent.click(screen.getByRole("button", { name: "New protocol" })); fill(false);
  const button = screen.getByRole("button", { name: "Record original plan" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Declared data stage"), { target: { value: "results_seen" } }); expect(button.disabled).toBe(false);
});
