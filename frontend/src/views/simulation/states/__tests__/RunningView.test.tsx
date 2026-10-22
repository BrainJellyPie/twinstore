// @vitest-environment jsdom
import { Component, type ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { RunningView } from "../RunningView";
import type { ViewCommon } from "../types";

vi.mock("@/shared/api/client", () => ({ getRunStatus: vi.fn() }));
vi.mock("@/features/store-viewer/hooks/useStoreAssets", () => ({ useStoreAssets: () => ({ minTime: 0, maxTime: 1 }) }));
vi.mock("@/features/playback/hooks/usePersonaData", () => ({ usePersonaData: () => ({ personaNames: {}, personaGenders: {} }) }));
vi.mock("@/views/simulation/ProjectShell", () => ({ ProjectShell: ({ centerSlot, sidePanelSlot }: { centerSlot: ReactNode; sidePanelSlot: ReactNode }) => <>{centerSlot}{sidePanelSlot}</> }));
vi.mock("@/views/simulation/SimulationLayout", () => ({ SimulationLayout: ({ overlay }: { overlay?: ReactNode }) => <div>{overlay}</div> }));
vi.mock("@/views/simulation/SidePanel", () => ({ SidePanel: ({ runStatus }: { runStatus?: api.RunStatus }) => <p data-testid="progress">{runStatus ? `${runStatus.completed_customers} done` : "no status"}</p> }));

class Boundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() { return this.state.error ? <p role="alert">{this.state.error.message}</p> : this.props.children; }
}

const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); vi.restoreAllMocks(); useLocale.getState().setLocale("en"); });
const running = (done: number): api.RunStatus => ({ status: "running", error: "", total_customers: 10, completed_customers: done });

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  const setup = { id: "layout", store: { id: "store" } } as unknown as ViewCommon["setup"];
  return render(<QueryClientProvider client={client}><Boundary>
    <RunningView pid="project" setupId="layout" runId="run" setup={setup} personas={[]} location="" layouts={[]} selectedSetupId="layout" onLayoutSelect={vi.fn()} onAddLayout={vi.fn()} />
  </Boundary></QueryClientProvider>);
}

it("keeps the last progress, says it is reconnecting and keeps polling after a failed status poll", async () => {
  useLocale.getState().setLocale("ko");
  vi.mocked(api.getRunStatus).mockResolvedValueOnce(running(3)).mockRejectedValueOnce(new Error("Network down")).mockResolvedValue(running(5));
  show();
  await waitFor(() => expect(screen.getByTestId("progress").textContent).toBe("3 done"));
  const note = await screen.findByRole("status", {}, { timeout: 3000 });
  expect(note.textContent).toBe(translate("ko", "reconnecting"));
  expect(screen.getByTestId("progress").textContent).toBe("3 done");
  expect(screen.queryByRole("alert")).toBeNull();
  await waitFor(() => expect(screen.getByTestId("progress").textContent).toBe("5 done"), { timeout: 3000 });
  expect(screen.queryByRole("status")).toBeNull();
}, 10_000);

it("still sends a failure before any status arrived to the error boundary", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.mocked(api.getRunStatus).mockRejectedValue(new Error("Run not found"));
  show();
  expect((await screen.findByRole("alert")).textContent).toBe("Run not found");
});
