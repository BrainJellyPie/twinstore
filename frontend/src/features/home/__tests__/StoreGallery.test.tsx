// @vitest-environment jsdom
import type { ComponentProps } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ProjectListItem } from "@/shared/api/client";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { StoreGallery } from "../StoreGallery";

vi.mock("../StoreTile", () => ({
  StoreTile: ({ project, onOpen }: { project: ProjectListItem; onOpen: () => void }) => <button onClick={onOpen}>{project.name}</button>,
  NewStoreTile: ({ onClick }: { onClick: () => void }) => <button onClick={onClick}>New store</button>,
  StoreTileSkeleton: () => <span>Skeleton</span>,
}));
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

const base: ProjectListItem = { project_id: "a", name: "Morning Coffee", description: "Office workers", store_type: "coffee_shop", grid_size: [8, 8], weekly_schedule: [], created_at: "", updated_at: "", status: "Ready" };
const projects = [base, { ...base, project_id: "b", name: "Night Market", store_type: "supermarket", description: "Late-night snacks" }];
function show(overrides: Partial<ComponentProps<typeof StoreGallery>> = {}) {
  const props = { projects, isLoading: false, isFetching: false, error: null, onRetry: vi.fn(), onOpen: vi.fn(), onCreate: vi.fn(), ...overrides };
  const result = render(<StoreGallery {...props} />);
  return { ...result, props, update: (next: Partial<typeof props>) => result.rerender(<StoreGallery {...props} {...next} />) };
}
function filter(value: string) { fireEvent.change(screen.getByRole("searchbox", { name: "Filter stores" }), { target: { value } }); }

it.each(["coffee", "COFFEE", "  Morning   Coffee ", "coffee shop", "office workers"])("finds a store by normalized name, format or description (%s)", (query) => {
  show(); filter(query);
  expect(screen.getByRole("button", { name: base.name })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Night Market" })).toBeNull();
  expect(screen.getByRole("status").textContent).toBe("1 of 2 stores");
});

it.each(["Cafe Etoile", "ＣＡＦＥ", "cafe-etoile"])("matches accents and width variants in %s while preserving store names and IDs", (query) => {
  const { props } = show({ projects: [{ ...base, project_id: "proj_accent", name: "Café Étoile", store_type: "cafe" }, projects[1]!] });
  filter(query); fireEvent.click(screen.getByRole("button", { name: "Café Étoile" }));
  expect(screen.queryByRole("button", { name: "Night Market" })).toBeNull();
  expect(props.onOpen).toHaveBeenCalledWith("proj_accent");
});

it("explains an empty result and restores the list with keyboard focus", () => {
  show(); filter("missing store");
  expect(screen.getByRole("heading", { name: "No matching stores" })).toBeTruthy();
  expect(screen.getByRole("status").textContent).toBe("0 of 2 stores");
  fireEvent.click(screen.getByRole("button", { name: "Clear filter" }));
  expect(screen.getByRole("button", { name: base.name })).toBeTruthy();
  expect(document.activeElement).toBe(screen.getByRole("searchbox"));
  expect(screen.queryByText("No matching stores")).toBeNull();
});

it.each(["", "   ", "\t"])("shows all stores for an empty or whitespace query (%j)", (query) => {
  show(); filter(query);
  expect(screen.getByRole("button", { name: base.name })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Night Market" })).toBeTruthy();
  expect(screen.queryByText("No matching stores")).toBeNull();
});

it("keeps the filter available when the list shrinks to one store", () => {
  const { update } = show(); filter("Night");
  update({ projects: [base] });
  expect(screen.getByRole("searchbox")).toBeTruthy();
  expect(screen.getByText("No matching stores")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear store filter" }));
  expect(screen.getByRole("button", { name: base.name })).toBeTruthy();
});

it("clears a retained query after the last store disappears and focuses the heading", () => {
  const { update } = show(); filter("Night");
  update({ projects: [] });
  fireEvent.click(screen.getByRole("button", { name: "Clear filter" }));
  expect(screen.queryByRole("searchbox")).toBeNull();
  expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Your stores" }));
  expect(screen.getByText(/No stores yet/)).toBeTruthy();
});

it("clears with Escape and keeps focus in a populated search", () => {
  show(); filter("Night");
  const input = screen.getByRole("searchbox"); input.focus();
  fireEvent.keyDown(input, { key: "Escape" });
  expect((input as HTMLInputElement).value).toBe("");
  expect(document.activeElement).toBe(input);
});

it.each([["regexp characters", "[.*]"], ["markup", "<script>"], ["long query", "a".repeat(5000)]])("treats %s as literal text", (_label, query) => {
  show(); filter(query);
  expect(screen.getByText("No matching stores")).toBeTruthy();
  expect(document.querySelector("script")).toBeNull();
});

it.each([
  ["東京 スーパー", "東京　スーパー"], ["서울 편의점", "서울 편의점"],
  ["ガーデン", "ｶﾞｰﾃﾞﾝ"], ["Cafe", "Ｃａｆｅ"],
])("normalizes international search text for %s", (name, query) => {
  show({ projects: [{ ...base, name }] }); filter(query);
  expect(screen.getByRole("button", { name })).toBeTruthy();
});

it("shows loading separately from an empty workspace", () => {
  show({ projects: undefined, isLoading: true, isFetching: true });
  expect(screen.getByRole("status", { name: "Loading stores" })).toBeTruthy();
  expect(screen.queryByText(/No stores yet/)).toBeNull();
  expect(screen.queryByRole("button", { name: "New store" })).toBeNull();
});

it("explains an initial failure and retries without pretending the workspace is empty", () => {
  const { props, update } = show({ projects: undefined, error: new Error("Connection lost") });
  expect(screen.getByRole("alert").textContent).toContain("Connection lost");
  expect(screen.queryByText(/No stores yet/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Try again" })); expect(props.onRetry).toHaveBeenCalledOnce();
  update({ isFetching: true });
  expect((screen.getByRole("button", { name: "Trying again…" }) as HTMLButtonElement).disabled).toBe(true);
});

it("retains cached stores when a refresh fails", () => {
  show({ error: new Error("Refresh failed") }); filter("coffee");
  expect(screen.getByRole("alert").textContent).toContain("Refresh failed");
  expect(screen.getByRole("button", { name: base.name })).toBeTruthy();
});

it("opens the selected store and still allows creation after an unmatched search", () => {
  const { props } = show();
  fireEvent.click(screen.getByRole("button", { name: base.name }));
  expect(props.onOpen).toHaveBeenCalledWith("a");
  filter("missing"); fireEvent.click(screen.getByRole("button", { name: "New store" }));
  expect(props.onCreate).toHaveBeenCalledOnce();
});

it.each(LOCALES)("searches translated store types in $code without altering IDs", ({ code }) => {
  show({ projects: [{ ...base, store_type: "cafe" }] });
  act(() => useLocale.getState().setLocale(code));
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: translate(code, "cafe") } });
  expect(screen.getByRole("status").textContent).toBe(translate(code, "filteredOneStore", { shown: 1, total: 1 }));
  expect(screen.getByRole("button", { name: base.name })).toBeTruthy();
});

it.each(LOCALES)("leads a load failure with the $code message and keeps the raw detail secondary", ({ code }) => {
  useLocale.getState().setLocale(code);
  show({ projects: undefined, error: new TypeError("Failed to fetch") });
  const alert = screen.getByRole("alert");
  expect(alert.querySelector(".font-medium")!.textContent).toBe(translate(code, "loadStoresError"));
  expect(alert.textContent).toContain("Failed to fetch");
});
