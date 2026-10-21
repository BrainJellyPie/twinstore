// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { previewFloorPlan } from "@/shared/api/client";
import { AddLayoutDialog } from "../AddLayoutDialog";

const mutation = vi.hoisted(() => ({ isPending: false, isError: false, error: null, reset: vi.fn(), mutate: vi.fn() }));
vi.mock("../../hooks/useCreateLayout", () => ({ useCreateLayout: () => mutation }));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), previewFloorPlan: vi.fn() }));

beforeEach(() => vi.stubGlobal("ResizeObserver", class {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("floor plan preview", () => {
  it("imports the page and orientation the operator previewed", async () => {
    vi.mocked(previewFloorPlan).mockImplementation(async (_pid, _file, options) => ({
      page_number: options.pageNumber, page_count: 3, rotation: options.rotation,
      width: 100, height: 50, image: "data:image/png;base64,cHJldmlldw==",
    }));
    render(<AddLayoutDialog open onOpenChange={vi.fn()} projectId="p" parentSetupId="" layouts={[]} />, { wrapper });
    fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
    const file = new File(["%PDF-"], "store.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [file] } });
    await screen.findByAltText("Floor plan page 1, rotated 0 degrees clockwise");
    fireEvent.change(screen.getByLabelText("Floor plan page"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Floor plan rotation"), { target: { value: "90" } });
    await screen.findByAltText("Floor plan page 2, rotated 90 degrees clockwise");
    fireEvent.click(screen.getByRole("button", { name: "Add layout" }));
    expect(mutation.mutate).toHaveBeenCalledWith(expect.objectContaining({
      source: { kind: "plan", file, reader: "auto", pageNumber: 2, rotation: 90 },
    }), expect.any(Object));
  });

  it("blocks layout creation when the selected page cannot be previewed", async () => {
    vi.mocked(previewFloorPlan).mockRejectedValue(new Error("This PDF has no pages."));
    render(<AddLayoutDialog open onOpenChange={vi.fn()} projectId="p" parentSetupId="" layouts={[]} />, { wrapper });
    fireEvent.click(screen.getByLabelText("From a floor plan — sketch, CAD export or PDF"));
    fireEvent.change(screen.getByLabelText("Choose floor plan file"), { target: { files: [new File(["bad"], "bad.pdf")] } });
    await screen.findByRole("alert");
    await waitFor(() => expect((screen.getByRole("button", { name: "Add layout" }) as HTMLButtonElement).disabled).toBe(true));
    expect(mutation.mutate).not.toHaveBeenCalled();
  });
});
