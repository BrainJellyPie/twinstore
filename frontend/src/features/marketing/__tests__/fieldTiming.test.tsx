// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { PilotTimingReport } from "@/shared/api/fieldTiming";
import { PilotTiming } from "../PilotTiming";

let qc: QueryClient;
const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => { qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => { cleanup(); qc.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });
function wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={qc}>{children}</QueryClientProvider>; }
const props = { projectId: "project_test", pilotId: "pilot_test", revision: 2, eligible: true };
function report(complete = true): PilotTimingReport {
  return { method: "assigned-encounter-time-v1", pilot_id: "pilot_test", revision: 2, source_sha256: "abc", source_rows: 40,
    complete, planned: 40, timed: complete ? 40 : 20,
    a: { arm: "A", planned: 20, timed: 20, mean_seconds: complete ? 1.001 : null, max_seconds: complete ? 1.001 : null },
    b: { arm: "B", planned: 20, timed: complete ? 20 : 0, mean_seconds: complete ? 2.001 : null, max_seconds: complete ? 2.001 : null },
    difference_seconds: complete ? 1 : null, blocks: [{ staff_id: "s1", shift_id: "am", planned: 40, timed: complete ? 40 : 20 }], rows: [], notes: ["Offline fixture."] };
}
function choose(file = new File(["offline fixture"], "time.csv", { type: "text/csv" })) {
  fireEvent.change(screen.getByLabelText("Staff time CSV"), { target: { files: [file] } }); return file;
}

it("gates incomplete pilots and requires an explicit source file", () => {
  const view = render(<PilotTiming {...props} eligible={false} />, { wrapper });
  expect(screen.queryByLabelText("Staff time CSV")).toBeNull();
  expect(screen.getByText(/do not close early/)).toBeTruthy();
  view.rerender(<PilotTiming {...props} />);
  expect((screen.getByRole("button", { name: "Review staff time" }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("submits a revision-bound file, shows complete evidence, and clears it when the file changes", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())));
  render(<PilotTiming {...props} />, { wrapper }); choose();
  fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  expect(await screen.findByText(/Timed 40 of 40/)).toBeTruthy();
  const [url, init] = fetchMock.mock.calls[0]!;
  expect(url).toContain("/project_test/staff-pilots/pilot_test/timing/preview");
  const body = init?.body as FormData;
  expect(body.get("revision")).toBe("2"); expect((body.get("file") as File).name).toBe("time.csv");
  expect(screen.getByText("B-minus-A mean time: 1 seconds.")).toBeTruthy();
  choose(new File(["different"], "other.csv"));
  expect(screen.queryByText(/Timed 40 of 40/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Export staff time audit CSV" })).toBeNull();
});

it("shows incomplete coverage without presenting a partial mean comparison", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report(false))));
  render(<PilotTiming {...props} />, { wrapper }); choose();
  fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  expect(await screen.findByText(/Timed 20 of 40/)).toBeTruthy();
  expect(screen.getAllByText("Withheld until complete")).toHaveLength(4);
  expect(screen.getByText(/Missing times remain unknown/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Export staff time audit CSV" })).toBeTruthy();
});

it("preserves small signed mean differences instead of displaying negative zero", async () => {
  const data = report(); data.difference_seconds = -0.00005; data.a.mean_seconds = 1.00005; data.b.mean_seconds = 1;
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(data)));
  render(<PilotTiming {...props} />, { wrapper }); choose();
  fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  expect(await screen.findByText("B-minus-A mean time: -0.00005 seconds.")).toBeTruthy();
});

it("enforces the byte boundary locally and handles cancelled selection", () => {
  render(<PilotTiming {...props} />, { wrapper });
  const review = screen.getByRole("button", { name: "Review staff time" }) as HTMLButtonElement;
  choose(new File([new Uint8Array(2 * 1024 * 1024)], "limit.csv")); expect(review.disabled).toBe(false);
  choose(new File([new Uint8Array(2 * 1024 * 1024 + 1)], "large.csv"));
  expect(review.disabled).toBe(true); expect(screen.getByRole("alert").textContent).toContain("2 MB");
  choose(); expect(screen.queryByRole("alert")).toBeNull(); expect(review.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Staff time CSV"), { target: { files: [] } }); expect(review.disabled).toBe(true);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("locks file changes during requests and recovers from server and network failures", async () => {
  let finish!: (response: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  render(<PilotTiming {...props} />, { wrapper }); choose();
  fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  await waitFor(() => expect((screen.getByLabelText("Staff time CSV") as HTMLInputElement).disabled).toBe(true));
  finish(new Response(JSON.stringify({ detail: "Reload the pilot" }), { status: 409 }));
  expect((await screen.findByRole("alert")).textContent).toContain("Reload the pilot");
  expect(screen.queryByRole("button", { name: "Export staff time audit CSV" })).toBeNull();
  expect((screen.getByLabelText("Staff time CSV") as HTMLInputElement).disabled).toBe(false);
  choose(); fetchMock.mockRejectedValueOnce(new Error("Connection lost"));
  fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Can't reach TwinStore");
});

it("does not show a late response after switching source or revision", async () => {
  let finish!: (response: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = render(<PilotTiming {...props} />, { wrapper }); choose();
  fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
  view.rerender(<PilotTiming {...props} revision={3} />);
  finish(new Response(JSON.stringify(report())));
  await waitFor(() => expect((screen.getByRole("button", { name: "Review staff time" }) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.queryByText(/Timed 40 of 40/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Export staff time audit CSV" })).toBeNull();
});

it("downloads the reviewed file and source revision and releases blob URLs", async () => {
  const createURL = vi.fn(() => "blob:timing"); const revokeURL = vi.fn();
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: createURL, revokeObjectURL: revokeURL }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  fetchMock.mockResolvedValueOnce(new Response("template,csv"));
  render(<PilotTiming {...props} />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Download staff time template" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
  expect(fetchMock.mock.calls[0]![0]).toContain("/timing/template.csv?revision=2");
  expect((click.mock.contexts[0] as HTMLAnchorElement).download).toBe("pilot_test-staff-time-template.csv");
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report()))).mockResolvedValueOnce(new Response("audit,csv"));
  choose(); fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export staff time audit CSV" }));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(2));
  const [url, init] = fetchMock.mock.calls[2]!;
  expect(url).toContain("/timing/export.csv"); expect((init?.body as FormData).get("revision")).toBe("2");
  expect(((init?.body as FormData).get("file") as File).name).toBe("time.csv");
  expect((click.mock.contexts[1] as HTMLAnchorElement).download).toBe("pilot_test-staff-time-r2.csv");
  await waitFor(() => expect(revokeURL).toHaveBeenCalledTimes(2));
});

it("surfaces export failures without silently replacing the source snapshot", async () => {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(report())))
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "The saved pilot changed" }), { status: 409 }));
  render(<PilotTiming {...props} />, { wrapper }); choose(); fireEvent.click(screen.getByRole("button", { name: "Review staff time" }));
  fireEvent.click(await screen.findByRole("button", { name: "Export staff time audit CSV" }));
  expect((await screen.findByRole("alert")).textContent).toContain("saved pilot changed");
  expect(screen.getByText(/locked revision 2/)).toBeTruthy();
});
