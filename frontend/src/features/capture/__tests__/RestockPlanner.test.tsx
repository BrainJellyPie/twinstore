// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { AuditReport } from "@/shared/api/client";
import { RestockPlanner } from "../RestockPlanner";

afterEach(cleanup);

const report: AuditReport = {
  job_id: "a", capture_id: "c", setup_id: "s", rack_id: "r", face: "N", currency: "USD", compliance: 0,
  levels: [], findings: [{ kind: "missing", level: 3, sku: "A", name: "Cola", expected: "stock", found: "none",
    box: { x1: 1, y1: 1, x2: 2, y2: 2 }, loss_per_day: 10000, loss_ci: [8000, 12000] }],
  impact: null, visitors_per_day: 100, revenue_delta_per_day: -10000, revenue_delta_ci: [-12000, -8000],
  panel_size: 50, notes: [], seconds: 1,
};

it("recalculates decisions from operator costs and locates the shelf gap", () => {
  const onFocus = vi.fn();
  render(<RestockPlanner report={report} onFocus={onFocus} />);
  expect(screen.getByText("Positive lower bound")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Locate" }));
  expect(onFocus).toHaveBeenCalledWith(report.findings[0]?.box);
  fireEvent.change(screen.getByLabelText("Overhead per SKU (USD minor units)"), { target: { value: "10000" } });
  expect(screen.getByText("Nonpositive interval")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Recovery horizon (trading days)"), { target: { value: "0" } });
  expect(screen.getByRole("alert")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Export restocking CSV" }) as HTMLButtonElement).disabled).toBe(true);
});
