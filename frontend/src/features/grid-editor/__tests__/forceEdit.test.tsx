// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useLocale } from "@/shared/i18n/i18n";
import { FloorConfigurationPanel } from "../FloorConfigurationPanel";
import type { SetupDetailWithBlocked } from "../types";

const save = vi.hoisted(() => vi.fn());
vi.mock("../gridEditorApi", () => ({ saveSetup: save, loadSetup: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); useLocale.getState().setLocale("en"); });

const setup: SetupDetailWithBlocked = { id: "s", name: "Floor", status: "draft", parentId: null, runId: null, memo: "",
  readiness: null, created_at: "2026-10-22", updated_at: "2026-10-22", blocked_faces: [],
  store: { id: "store", name: "Floor", type: "cafe", grid_size: [8, 8], weekly_schedule: [], racks: [] } };

function renderPanel(value: SetupDetailWithBlocked) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <FloorConfigurationPanel pid="p" sid="s" setup={value} itemCount={3} />
  </QueryClientProvider>);
}

it("shows the server's reason when clearing items before a floor edit fails", async () => {
  save.mockResolvedValue({ ok: false, status: 409, code: "setup_locked", reason: "run_active", details: {},
    message: "This layout is locked while a simulation is running." });
  renderPanel(setup);
  fireEvent.click(screen.getByTestId("floor-config-edit-link"));
  fireEvent.click(screen.getByRole("button", { name: "Edit floor configuration" }));
  expect((await screen.findByTestId("edit-floor-confirm-error")).textContent)
    .toBe("This layout is locked while a simulation is running.");
});

it("translates the floor step heading and actions", () => {
  useLocale.getState().setLocale("ko");
  const { unmount } = renderPanel(setup);
  expect(screen.getByRole("heading").textContent).toBe("1단계: 매장 배치 구성");
  expect(screen.getByTestId("floor-config-edit-link").textContent).toBe("편집");
  unmount();
  renderPanel({ ...setup, store: null });
  expect(screen.getByTestId("floor-config-build-button").textContent).toBe("빈 배치부터 시작");
});
