// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { SetupDetailWithBlocked } from "@/features/grid-editor/types";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { DashboardPanel } from "../DashboardPanel";

vi.mock("@/features/grid-editor/FloorConfigurationPanel", () => ({ FloorConfigurationPanel: () => null }));
vi.mock("@/features/products/StarterFill", () => ({ StarterFill: () => null }));
vi.mock("@/features/products/RackCopy", () => ({ RackCopy: () => null }));
vi.mock("@/features/products/ProductBulkEditor", () => ({ ProductBulkEditor: () => null }));
vi.mock("@/features/layouts/components/LayoutExcelControls", () => ({ LayoutExcelControls: () => null }));
vi.mock("@/features/runs/components/PreviewRunsList", () => ({ PreviewRunsList: () => null }));
vi.mock("@/features/runs/components/LastRunFailure", () => ({ LastRunFailure: () => null }));
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

const setup: SetupDetailWithBlocked = { id: "s", name: "Floor", status: "draft", parentId: null, runId: null, memo: "",
  readiness: null, created_at: "", updated_at: "", blocked_faces: [],
  store: { id: "store", name: "Floor", type: "cafe", grid_size: [8, 8], weekly_schedule: [], racks: [] } };

it.each(LOCALES)("translates item placement, the run hint and readiness reasons in $code", ({ code }) => {
  useLocale.getState().setLocale(code);
  const { unmount } = render(<DashboardPanel mode="ready" pid="p" sid="s" setup={setup} itemCount={0} onSimulate={vi.fn()}
    availability={{ canSimulate: false, reasons: ["no_items", "no_counter"] }} />);
  expect(screen.getByRole("heading", { name: translate(code, "itemPlacementStep") })).toBeTruthy();
  expect(screen.getByText(translate(code, "runEngineChoiceHint"))).toBeTruthy();
  expect(screen.getByText(translate(code, "readinessNoItems"))).toBeTruthy();
  expect(screen.getByText(translate(code, "readinessNoCounter"))).toBeTruthy();
  unmount();
  render(<DashboardPanel mode="ready" pid="p" sid="s" setup={{ ...setup, store: null }} itemCount={0} />);
  expect(screen.getByRole("heading", { name: translate(code, "itemPlacementStep") })).toBeTruthy();
});
