// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { deleteStudyReading, getStudyReading, writeStudyReading, type StudyReading as Reading } from "@/shared/api/marketing";
import { StudyReading } from "../StudyReading";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  getModels: vi.fn().mockResolvedValue([{ ref: "anthropic:claude-haiku-5-5", label: "Claude Haiku 5.5" }]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(),
  getStudyReading: vi.fn(), writeStudyReading: vi.fn(), deleteStudyReading: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const READING: Reading = {
  summary: "The new pack lifts picks.", interpretation: "People notice it.", next_steps: "Test the price next.",
  themes_question: "Why?", answers_coded: 7, groups: ["control", "test"], model: "anthropic:claude-haiku-5-5", created_at: "",
  themes: [
    { label: "Bright new pack", count: 4, share: 4 / 7, by_group: { control: 1, test: 3 }, examples: ["Loved the new pack."] },
    { label: "Usual brand", count: 3, share: 3 / 7, by_group: { control: 2, test: 1 }, examples: [] },
  ],
};

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><StudyReading projectId="p" study="shelf-tests" jobId="slf_1" answers={7} /></QueryClientProvider>);
}

it("offers to read the answers, then shows the commentary and themes split by arm", async () => {
  vi.mocked(getStudyReading).mockResolvedValue(null);
  vi.mocked(writeStudyReading).mockResolvedValue(READING);
  mount();
  expect(await screen.findByText(/groups the 7 reasons respondents gave into themes/)).toBeTruthy();
  await screen.findByRole("option", { name: "Claude Haiku 5.5" });
  fireEvent.change(screen.getByLabelText("Model for the reading"), { target: { value: "anthropic:claude-haiku-5-5" } });
  fireEvent.click(screen.getByRole("button", { name: "Read the answers" }));
  expect(await screen.findByText("The new pack lifts picks.")).toBeTruthy();
  expect(writeStudyReading).toHaveBeenCalledWith("p", "shelf-tests", "slf_1", "anthropic:claude-haiku-5-5");
  expect(screen.getByText(/written by Claude Haiku 5.5/)).toBeTruthy();
  expect(screen.getByText("Bright new pack")).toBeTruthy();
  expect(screen.getByText("“Loved the new pack.”")).toBeTruthy();
  // Each arm's bar is that arm's share of its own reasons: test 3 of 4, control 1 of 3.
  expect(screen.getByTitle("test: 3 of 4 reasons")).toBeTruthy();
  expect(screen.getByTitle("control: 1 of 3 reasons")).toBeTruthy();
});

it("removes a reading and shows the offer again", async () => {
  vi.mocked(getStudyReading).mockResolvedValue(READING);
  vi.mocked(deleteStudyReading).mockResolvedValue(undefined);
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Remove the reading" }));
  await waitFor(() => expect(deleteStudyReading).toHaveBeenCalledWith("p", "shelf-tests", "slf_1"));
  expect(await screen.findByRole("button", { name: "Read the answers" })).toBeTruthy();
});

it("shows why a reading could not be written", async () => {
  vi.mocked(getStudyReading).mockResolvedValue(null);
  vi.mocked(writeStudyReading).mockRejectedValue(new Error("The reading could not be written: the model took too long to reply. Try again."));
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Read the answers" }));
  expect((await screen.findByRole("alert")).textContent).toContain("took too long");
});
