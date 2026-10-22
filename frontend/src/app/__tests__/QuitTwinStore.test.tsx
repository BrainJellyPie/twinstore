// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { useLocale } from "@/shared/i18n/i18n";

import { QuitButton, TAB_CLOSE_NOTICE_KEY, TabCloseNotice } from "../QuitTwinStore";

const state = vi.hoisted(() => ({ launched: false, quit: vi.fn() }));
vi.mock("../launcher", () => ({
  useLauncher: () => state.launched,
  quitLauncher: (note: unknown) => state.quit(note),
}));

beforeEach(() => {
  useLocale.getState().setLocale("en");
  state.launched = false;
  localStorage.clear();
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("shows the Quit button only when the app runs under the launcher", () => {
  const view = render(<QuitButton />);
  expect(screen.queryByRole("button", { name: "Quit TwinStore" })).toBeNull();
  state.launched = true;
  view.rerender(<QuitButton />);
  const button = screen.getByRole("button", { name: "Quit TwinStore" });
  expect(button.textContent).toContain("Quit");
  expect(button.getAttribute("title")).toMatch(/Closing this tab does not stop it/);
});

it("asks before quitting, and quits only on confirmation", () => {
  state.launched = true;
  render(<QuitButton />);
  fireEvent.click(screen.getByRole("button", { name: "Quit TwinStore" }));
  expect(screen.getByRole("alertdialog")).toBeTruthy();
  expect(screen.getByText(/Running simulations and generations stop too, and so does the local model/)).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(state.quit).not.toHaveBeenCalled();
  expect(screen.queryByRole("alertdialog")).toBeNull();

  fireEvent.click(screen.getByRole("button", { name: "Quit TwinStore" }));
  const dialog = screen.getByRole("alertdialog");
  fireEvent.click(Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent === "Quit TwinStore")!);
  expect(state.quit).toHaveBeenCalledWith({
    title: "TwinStore stopped",
    body: "You can close this tab. Click the TwinStore icon to start it again.",
  });
});

it("localizes the button and the stopped screen", () => {
  state.launched = true;
  useLocale.getState().setLocale("ko");
  render(<QuitButton />);
  fireEvent.click(screen.getByRole("button", { name: "TwinStore 종료" }));
  const dialog = screen.getByRole("alertdialog");
  expect(dialog.textContent).toContain("TwinStore를 종료할까요?");
  fireEvent.click(Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent === "TwinStore 종료")!);
  expect(state.quit).toHaveBeenCalledWith(expect.objectContaining({ title: "TwinStore가 종료되었습니다" }));
});

it("warns once that closing the tab does not stop TwinStore, and remembers the dismissal", () => {
  const view = render(<TabCloseNotice />);
  expect(screen.queryByRole("note")).toBeNull();          // not under the launcher: nothing to warn about
  state.launched = true;
  view.rerender(<TabCloseNotice />);
  expect(screen.getByRole("note").textContent).toContain("Closing this tab does not stop TwinStore");
  expect(screen.getByText(/press Quit at the top right/)).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "Hide this notice" }));
  expect(screen.queryByRole("note")).toBeNull();
  expect(localStorage.getItem(TAB_CLOSE_NOTICE_KEY)).toBe("1");

  view.unmount();
  render(<TabCloseNotice />);
  expect(screen.queryByRole("note")).toBeNull();          // stays hidden after a reload
});

it("still shows and hides the notice when browser storage is blocked", () => {
  state.launched = true;
  const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
  render(<TabCloseNotice />);
  fireEvent.click(screen.getByRole("button", { name: "Hide this notice" }));
  expect(screen.queryByRole("note")).toBeNull();
  get.mockRestore(); set.mockRestore();
});
