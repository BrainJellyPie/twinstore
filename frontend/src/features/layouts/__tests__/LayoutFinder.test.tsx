// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LayoutFinder } from "../components/LayoutFinder";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import type { Layout } from "../hooks/useLayouts";

afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });
const cafe: Layout = { id: "cafe", name: "Upstairs retreat", parentId: null, status: "draft", createdAt: "2026-10-21",
  building: { id: "house", name: "Market house", level: 2, label: "Café", floor_count: 2 },
  generation: { template_id: "book_cafe", seed: 1, currency: "JPY", requirements: "Quiet reading corner" } };
const pharmacy: Layout = { id: "pharmacy", name: "Neighborhood care", parentId: null, status: "locked", createdAt: "2026-10-20",
  generation: { template_id: "community_pharmacy", seed: 0, currency: "USD", requirements: "Open consultation space",
    reserved_areas: [{ label: "Express pickup", x: 2, y: 2, width: 3, height: 2 }] } };

it("finds a floor by building, level and brief, and switches directly to that layout", () => {
  const onSelect = vi.fn();
  render(<LayoutFinder layouts={[pharmacy, cafe]} selectedId={pharmacy.id} onSelect={onSelect} />);
  fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  fireEvent.change(screen.getByLabelText("Search layouts"), { target: { value: "HOUSE 2F quiet" } });
  expect(screen.getByRole("status").textContent).toBe("1 of 2 layouts");
  expect(screen.queryByTestId("layout-search-result-pharmacy")).toBeNull();
  fireEvent.click(screen.getByTestId("layout-search-result-cafe"));
  expect(onSelect).toHaveBeenCalledWith(cafe.id);
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("filters floors, searches formats, and resets the finder when reopened", () => {
  render(<LayoutFinder layouts={[pharmacy, cafe]} selectedId={cafe.id} onSelect={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  fireEvent.change(screen.getByLabelText("Layout group"), { target: { value: "single" } });
  expect(screen.queryByTestId("layout-search-result-cafe")).toBeNull();
  fireEvent.change(screen.getByLabelText("Search layouts"), { target: { value: "pharmacy" } });
  expect(screen.getByTestId("layout-search-result-pharmacy").textContent).toContain("Simulation saved");
  fireEvent.change(screen.getByLabelText("Search layouts"), { target: { value: "missing" } });
  expect(screen.getByText(/No matching layouts/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  expect(screen.getByRole("status").textContent).toBe("2 of 2 layouts");
  expect((screen.getByLabelText("Search layouts") as HTMLInputElement).value).toBe("");
  expect(screen.getAllByTestId(/layout-search-result-/)[0]!.getAttribute("aria-pressed")).toBe("true");
});

it("respects the parent navigation lock", () => {
  render(<LayoutFinder layouts={[cafe]} selectedId={cafe.id} onSelect={vi.fn()} disabled />);
  expect((screen.getByRole("button", { name: "Find layout" }) as HTMLButtonElement).disabled).toBe(true);
});

it("finds a layout by a saved reserved-area name", () => {
  render(<LayoutFinder layouts={[pharmacy, cafe]} selectedId={cafe.id} onSelect={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  fireEvent.change(screen.getByLabelText("Search layouts"), { target: { value: "express pickup" } });
  expect(screen.getByRole("status").textContent).toBe("1 of 2 layouts");
  expect(screen.getByTestId("layout-search-result-pharmacy").textContent).toContain("Reserved: Express pickup");
});

it("finds accent, width and separator variants consistently", () => {
  render(<LayoutFinder layouts={[pharmacy, cafe]} selectedId={cafe.id} onSelect={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  for (const query of ["CAFE", "ＣＡＦＥ", "book_cafe", "book-cafe"]) {
    fireEvent.change(screen.getByLabelText("Search layouts"), { target: { value: query } });
    expect(screen.getByTestId("layout-search-result-cafe")).toBeTruthy(); expect(screen.queryByTestId("layout-search-result-pharmacy")).toBeNull();
  }
});

it("clears only the query, restores input focus and preserves the group filter", () => {
  render(<LayoutFinder layouts={[pharmacy, cafe]} selectedId={cafe.id} onSelect={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  fireEvent.change(screen.getByLabelText("Layout group"), { target: { value: "single" } });
  fireEvent.change(screen.getByLabelText("Search layouts"), { target: { value: "missing" } });
  fireEvent.click(screen.getByRole("button", { name: "Clear layout search" }));
  expect((screen.getByLabelText("Search layouts") as HTMLInputElement).value).toBe(""); expect(document.activeElement).toBe(screen.getByLabelText("Search layouts"));
  expect((screen.getByLabelText("Layout group") as HTMLSelectElement).value).toBe("single"); expect(screen.getByRole("status").textContent).toBe("1 of 2 layouts");
});

it.each(LOCALES)("localizes discovery and resets filters without selecting a layout in $code", ({ code }) => {
  useLocale.getState().setLocale(code); const onSelect = vi.fn();
  render(<LayoutFinder layouts={[pharmacy, cafe]} selectedId={cafe.id} onSelect={onSelect} />);
  fireEvent.click(screen.getByRole("button", { name: translate(code, "findLayout") }));
  expect(screen.getByRole("dialog", { name: translate(code, "findLayoutTitle") })).toBeTruthy();
  fireEvent.change(screen.getByLabelText(translate(code, "layoutGroup")), { target: { value: "single" } });
  fireEvent.change(screen.getByLabelText(translate(code, "searchLayouts")), { target: { value: "missing" } });
  fireEvent.click(screen.getByRole("button", { name: translate(code, "resetLayoutFilters") }));
  expect(screen.getByRole("status").textContent).toBe(translate(code, "filteredLayouts", { shown: 2, total: 2 }));
  expect(document.activeElement).toBe(screen.getByLabelText(translate(code, "searchLayouts"))); expect(onSelect).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("layout-search-result-pharmacy")); expect(onSelect).toHaveBeenCalledWith("pharmacy");
});
it.each([{ isComposing: true }, { keyCode: 229 }])("preserves text and the dialog on IME Escape %j", async (flags) => {
  render(<LayoutFinder layouts={[cafe]} selectedId={cafe.id} onSelect={vi.fn()} />); fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  const input = screen.getByLabelText("Search layouts") as HTMLInputElement; fireEvent.change(input, { target: { value: "composing" } });
  fireEvent.keyDown(input, { key: "Escape", ...flags }); expect(screen.getByRole("dialog")).toBeTruthy(); expect(input.value).toBe("composing");
  fireEvent.keyDown(input, { key: "Escape" }); expect(input.value).toBe(""); expect(screen.getByRole("dialog")).toBeTruthy();
  fireEvent.keyDown(input, { key: "Escape" }); await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});
it("keeps focus and filters through locale and live catalog changes without choosing another layout", () => {
  const onSelect = vi.fn(); const props = { layouts: [pharmacy, cafe], selectedId: cafe.id, onSelect };
  const { rerender } = render(<LayoutFinder {...props} />); fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  const input = screen.getByLabelText("Search layouts"); input.focus(); fireEvent.change(input, { target: { value: "cafe" } });
  act(() => useLocale.getState().setLocale("ko")); rerender(<LayoutFinder {...props} layouts={[pharmacy]} />);
  expect(document.activeElement).toBe(input); expect((input as HTMLInputElement).value).toBe("cafe"); expect(onSelect).not.toHaveBeenCalled();
  expect(screen.queryByTestId("layout-search-result-cafe")).toBeNull(); expect(screen.getByText(translate("ko", "noMatchingLayouts"))).toBeTruthy();
});
it("distinguishes an empty catalog and uses singular counts with an unnamed layout", () => {
  const props = { layouts: [] as Layout[], selectedId: undefined, onSelect: vi.fn() }; const { rerender } = render(<LayoutFinder {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Find layout" })); expect(screen.getByText("No layouts saved yet.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Reset layout filters" })).toBeNull();
  rerender(<LayoutFinder {...props} layouts={[{ ...cafe, name: "" }]} />); expect(screen.getByRole("status").textContent).toBe("1 of 1 layout");
  expect(screen.getByTestId("layout-search-result-cafe").textContent).toContain("Layout 1");
});
it("respects a navigation lock applied while the dialog is already open", () => {
  const onSelect = vi.fn(); const props = { layouts: [pharmacy, cafe], selectedId: cafe.id, onSelect };
  const { rerender } = render(<LayoutFinder {...props} />); fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  rerender(<LayoutFinder {...props} disabled />); const result = screen.getByTestId("layout-search-result-pharmacy") as HTMLButtonElement;
  expect(result.disabled).toBe(true); fireEvent.click(result); expect(onSelect).not.toHaveBeenCalled();
});

it("opens the first match with Enter and moves into the results with the down arrow", () => {
  const onSelect = vi.fn();
  render(<LayoutFinder layouts={[pharmacy, cafe]} selectedId={pharmacy.id} onSelect={onSelect} />);
  fireEvent.click(screen.getByRole("button", { name: "Find layout" }));
  const search = screen.getByLabelText("Search layouts");
  fireEvent.change(search, { target: { value: "quiet" } });
  fireEvent.keyDown(search, { key: "ArrowDown" });
  expect(document.activeElement).toBe(screen.getByTestId("layout-search-result-cafe"));
  fireEvent.keyDown(search, { key: "Enter" });
  expect(onSelect).toHaveBeenCalledWith(cafe.id);
  expect(screen.queryByRole("dialog")).toBeNull();
});
