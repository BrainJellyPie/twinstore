// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { getMovementReport, uploadMovement, type MovementReport } from "@/shared/api/movement";
import { MovementSection } from "../MovementSection";

vi.mock("@/shared/api/movement", () => ({ getMovementReport: vi.fn(), uploadMovement: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const report: MovementReport = {
  grid_size: [2, 1], max_gap_seconds: 30, created_at: "2026-10-21T05:00:00Z", notes: [],
  visitation_similarity: 1, occupancy_similarity: 1, largest_gaps: [],
  observed: { tracks: 2, samples: 4, duplicate_samples: 0, single_point_tracks: 0, excluded_gaps: 0,
    excluded_seconds: 0, observed_seconds: 10, visitors: [[2, 1]], occupancy_seconds: [[7, 3]] },
  simulated: { tracks: 4, samples: 8, duplicate_samples: 0, single_point_tracks: 0, excluded_gaps: 0,
    excluded_seconds: 0, observed_seconds: 20, visitors: [[4, 2]], occupancy_seconds: [[14, 6]] },
};

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("movement comparison", () => {
  it("loads saved aggregate maps and switches to occupancy", async () => {
    vi.mocked(getMovementReport).mockResolvedValue(report);
    render(<MovementSection projectId="p" runId="r" />, { wrapper });
    await screen.findByText(/2 observed tracks/);
    expect(screen.getAllByRole("img")).toHaveLength(2);
    expect(screen.getByText("Shared color scale: 0–100.0%. Hover a cell for its coordinates and share.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Movement map layer"), { target: { value: "occupancy_seconds" } });
    expect(screen.getByText("Shared color scale: 0–70.0%. Hover a cell for its coordinates and share.")).toBeTruthy();
  });

  it("passes the gap threshold and prevents a pending read from overwriting a new upload", async () => {
    let resolveRead: (value: MovementReport | null) => void = () => {};
    vi.mocked(getMovementReport).mockImplementation(() => new Promise((resolve) => { resolveRead = resolve; }));
    vi.mocked(uploadMovement).mockResolvedValue(report);
    const { container } = render(<MovementSection projectId="p" runId="r" />, { wrapper });
    fireEvent.change(screen.getByLabelText("Maximum tracking gap"), { target: { value: "6" } });
    const file = new File(["csv"], "tracks.csv", { type: "text/csv" });
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
    await waitFor(() => expect(uploadMovement).toHaveBeenCalledWith("p", "r", file, 6));
    await screen.findByText(/2 observed tracks/);
    await act(async () => { resolveRead(null); });
    expect(screen.getByText(/2 observed tracks/)).toBeTruthy();
  });
});
