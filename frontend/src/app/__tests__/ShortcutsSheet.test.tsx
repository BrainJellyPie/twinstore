// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { useLocale } from "@/shared/i18n/i18n";
import { useShortcutsSheet } from "../commandPalette";
import { ShortcutsSheet } from "../ShortcutsSheet";

beforeEach(() => { useLocale.getState().setLocale("en"); useShortcutsSheet.getState().setOpen(false); });
afterEach(cleanup);

it("opens with ? and lists the playback keys", () => {
  render(<ShortcutsSheet />);
  fireEvent.keyDown(window, { key: "?" });
  expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeTruthy();
  expect(screen.getByText("Step back or forward 15 minutes on the store floor")).toBeTruthy();
});

it("does not open while typing a question mark in a field", () => {
  render(<ShortcutsSheet />);
  const input = document.createElement("input");
  document.body.append(input);
  try {
    fireEvent.keyDown(input, { key: "?" });
    expect(screen.queryByRole("dialog")).toBeNull();
  } finally { input.remove(); }
});
