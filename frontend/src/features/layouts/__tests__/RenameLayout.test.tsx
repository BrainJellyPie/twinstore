// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { RenameLayout } from "../components/RenameLayout";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getSetups: vi.fn(), saveSetup: vi.fn() }));

const setup = (id: string, name: string, status = "draft") =>
  ({ id, name, parentId: null, status, created_at: `2026-10-2${id.length}` }) as unknown as api.SetupSummary;

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function show(setupId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><RenameLayout projectId="p1" setupId={setupId} /></QueryClientProvider>);
}

it("renames a layout with a trimmed name and keeps the new name while the list refreshes", async () => {
  vi.mocked(api.getSetups).mockResolvedValueOnce([setup("a", "Optimized")]).mockResolvedValue([setup("a", "Wide aisles")]);
  vi.mocked(api.saveSetup).mockResolvedValue({ setup: setup("a", "Wide aisles"), cleared: [], blocked_faces: [], issues: [] });
  show("a");
  const field = await screen.findByLabelText("Layout name") as HTMLInputElement;
  expect(field.value).toBe("Optimized");
  fireEvent.change(field, { target: { value: "  Wide aisles " } });
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await waitFor(() => expect(api.saveSetup).toHaveBeenCalledWith("p1", "a", { name: "Wide aisles" }));
  expect(await screen.findByText("Saved")).toBeTruthy();
  expect(field.value).toBe("Wide aisles");
});

it("does not save an empty or unchanged name", async () => {
  vi.mocked(api.getSetups).mockResolvedValue([setup("a", "Optimized")]);
  show("a");
  const field = await screen.findByLabelText("Layout name");
  const rename = screen.getByRole("button", { name: "Rename" });
  expect(rename.getAttribute("aria-disabled")).toBe("true");
  fireEvent.click(rename);
  fireEvent.change(field, { target: { value: "   " } });
  fireEvent.submit(field);
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(api.saveSetup).not.toHaveBeenCalled();
});

it("is not offered for a finalized layout, which the server keeps unchanged", async () => {
  vi.mocked(api.getSetups).mockResolvedValue([setup("a", "Final", "locked")]);
  show("a");
  await waitFor(() => expect(api.getSetups).toHaveBeenCalled());
  expect(screen.queryByLabelText("Layout name")).toBeNull();
});
