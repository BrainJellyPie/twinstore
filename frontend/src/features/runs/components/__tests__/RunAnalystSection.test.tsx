// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { askAnalyst, clearAnalyst, getAnalyst, type AnalystThread } from "@/shared/api/interview";
import { RunAnalystSection } from "../RunAnalystSection";
import { useAssistStore } from "@/stores/assistStore";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(), getAnalyst: vi.fn(), askAnalyst: vi.fn(), clearAnalyst: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); useAssistStore.setState({ pending: null }); });

const empty: AnalystThread = { run_id: "r", model: "", messages: [] };
const answered: AnalystThread = { run_id: "r", model: "m", messages: [
  { role: "user", text: "Which shelf converts worst?", figures: [], follow_ups: [], created_at: "" },
  { role: "analyst", text: "Ice cream 1: under half of those who stop buy.", figures: ["Ice cream 1 274 / 120"],
    follow_ups: ["Why do shoppers leave the freezer empty-handed?"], created_at: "" },
] };

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <RunAnalystSection projectId="p" runId="r" />
  </QueryClientProvider>);
}

it("starts from suggested questions and shows the answer with the figures it used", async () => {
  vi.mocked(getAnalyst).mockResolvedValue(empty);
  vi.mocked(askAnalyst).mockResolvedValue(answered);
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Which shelf converts worst, and why might that be?" }));
  expect(await screen.findByText("Ice cream 1: under half of those who stop buy.")).toBeTruthy();
  expect(askAnalyst).toHaveBeenCalledWith("p", "r", "Which shelf converts worst, and why might that be?");
  expect(screen.getByRole("list", { name: "Figures used" }).textContent).toContain("Ice cream 1 274 / 120");
  // The analyst's own follow-ups replace the starters.
  expect(screen.getByRole("button", { name: "Why do shoppers leave the freezer empty-handed?" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Which shoppers spend the most per visit?" })).toBeNull();
});

it("asks a typed question and clears the thread", async () => {
  vi.mocked(getAnalyst).mockResolvedValue(answered);
  vi.mocked(askAnalyst).mockImplementation(() => new Promise(() => {}));
  vi.mocked(clearAnalyst).mockResolvedValue(undefined);
  mount();
  fireEvent.change(await screen.findByLabelText("Question about this run"), { target: { value: "Busiest hour?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(askAnalyst).toHaveBeenCalledWith("p", "r", "Busiest hour?"));
  expect(screen.getByText("Reading the run…")).toBeTruthy();
});

it("asks a question routed from the command palette once, for its own project only", async () => {
  vi.mocked(getAnalyst).mockResolvedValue(empty);
  vi.mocked(askAnalyst).mockResolvedValue(answered);
  useAssistStore.getState().send({ projectId: "other", destination: "run_question", text: "Not for this store" });
  useAssistStore.getState().send({ projectId: "p", destination: "run_question", text: "Why is the freezer so quiet?" });
  mount();
  await waitFor(() => expect(askAnalyst).toHaveBeenCalledWith("p", "r", "Why is the freezer so quiet?"));
  expect(await screen.findByText("Ice cream 1: under half of those who stop buy.")).toBeTruthy();
  expect(askAnalyst).toHaveBeenCalledTimes(1);
  expect(useAssistStore.getState().pending).toBeNull();
});
