// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { OnlineRunNotice } from "../OnlineRunNotice";

const navigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
  useLocation: ({ select }: { select: (l: { pathname: string }) => string }) => select({ pathname: "/projects/p1" }),
}));
vi.mock("@/shared/queries/useProjects", () => ({ useProjects: () => ({ data: [] }) }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), listRuns: vi.fn() }));

const run = (status: online.OnlineRunStatus["status"]) =>
  ({ run_id: "r1", name: "Popup test", site_names: ["Shop", "Shop B"], status }) as online.OnlineRunStatus;

beforeEach(() => { useLocale.getState().setLocale("en"); window.history.replaceState(null, "", "/projects/p1"); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });

async function finish(status: online.OnlineRunStatus["status"]) {
  vi.mocked(online.listRuns).mockResolvedValue([run("running")]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OnlineRunNotice /></QueryClientProvider>);
  await waitFor(() => expect(online.listRuns).toHaveBeenCalled());
  vi.mocked(online.listRuns).mockResolvedValue([run(status)]);
  await act(async () => { await client.refetchQueries(); });
}

it("names a run that finished elsewhere and opens its report", async () => {
  await finish("completed");
  expect((await screen.findByRole("status")).textContent).toContain("Online run finished");
  expect(screen.getByText("Popup test")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Open the report" }));
  expect(navigate).toHaveBeenCalledWith({ to: "/online/$pid", params: { pid: "p1" }, search: { run: "r1" } });
  expect(screen.queryByRole("status")).toBeNull();
});

it("says so when a run fails", async () => {
  await finish("failed");
  expect((await screen.findByRole("status")).textContent).toContain("Online run failed");
});

it("stays quiet for the run whose report is already open, and for runs that were done before", async () => {
  window.history.replaceState(null, "", "/online/p1?run=r1");
  await finish("completed");
  expect(screen.queryByRole("status")).toBeNull();
  cleanup();
  window.history.replaceState(null, "", "/projects/p1");
  vi.mocked(online.listRuns).mockResolvedValue([run("completed")]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OnlineRunNotice /></QueryClientProvider>);
  await act(async () => { await client.refetchQueries(); });
  expect(screen.queryByRole("status")).toBeNull();
});
