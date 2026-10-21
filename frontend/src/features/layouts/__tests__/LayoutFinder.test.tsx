// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LayoutFinder } from "../components/LayoutFinder";
import type { Layout } from "../hooks/useLayouts";

afterEach(cleanup);
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
