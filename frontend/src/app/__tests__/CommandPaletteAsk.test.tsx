// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render as renderUi, screen, waitFor } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { queryKeys } from "@/shared/queries/keys";
import { CommandPalette } from "../CommandPalette";
import { useCommandPalette } from "../commandPalette";

const state = vi.hoisted(() => ({
  navigate: vi.fn(), pathname: "/projects/proj_cafe",
  projects: [{ project_id: "proj_cafe", name: "Café Étoile", store_type: "cafe", status: "Simulated" }],
}));
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => state.navigate, useLocation: () => ({ pathname: state.pathname }) }));
vi.mock("@/shared/queries/useProjects", () => ({ useProjects: () => ({ data: state.projects }) }));
vi.mock("../theme", () => ({ useTheme: () => ({ theme: "dark", setTheme: vi.fn() }) }));
vi.mock("../launcher", () => ({ useLauncher: () => false, quitLauncher: vi.fn() }));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), routeAssist: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof import("@/shared/api/online")>(), listRuns: vi.fn() }));
Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });

const queryClient = new QueryClient();
const render = (ui: ReactElement) => renderUi(ui, { wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider> });
const layout = (id: string, runId: string | null, updated_at = "2026-10-01"): api.SetupSummary => ({ id, name: id, status: runId ? "locked" : "draft",
  parentId: null, runId, memo: "", readiness: null, created_at: "2026-09-01", updated_at });
beforeEach(() => {
  useLocale.getState().setLocale("en"); useCommandPalette.setState({ open: true }); state.pathname = "/projects/proj_cafe";
  queryClient.setQueryData(queryKeys.setups("proj_cafe"), [layout("a", "run_a")]);
});
afterEach(() => {
  cleanup(); useCommandPalette.setState({ open: false }); useAssistStore.setState({ pending: null }); useSimulationStore.getState().reset();
  queryClient.clear(); vi.clearAllMocks();
});

function type(text: string) {
  render(<CommandPalette />);
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: text } });
  return input;
}

it.each([
  ["ab_test", "Would a 1+1 sign on cola sell more?", "/marketing/$pid"],
  ["conjoint", "Would people pay more for oat milk?", "/marketing/$pid"],
  ["concept_test", "Which of our two labels looks more premium?", "/marketing/$pid"],
  ["shelf_test", "Would the gold label stand out on the tea shelf?", "/marketing/$pid"],
  ["area", "We sit on a busy campus street", "/town/$pid"],
  ["run_question", "Why does the freezer sell so little?", "/projects/$pid"],
  ["layout_edit", "Put the cola at eye level now", "/projects/$pid"],
  ["find_shoppers", "Show me students who left empty-handed", "/projects/$pid"],
  ["optimize", "Optimize the layout for more impulse sales", "/projects/$pid"],
] as const)("routes a typed request to %s and hands the words to that page", async (destination, text, to) => {
  vi.mocked(api.routeAssist).mockResolvedValue({ destination, reason: "" });
  useSimulationStore.getState().setActiveTab("settings");
  const input = type(text);
  expect(screen.getAllByRole("option")[0]!.textContent).toContain(text);
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() => expect(state.navigate).toHaveBeenCalledWith({ to, params: { pid: "proj_cafe" } }));
  expect(api.routeAssist).toHaveBeenCalledWith({ text, has_run: true });
  expect(useAssistStore.getState().pending).toMatchObject({ projectId: "proj_cafe", destination, text });
  const tab = { run_question: "dashboard", find_shoppers: "shoppers" } as Record<string, string>;
  expect(useSimulationStore.getState().activeTab).toBe(tab[destination] ?? "settings");  // layout edits open Store
  expect(useCommandPalette.getState().open).toBe(false);
});

it("keeps the palette open with a hint when the request fits no tool", async () => {
  vi.mocked(api.routeAssist).mockResolvedValue({ destination: "none", reason: "" });
  const input = type("Order more paper towels tomorrow");
  fireEvent.keyDown(input, { key: "Enter" });
  expect(await screen.findByText(/TwinStore cannot set that up yet/)).toBeTruthy();
  expect(state.navigate).not.toHaveBeenCalled();
  expect(useAssistStore.getState().pending).toBeNull();
  expect(useCommandPalette.getState().open).toBe(true);
});

it("offers to ask only inside a store, for a sentence that names no command", () => {
  type("floor");
  expect(screen.queryByText("Ask TwinStore")).toBeNull();
  cleanup();
  useLocale.getState().setLocale("es");
  type("Proveedores de modelos");  // a three-word command name stays a command
  expect(screen.queryByText("Pedir a TwinStore")).toBeNull();
  expect(screen.getAllByRole("option")).toHaveLength(1);
  cleanup();
  state.pathname = "/projects/new";
  type("Would a 1+1 sign on cola sell more?");
  expect(screen.queryByText("Ask TwinStore")).toBeNull();
});

it("opens the most recent layout with a finished run before handing over a run question", async () => {
  vi.mocked(api.routeAssist).mockResolvedValue({ destination: "run_question", reason: "" });
  queryClient.setQueryData(queryKeys.setups("proj_cafe"), [layout("draft", null), layout("old", "run_old", "2026-10-02"), layout("recent", "run_new", "2026-10-09")]);
  useSimulationStore.getState().setSelectedSetupId("draft");
  fireEvent.keyDown(type("Why does the freezer sell so little?"), { key: "Enter" });
  await waitFor(() => expect(state.navigate).toHaveBeenCalledWith({ to: "/projects/$pid", params: { pid: "proj_cafe" } }));
  expect(useSimulationStore.getState().selectedSetupId).toBe("recent");
  expect(useAssistStore.getState().pending).toMatchObject({ destination: "run_question", text: "Why does the freezer sell so little?" });
  expect(useCommandPalette.getState().open).toBe(false);
});

it("keeps the viewed layout when it is showing a finished run", async () => {
  vi.mocked(api.routeAssist).mockResolvedValue({ destination: "run_question", reason: "" });
  queryClient.setQueryData(queryKeys.setups("proj_cafe"), [layout("draft", null), layout("recent", "run_new")]);
  useSimulationStore.getState().setSelectedSetupId("draft");
  useSimulationStore.getState().setViewRunId("preview_run");
  fireEvent.keyDown(type("Why does the freezer sell so little?"), { key: "Enter" });
  await waitFor(() => expect(state.navigate).toHaveBeenCalled());
  expect(useSimulationStore.getState().selectedSetupId).toBe("draft");
  expect(useSimulationStore.getState().viewRunId).toBe("preview_run");
});

it("keeps the palette open with a note when no layout has a finished run", async () => {
  useLocale.getState().setLocale("fr");
  vi.mocked(api.routeAssist).mockResolvedValue({ destination: "run_question", reason: "" });
  queryClient.setQueryData(queryKeys.setups("proj_cafe"), [layout("draft", null), layout("other", null)]);
  useSimulationStore.getState().setSelectedSetupId("draft");
  fireEvent.keyDown(type("Pourquoi le congélateur vend-il si peu ?"), { key: "Enter" });
  expect(await screen.findByText(translate("fr", "commandAskNoRun"))).toBeTruthy();
  expect(state.navigate).not.toHaveBeenCalled();
  expect(useAssistStore.getState().pending).toBeNull();
  expect(useSimulationStore.getState().selectedSetupId).toBe("draft");
  expect(useCommandPalette.getState().open).toBe(true);
});

const onlineRun = (run_id: string, status: online.OnlineRunStatus["status"], created_at: string) =>
  ({ run_id, status, created_at }) as online.OnlineRunStatus;

it("opens the latest finished online run before handing over a question about the web shop", async () => {
  vi.mocked(api.routeAssist).mockResolvedValue({ destination: "online_question", reason: "" });
  vi.mocked(online.listRuns).mockResolvedValue([
    onlineRun("orun_old", "completed", "2026-10-01T10:00:00"), onlineRun("orun_busy", "running", "2026-10-03T10:00:00"),
    onlineRun("orun_new", "completed", "2026-10-02T10:00:00"),
  ]);
  fireEvent.keyDown(type("Did the web shop's new checkout win?"), { key: "Enter" });
  await waitFor(() => expect(state.navigate).toHaveBeenCalledWith({ to: "/online/$pid", params: { pid: "proj_cafe" }, search: { run: "orun_new" } }));
  expect(useAssistStore.getState().pending).toMatchObject({ destination: "online_question", text: "Did the web shop's new checkout win?" });
});

it("keeps the palette open with a note when no online run has finished", async () => {
  vi.mocked(api.routeAssist).mockResolvedValue({ destination: "online_question", reason: "" });
  vi.mocked(online.listRuns).mockResolvedValue([onlineRun("orun_busy", "running", "2026-10-03T10:00:00")]);
  fireEvent.keyDown(type("Did the web shop's new checkout win?"), { key: "Enter" });
  expect(await screen.findByText(translate("en", "commandAskNoOnlineRun"))).toBeTruthy();
  expect(state.navigate).not.toHaveBeenCalled();
  expect(useAssistStore.getState().pending).toBeNull();
});
