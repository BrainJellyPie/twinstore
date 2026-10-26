// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { readReceipts, uploadFidelity, type FidelityReport, type ReceiptsResult } from "@/shared/api/client";
import { FidelitySection } from "../FidelitySection";

vi.mock("@/shared/api/client", () => ({ readReceipts: vi.fn(), uploadFidelity: vi.fn(), reviewReceipts: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const receipts: ReceiptsResult = {
  receipts: [], matched_lines: 0, unmatched_lines: 0, products: {}, currency: "USD", csv: "",
};
const report: FidelityReport = {
  real_transactions: 7, sim_customers: 9, matched_skus: 2, metrics: [], notes: [],
};

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
}

it.each([
  { projectId: "other", runId: "r" },
  { projectId: "p", runId: "other" },
])("clears receipt review and scores when switching to %j", async (next) => {
  vi.mocked(readReceipts).mockResolvedValue(receipts);
  vi.mocked(uploadFidelity).mockResolvedValue(report);
  const { container, rerender } = render(<FidelitySection projectId="p" runId="r" />, { wrapper });
  fireEvent.change(container.querySelector('input[type="file"]:not([multiple])')!, {
    target: { files: [new File(["csv"], "sales.csv")] },
  });
  await screen.findByText(/7 real receipts/);
  fireEvent.change(container.querySelector('input[type="file"][multiple]')!, {
    target: { files: [new File(["photo"], "receipt.png")] },
  });
  await screen.findByRole("region", { name: "Review receipt readings" });

  rerender(<FidelitySection {...next} />);

  expect(screen.queryByRole("region", { name: "Review receipt readings" })).toBeNull();
  expect(screen.queryByText(/7 real receipts/)).toBeNull();
});

it.each(["receipts", "sales"] as const)("ignores a late %s response after switching runs", async (kind) => {
  let complete = () => {};
  if (kind === "receipts") {
    vi.mocked(readReceipts).mockImplementation(() => new Promise((resolve) => { complete = () => resolve(receipts); }));
  } else {
    vi.mocked(uploadFidelity).mockImplementation(() => new Promise((resolve) => { complete = () => resolve(report); }));
  }
  const { container, rerender } = render(<FidelitySection projectId="p" runId="r" />, { wrapper });
  fireEvent.change(container.querySelector(kind === "receipts" ? 'input[multiple]' : 'input[type="file"]:not([multiple])')!, {
    target: { files: [new File(["data"], "input")] },
  });
  await screen.findByRole("button", { name: kind === "receipts" ? "Reading…" : "Scoring…" });
  rerender(<FidelitySection projectId="p" runId="next" />);
  await act(async () => complete());
  await waitFor(() => expect(screen.getByRole("button", { name: kind === "receipts" ? "Receipts" : "Upload POS" })).toBeTruthy());

  expect(screen.queryByRole("region", { name: "Review receipt readings" })).toBeNull();
  expect(screen.queryByText(/7 real receipts/)).toBeNull();
});

it("names metrics in plain words in the selected language and keeps the statistic's id in the tooltip", async () => {
  const { useLocale } = await import("@/shared/i18n/i18n");
  useLocale.getState().setLocale("ko");
  try {
    const metric = (name: string) => ({ name, value: 0.5, better: "higher", description: "" });
    vi.mocked(uploadFidelity).mockResolvedValue({ ...report, metrics: [metric("sku_js_similarity"), metric("sku_ndcg@10"), metric("new_metric_x")] });
    const { container } = render(<FidelitySection projectId="p" runId="r" />, { wrapper });
    fireEvent.change(container.querySelector('input[type="file"]:not([multiple])')!, { target: { files: [new File(["csv"], "sales.csv")] } });
    const label = await screen.findByText("상품 구성 유사도");
    expect(label.getAttribute("title")).toBe("sku_js_similarity");
    expect(screen.getByText("상위 10개 인기 상품 일치 (NDCG)")).toBeTruthy();
    expect(screen.getByText("new metric x")).toBeTruthy();
  } finally {
    useLocale.getState().setLocale("en");
  }
});
