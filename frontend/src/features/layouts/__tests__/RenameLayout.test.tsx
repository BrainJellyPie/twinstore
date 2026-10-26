// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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


it("keeps a newer edit when an earlier rename finishes", async () => {
  let savedName = "Optimized";
  vi.mocked(api.getSetups).mockImplementation(async () => [setup("a", savedName)]);
  let finish!: (value: Awaited<ReturnType<typeof api.saveSetup>>) => void;
  vi.mocked(api.saveSetup).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  show("a");
  const field = await screen.findByLabelText("Layout name") as HTMLInputElement;
  fireEvent.change(field, { target: { value: "First name" } });
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await waitFor(() => expect(api.saveSetup).toHaveBeenCalledTimes(1));
  fireEvent.change(field, { target: { value: "Newer draft" } });
  savedName = "First name";
  await act(async () => finish({ setup: setup("a", savedName), cleared: [], blocked_faces: [], issues: [] }));
  await waitFor(() => expect(api.getSetups).toHaveBeenCalledTimes(2));
  expect(field.value).toBe("Newer draft");
  expect(screen.queryByText("Saved")).toBeNull();
});

it("does not start an overlapping rename when the name changes during a save", async () => {
  vi.mocked(api.getSetups).mockResolvedValue([setup("a", "Optimized")]);
  let finish!: (value: Awaited<ReturnType<typeof api.saveSetup>>) => void;
  vi.mocked(api.saveSetup).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  show("a");
  const field = await screen.findByLabelText("Layout name");
  const button = screen.getByRole("button", { name: "Rename" });
  fireEvent.change(field, { target: { value: "First name" } });
  fireEvent.click(button);
  await waitFor(() => expect(api.saveSetup).toHaveBeenCalledTimes(1));
  fireEvent.change(field, { target: { value: "Newer draft" } });
  fireEvent.click(button);
  await act(async () => {});
  try {
    expect(api.saveSetup).toHaveBeenCalledTimes(1);
    expect(button.getAttribute("aria-disabled")).toBe("true");
  } finally {
    await act(async () => finish({ setup: setup("a", "First name"), cleared: [], blocked_faces: [], issues: [] }));
  }
});


it("blocks two submit events before the pending render", async () => {
  vi.mocked(api.getSetups).mockResolvedValue([setup("a", "Optimized")]);
  let finish!: (value: Awaited<ReturnType<typeof api.saveSetup>>) => void;
  vi.mocked(api.saveSetup).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  show("a");
  const field = await screen.findByLabelText("Layout name");
  fireEvent.change(field, { target: { value: "New name" } });
  act(() => { fireEvent.submit(field); fireEvent.submit(field); });
  await waitFor(() => expect(api.saveSetup).toHaveBeenCalled());
  try { expect(api.saveSetup).toHaveBeenCalledTimes(1); }
  finally { await act(async () => finish({ setup: setup("a", "New name"), cleared: [], blocked_faces: [], issues: [] })); }
});

it("retains the draft after failure and allows a corrected retry", async () => {
  vi.mocked(api.getSetups).mockResolvedValueOnce([setup("a", "Optimized")]).mockResolvedValue([setup("a", "Retry name")]);
  vi.mocked(api.saveSetup).mockRejectedValueOnce(new Error("Save failed")).mockResolvedValue({ setup: setup("a", "Retry name"), cleared: [], blocked_faces: [], issues: [] });
  show("a");
  const field = await screen.findByLabelText("Layout name") as HTMLInputElement;
  const button = screen.getByRole("button", { name: "Rename" });
  fireEvent.change(field, { target: { value: "First name" } });
  fireEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Save failed");
  expect(field.value).toBe("First name");
  fireEvent.change(field, { target: { value: "Retry name" } });
  expect(screen.queryByRole("alert")).toBeNull();
  fireEvent.click(button);
  expect(await screen.findByText("Saved")).toBeTruthy();
  expect(api.saveSetup).toHaveBeenLastCalledWith("p1", "a", { name: "Retry name" });
  expect(field.value).toBe("Retry name");
});
