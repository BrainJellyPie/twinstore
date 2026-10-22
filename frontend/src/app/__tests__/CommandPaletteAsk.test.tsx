// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";
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
Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });

beforeEach(() => { useLocale.getState().setLocale("en"); useCommandPalette.setState({ open: true }); state.pathname = "/projects/proj_cafe"; });
afterEach(() => { cleanup(); useCommandPalette.setState({ open: false }); useAssistStore.setState({ pending: null }); vi.clearAllMocks(); });

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
] as const)("routes a typed request to %s and hands the words to that page", async (destination, text, to) => {
  vi.mocked(api.routeAssist).mockResolvedValue({ destination, reason: "" });
  useSimulationStore.getState().setActiveTab("settings");
  const input = type(text);
  expect(screen.getAllByRole("option")[0]!.textContent).toContain(text);
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() => expect(state.navigate).toHaveBeenCalledWith({ to, params: { pid: "proj_cafe" } }));
  expect(api.routeAssist).toHaveBeenCalledWith({ text, has_run: true });
  expect(useAssistStore.getState().pending).toMatchObject({ projectId: "proj_cafe", destination, text });
  expect(useSimulationStore.getState().activeTab).toBe(destination === "run_question" ? "dashboard" : "settings");  // layout edits open Store
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
