// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { readReceipts, reviewReceipts, uploadFidelity, type ReceiptsResult } from "@/shared/api/client";
import { ReceiptReviewPanel } from "../ReceiptReviewPanel";
import { FidelitySection } from "../FidelitySection";

vi.mock("@/shared/api/client", () => ({ reviewReceipts: vi.fn(), readReceipts: vi.fn(), uploadFidelity: vi.fn() }));

afterEach(() => { cleanup(); vi.resetAllMocks(); });

const result: ReceiptsResult = {
  receipts: [{ receipt_id: "r1", store: "Shop", timestamp: "2026-10-21 14:05", currency: "USD", total: 200, notes: [],
    lines: [{ name: "Cola", quantity: 1, unit_price: 200, line_total: 200, sku: "A1", matched: true }] }],
  matched_lines: 1, unmatched_lines: 0, products: { A1: "Cola" }, currency: "USD", csv: "unreviewed",
};

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("receipt review", () => {
  it("requires a check before scoring and invalidates it when an amount changes", async () => {
    vi.mocked(reviewReceipts).mockResolvedValue({ receipts: result.receipts, issues: [], ready: true, included_lines: 1, currency: "USD", csv: "reviewed" });
    const onScore = vi.fn();
    render(<ReceiptReviewPanel projectId="p" runId="r" result={result} scoring={false} onScore={onScore} />, { wrapper });
    const useButton = screen.getByRole("button", { name: "Use reviewed receipts" }) as HTMLButtonElement;
    expect(useButton.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Check receipts" }));
    await waitFor(() => expect(useButton.disabled).toBe(false));
    expect(onScore).not.toHaveBeenCalled();
    fireEvent.click(useButton);
    expect(onScore).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Line total for r1 line 1"), { target: { value: "100" } });
    expect(useButton.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Check receipts" }));
    await waitFor(() => expect(vi.mocked(reviewReceipts).mock.lastCall?.[2][0]?.lines[0]?.line_total).toBe(100));
  });

  it("omits excluded receipts before requesting review", async () => {
    vi.mocked(reviewReceipts).mockResolvedValue({ receipts: [], issues: [], ready: false, included_lines: 0, currency: "USD", csv: "" });
    render(<ReceiptReviewPanel projectId="p" runId="r" result={result} scoring={false} onScore={vi.fn()} />, { wrapper });
    fireEvent.click(screen.getByLabelText("Include r1 · Shop"));
    fireEvent.click(screen.getByRole("button", { name: "Check receipts" }));
    await waitFor(() => expect(reviewReceipts).toHaveBeenCalledWith("p", "r", []));
  });

  it("does not automatically score an OCR response", async () => {
    vi.mocked(readReceipts).mockResolvedValue(result);
    const { container } = render(<FidelitySection projectId="p" runId="r" />, { wrapper });
    const fileInput = container.querySelector('input[type="file"][multiple]')!;
    fireEvent.change(fileInput, { target: { files: [new File(["photo"], "r.png", { type: "image/png" })] } });
    await screen.findByRole("region", { name: "Review receipt readings" });
    expect(uploadFidelity).not.toHaveBeenCalled();
  });
});
