// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { DeleteLayout } from "../components/DeleteLayout";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getSetups: vi.fn(), deleteSetup: vi.fn() }));

const setup = (id: string, parentId: string | null, status = "draft") =>
  ({ id, name: `Layout ${id}`, parentId, status, created_at: `2026-10-2${id.length}` }) as unknown as api.SetupSummary;

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function show(setupId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><DeleteLayout projectId="p1" setupId={setupId} /></QueryClientProvider>);
}

it("deletes a top-level layout and the layouts made from it after confirming", async () => {
  vi.mocked(api.getSetups).mockResolvedValue([setup("a", null), setup("b", null), setup("bb", "b")]);
  vi.mocked(api.deleteSetup).mockResolvedValue({ status: "deleted", deleted: ["bb", "b"] });
  show("b");
  fireEvent.click(await screen.findByRole("button", { name: "Delete this layout" }));
  expect(screen.getByText("Delete “Layout b”? This cannot be undone.")).toBeTruthy();
  expect(screen.getByText("Layouts made from it are deleted too: 1")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(api.deleteSetup).toHaveBeenCalledWith("p1", "b"));
});

it("does not offer to delete the store's last layout", async () => {
  vi.mocked(api.getSetups).mockResolvedValue([setup("a", null), setup("aa", "a")]);
  show("a");
  await waitFor(() => expect(api.getSetups).toHaveBeenCalled());
  expect(screen.queryByRole("button", { name: "Delete this layout" })).toBeNull();
});
