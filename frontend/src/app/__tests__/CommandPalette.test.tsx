// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CommandPalette } from "../CommandPalette";
import { useCommandPalette } from "../commandPalette";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { createContext, useContext } from "react";

const MockUpdates = createContext(0);

const state = vi.hoisted(() => ({
  navigate: vi.fn(), pathname: "/projects/new", theme: "dark", setTheme: vi.fn(), launched: false, quit: vi.fn(),
  loaded: true,
  projects: [{ project_id: "proj_cafe", name: "Café Étoile", store_type: "cafe" }, { project_id: "proj_pharmacy", name: "약국 Sakura", store_type: "pharmacy" }],
}));
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => state.navigate, useLocation: () => ({ pathname: state.pathname }) }));
vi.mock("@/shared/queries/useProjects", () => ({ useProjects: () => {
  useContext(MockUpdates);
  return { data: state.loaded ? state.projects : undefined };
} }));
vi.mock("../theme", () => ({ useTheme: () => ({ theme: state.theme, setTheme: state.setTheme }) }));
vi.mock("../launcher", () => ({ useLauncher: () => state.launched, quitLauncher: () => state.quit() }));
Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });

beforeEach(() => {
  useLocale.getState().setLocale("en"); useCommandPalette.setState({ open: true }); state.pathname = "/projects/new"; state.launched = false; state.theme = "dark"; state.loaded = true;
  state.projects = [{ project_id: "proj_cafe", name: "Café Étoile", store_type: "cafe" }, { project_id: "proj_pharmacy", name: "약국 Sakura", store_type: "pharmacy" }];
});
afterEach(() => { cleanup(); useCommandPalette.setState({ open: false }); useLocale.getState().setLocale("en"); vi.clearAllMocks(); });
const composing = [{ name: "IME composition", isComposing: true }, { name: "legacy IME event", keyCode: 229 }];

// Context updates simulate subscriptions inside the real query/router/launcher hooks.
function showReactive() {
  let revision = 0;
  const view = render(<MockUpdates.Provider value={revision}><CommandPalette /></MockUpdates.Provider>);
  return { rerender: () => view.rerender(<MockUpdates.Provider value={++revision}><CommandPalette /></MockUpdates.Provider>) };
}

it.each(composing)("keeps Enter from navigating during $name, then accepts the completed command", (flags) => {
  render(<CommandPalette />); const input = screen.getByRole("combobox", { name: "Command" });
  fireEvent.change(input, { target: { value: "Model providers" } });
  fireEvent.keyDown(input, { key: "Enter", ...flags });
  expect(state.navigate).not.toHaveBeenCalled(); expect(screen.getByRole("dialog")).toBeTruthy();
  fireEvent.keyDown(input, { key: "Enter" });
  expect(state.navigate).toHaveBeenCalledWith({ to: "/settings", params: undefined });
});

it.each(composing.flatMap(flags => ["ArrowDown", "ArrowUp"].map(key => ({ ...flags, key }))))("keeps the active command while $name handles $key", (flags) => {
  render(<CommandPalette />); const input = screen.getByRole("combobox", { name: "Command" });
  const active = input.getAttribute("aria-activedescendant");
  fireEvent.keyDown(input, flags);
  expect(input.getAttribute("aria-activedescendant")).toBe(active);
});

it.each(composing)("keeps the palette open when Escape cancels $name", async (flags) => {
  render(<CommandPalette />); const input = screen.getByRole("combobox", { name: "Command" });
  fireEvent.keyDown(input, { key: "Escape", ...flags });
  expect(screen.getByRole("dialog")).toBeTruthy();
  fireEvent.keyDown(input, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

it.each(composing)("ignores the global shortcut during $name", (flags) => {
  render(<CommandPalette />); const input = screen.getByRole("combobox", { name: "Command" });
  fireEvent.keyDown(input, { key: "k", ctrlKey: true, ...flags });
  expect(screen.getByRole("dialog")).toBeTruthy();
  fireEvent.keyDown(input, { key: "k", ctrlKey: true });
  expect(useCommandPalette.getState().open).toBe(false);
});

it.each(LOCALES)("searches native and English commands and navigates with unchanged routes in $code", ({ code }) => {
  useLocale.getState().setLocale(code); state.pathname = "/projects/proj_original";
  render(<CommandPalette />); const input = screen.getByRole("combobox", { name: translate(code, "command") });
  expect(screen.getByRole("dialog", { name: translate(code, "commandPalette") })).toBeTruthy();
  expect(screen.getByPlaceholderText(translate(code, "commandPlaceholder"))).toBe(input);
  expect(screen.getByRole("option", { name: new RegExp(translate(code, "commandFloor")) })).toBeTruthy();
  for (const query of [translate(code, "modelProviders"), "Model providers"]) {
    fireEvent.change(input, { target: { value: query } });
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(input.getAttribute("aria-activedescendant")).toBe("cmd-models");
  }
  fireEvent.keyDown(input, { key: "Enter" });
  expect(state.navigate).toHaveBeenCalledWith({ to: "/settings", params: undefined });
});

it.each(LOCALES)("searches native store categories while keeping customer store names and IDs in $code", ({ code }) => {
  useLocale.getState().setLocale(code); render(<CommandPalette />);
  const input = screen.getByRole("combobox", { name: translate(code, "command") });
  fireEvent.change(input, { target: { value: translate(code, "pharmacy") } });
  expect(screen.getAllByRole("option")).toHaveLength(1);
  expect(screen.getByRole("option").textContent).toContain("약국 Sakura");
  fireEvent.keyDown(input, { key: "Enter" });
  expect(state.navigate).toHaveBeenCalledWith({ to: "/projects/$pid", params: { pid: "proj_pharmacy" } });
});

it.each(["ＣＡＦＥ", "Cafe Etoile", "café", "cafe-etoile", "store_proj_cafe"])("normalizes store search %s without changing its name", (query) => {
  render(<CommandPalette />); fireEvent.change(screen.getByRole("combobox", { name: "Command" }), { target: { value: query } });
  expect(screen.getAllByRole("option")).toHaveLength(1);
  expect(screen.getByRole("option").textContent).toContain("Café Étoile");
});

it("keeps a native query working and refreshes display labels when the locale changes", () => {
  useLocale.getState().setLocale("ko"); render(<CommandPalette />);
  fireEvent.change(screen.getByRole("combobox", { name: "명령" }), { target: { value: "모델 제공자" } });
  act(() => useLocale.getState().setLocale("fr"));
  expect((screen.getByRole("combobox", { name: translate("fr", "command") }) as HTMLInputElement).value).toBe("모델 제공자");
  expect(screen.getAllByRole("option")).toHaveLength(1);
  expect(screen.getByRole("option").textContent).toContain(translate("fr", "modelProviders"));
});

it("ignores navigation keys with no results and wraps correctly once search is cleared", () => {
  render(<CommandPalette />); const input = screen.getByRole("combobox", { name: "Command" });
  const query = "Unmatched".repeat(100);
  fireEvent.change(input, { target: { value: query } });
  expect(input.getAttribute("aria-activedescendant")).toBeNull();
  expect(screen.getByRole("status").textContent).toBe(translate("en", "commandNoMatches", { query }));
  for (const key of ["ArrowUp", "ArrowDown", "Enter"]) fireEvent.keyDown(input, { key });
  expect(state.navigate).not.toHaveBeenCalled(); expect(state.setTheme).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: "" } });
  fireEvent.keyDown(input, { key: "ArrowUp" }); expect(input.getAttribute("aria-activedescendant")).toBe("cmd-theme");
  fireEvent.keyDown(input, { key: "ArrowDown" }); expect(input.getAttribute("aria-activedescendant")).toBe("cmd-home");
  fireEvent.keyDown(input, { key: "Enter" }); expect(state.navigate).toHaveBeenCalledWith({ to: "/", params: undefined });
});

it("reveals late store results and removes stale active results when the list changes", () => {
  state.loaded = false; const view = showReactive(); const input = screen.getByRole("combobox", { name: "Command" });
  fireEvent.change(input, { target: { value: "Cafe Etoile" } }); expect(screen.queryByRole("option")).toBeNull();
  state.loaded = true; view.rerender();
  expect(screen.getByRole("option").textContent).toContain("Café Étoile");
  state.projects = []; view.rerender();
  expect(screen.queryByRole("option")).toBeNull(); expect(input.getAttribute("aria-activedescendant")).toBeNull();
  fireEvent.keyDown(input, { key: "Enter" }); expect(state.navigate).not.toHaveBeenCalled();
});

it.each(["input", "textarea", "select"])("does not open on slash typed into a %s", (tag) => {
  useCommandPalette.setState({ open: false }); render(<CommandPalette />);
  const editor = document.createElement(tag); document.body.append(editor);
  fireEvent.keyDown(editor, { key: "/" }); expect(useCommandPalette.getState().open).toBe(false);
  editor.remove(); fireEvent.keyDown(window, { key: "/" }); expect(useCommandPalette.getState().open).toBe(true);
});

it("keeps current-store actions out of the new-store route and preserves project IDs on real store routes", () => {
  const view = showReactive(); expect(screen.queryByRole("option", { name: /Floor & simulation/ })).toBeNull();
  state.pathname = "/town/proj_original"; view.rerender();
  fireEvent.click(screen.getByRole("option", { name: /Floor & simulation/ }));
  expect(state.navigate).toHaveBeenCalledWith({ to: "/projects/$pid", params: { pid: "proj_original" } });
});

it("runs a theme action without navigation", () => {
  state.theme = "light"; render(<CommandPalette />); fireEvent.click(screen.getByRole("option", { name: /Switch to night theme/ }));
  expect(state.setTheme).toHaveBeenCalledWith("dark"); expect(state.navigate).not.toHaveBeenCalled();
});

it("closes explicitly without executing an action", () => {
  render(<CommandPalette />); fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(useCommandPalette.getState().open).toBe(false);
  expect(state.navigate).not.toHaveBeenCalled(); expect(state.setTheme).not.toHaveBeenCalled(); expect(state.quit).not.toHaveBeenCalled();
});

it.each(["Model providers", "Switch to day theme", "Quit TwinStore"])("does not execute %s when Enter is pressed on the close button", (query) => {
  state.launched = true;
  render(<CommandPalette />);
  fireEvent.change(screen.getByRole("combobox", { name: "Command" }), { target: { value: query } });
  expect(screen.getAllByRole("option")).toHaveLength(1);
  const close = screen.getByRole("button", { name: "Close" });
  close.focus();
  // jsdom does not synthesize a button's native click from its Enter keydown.
  const notPrevented = fireEvent.keyDown(close, { key: "Enter" });
  expect(state.navigate).not.toHaveBeenCalled();
  expect(state.setTheme).not.toHaveBeenCalled();
  expect(state.quit).not.toHaveBeenCalled();
  expect(notPrevented).toBe(true);
  fireEvent.click(close);
  expect(useCommandPalette.getState().open).toBe(false);
});

it.each(["Escape", "Close"])("returns focus to the original editor after dismissing with %s", async (method) => {
  useCommandPalette.setState({ open: false }); render(<><input aria-label="Original editor" /><CommandPalette /></>);
  const editor = screen.getByRole("textbox", { name: "Original editor" }); editor.focus();
  fireEvent.keyDown(editor, { key: "k", ctrlKey: true });
  const command = await screen.findByRole("combobox", { name: "Command" });
  if (method === "Escape") fireEvent.keyDown(command, { key: "Escape" });
  else fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(document.activeElement).toBe(editor);
  expect(state.navigate).not.toHaveBeenCalled();
});

it("shows Quit only in the launcher and uses its action without navigation", () => {
  const view = showReactive(); expect(screen.queryByRole("option", { name: /Quit TwinStore/ })).toBeNull();
  state.launched = true; view.rerender(); fireEvent.click(screen.getByRole("option", { name: /Quit TwinStore/ }));
  expect(state.quit).toHaveBeenCalledOnce(); expect(state.navigate).not.toHaveBeenCalled();
});
