// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LayoutTabs } from "../components/LayoutTabs";
import type { Layout } from "../hooks/useLayouts";
import { LOCALES } from "@/shared/i18n/messages";
import { translate, useLocale } from "@/shared/i18n/i18n";
const layouts: Layout[] = ["one", "two", "three"].map((id) => ({ id, name: id, parentId: null, status: "draft", createdAt: "2026-10-21" }));
beforeEach(() => { vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} }); Element.prototype.scrollIntoView = vi.fn(); });
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.unstubAllGlobals(); });
function show(selectedId: string | undefined = "two", disabled = false) { const props = { layouts, selectedId, onSelect: vi.fn(), onAddNew: vi.fn(), disabled }; return { ...render(<LayoutTabs {...props} />), props }; }

it("has one Tab entry for the selected layout, regardless of layout count", () => {
  show(); const tabs = screen.getAllByRole("tab"); expect(tabs.map(tab => tab.tabIndex)).toEqual([-1, 0, -1]);
});
it("moves focus with arrows, Home and End without loading a different layout", () => {
  const { props } = show(); const tabs = screen.getAllByRole("tab"); tabs[1]!.focus();
  for (const [key, index] of [["ArrowRight", 2], ["ArrowRight", 0], ["ArrowLeft", 2], ["Home", 0], ["End", 2]] as const) {
    fireEvent.keyDown(document.activeElement!, { key }); expect(document.activeElement).toBe(tabs[index]); expect(tabs[index]!.tabIndex).toBe(0);
  }
  expect(props.onSelect).not.toHaveBeenCalled(); fireEvent.click(tabs[2]!); expect(props.onSelect).toHaveBeenCalledWith("three");
});
it("provides a first-tab entry when selection is absent, without choosing on the user's behalf", () => {
  const { props } = show("removed"); expect(screen.getAllByRole("tab").map(tab => tab.tabIndex)).toEqual([0, -1, -1]); expect(props.onSelect).not.toHaveBeenCalled();
});
it.each([{ isComposing: true }, { keyCode: 229 }])("ignores IME navigation and activation %j", (flags) => {
  const { props } = show(); const two = screen.getByRole("tab", { name: "two" }); two.focus();
  fireEvent.keyDown(two, { key: "ArrowRight", ...flags }); expect(document.activeElement).toBe(two); expect(props.onSelect).not.toHaveBeenCalled();
  expect(fireEvent.keyDown(two, { key: "Enter", ...flags })).toBe(false);
});
it("respects navigation locking for tabs, finder, new layout and programmatic key events", () => {
  const { props } = show("two", true); const tabs = screen.getAllByRole("tab");
  for (const tab of tabs) expect((tab as HTMLButtonElement).disabled).toBe(true);
  fireEvent.keyDown(tabs[1]!, { key: "ArrowRight" }); fireEvent.click(tabs[0]!); expect(props.onSelect).not.toHaveBeenCalled();
  expect((screen.getByRole("button", { name: "Find layout" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "New layout" }) as HTMLButtonElement).disabled).toBe(true);
});
it("does not steal focus after an external selection or language change", () => {
  const { props, rerender } = show(); const add = screen.getByRole("button", { name: "New layout" }); add.focus();
  rerender(<LayoutTabs {...props} selectedId="three" />); act(() => useLocale.getState().setLocale("ja")); expect(document.activeElement).toBe(add);
});
it("keeps a reachable fallback when the focused layout disappears", () => {
  const { props, rerender } = show(); const two = screen.getByRole("tab", { name: "two" }); two.focus();
  rerender(<LayoutTabs {...props} layouts={[layouts[0]!, layouts[2]!]} selectedId="one" />);
  expect(document.activeElement).toBe(screen.getByRole("tab", { name: "one" })); expect(props.onSelect).not.toHaveBeenCalled();
});

it.each([undefined, "one", "two"])("does not choose or move focus when an unfocused layout disappears (selected %s)", (selected) => {
  const { props, rerender } = show(selected); const add = screen.getByRole("button", { name: "New layout" }); add.focus();
  rerender(<LayoutTabs {...props} layouts={[layouts[2]!]} selectedId="three" />);
  expect(document.activeElement).toBe(add); expect(screen.getByRole("tab").tabIndex).toBe(0); expect(props.onSelect).not.toHaveBeenCalled();
});
it("does not reload the selected layout or treat browser navigation shortcuts as tab movement", () => {
  const { props } = show(); const two = screen.getByRole("tab", { name: "two" }); two.focus();
  fireEvent.click(two); fireEvent.keyDown(two, { key: "ArrowLeft", altKey: true }); expect(props.onSelect).not.toHaveBeenCalled(); expect(document.activeElement).toBe(two);
});
it("handles an empty list without invalid focus targets or selection", () => {
  const { props, rerender } = show(); rerender(<LayoutTabs {...props} layouts={[]} selectedId={undefined} />);
  expect(screen.queryByRole("tab")).toBeNull(); expect(props.onSelect).not.toHaveBeenCalled();
});
it.each(LOCALES)("localizes layout navigation and floor context without altering raw IDs in $code", ({ code }) => {
  useLocale.getState().setLocale(code); const { props, rerender } = show("one");
  rerender(<LayoutTabs {...props} layouts={[{ ...layouts[0]!, name: "", building: { id: "raw-building", name: "우리商店", level: 2, label: "Cafe", floor_count: 3 } }]} />);
  expect(screen.getByRole("tablist", { name: translate(code, "layoutsLabel") })).toBeTruthy();
  const tab = screen.getByRole("tab", { name: translate(code, "unnamedLayout", { number: 1 }) });
  expect(tab.textContent).toContain(translate(code, "layFloorBadge", { number: 2 }));
  expect(tab.title).toContain(translate(code, "buildingFloorPosition", { level: 2, count: 3 })); expect(tab.dataset.layoutId).toBe("one");
  expect(screen.getByRole("button", { name: translate(code, "newLayout") })).toBeTruthy();
});
