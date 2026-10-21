// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { askShopper, clearInterview, getInterview, interviewKeys, type Interview, type Journey } from "@/shared/api/interview";
import { InterviewChat } from "../InterviewChat";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(),
  askShopper: vi.fn(), clearInterview: vi.fn(), getInterview: vi.fn(),
}));
vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));

const journey: Journey = {
  run_id: "r", day: 1, arrival_time: "09:00:00", leave_time: "09:01:00", engine_type: "rule_based",
  currency: "USD", total_spent: 0, units: 0, steps: [], path: [], shelves: {},
  persona: { id: "p", day: 1, identity: "Shopper", age_group: "30s", gender: "Female", description: "",
    intent: "", purpose: "", arrival_hour: 9, preferred_categories: [], budget_min: 0, budget_max: 0, behavior_tendency: "" },
};
const empty: Interview = { run_id: "r", persona_id: "p", model: "fake", messages: [] };
const answered: Interview = { ...empty, messages: [
  { role: "interviewer", text: "Why?", steps: [], created_at: "" },
  { role: "shopper", text: "I was in a hurry.", steps: [], created_at: "" },
] };

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <InterviewChat projectId="project" runId="r" journey={journey} onCite={vi.fn()} />
  </QueryClientProvider>);
  return client;
}

function ask() {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Why?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

it("keeps a new answer when an older transcript read arrives late", async () => {
  let resolveRead: (value: Interview) => void = () => {};
  vi.mocked(getInterview).mockImplementation(() => new Promise((resolve) => { resolveRead = resolve; }));
  vi.mocked(askShopper).mockResolvedValue(answered);
  const client = mount();
  ask();
  await screen.findByText("I was in a hurry.");
  await act(async () => resolveRead(empty));
  await waitFor(() => expect(client.isFetching({ queryKey: interviewKeys.interview("project", "r", "p") })).toBe(0));
  expect(screen.getByText("I was in a hurry.")).toBeTruthy();
});

it("prevents clearing the interview while a reply is pending", async () => {
  vi.mocked(getInterview).mockResolvedValue(answered);
  vi.mocked(askShopper).mockImplementation(() => new Promise(() => {}));
  mount();
  await screen.findByText("I was in a hurry.");
  ask();
  await waitFor(() => expect(askShopper).toHaveBeenCalled());
  const reset = screen.getByRole("button", { name: "Start over" }) as HTMLButtonElement;
  expect(reset.disabled).toBe(true);
  fireEvent.click(reset);
  expect(clearInterview).not.toHaveBeenCalled();
});

it("prevents new questions while clearing the interview", async () => {
  vi.mocked(getInterview).mockResolvedValue(answered);
  vi.mocked(clearInterview).mockImplementation(() => new Promise(() => {}));
  mount();
  await screen.findByText("I was in a hurry.");
  fireEvent.click(screen.getByRole("button", { name: "Start over" }));
  await waitFor(() => expect(clearInterview).toHaveBeenCalled());
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Why?" } });
  const suggestion = screen.getByRole("button", { name: "How did the prices feel to you today?" }) as HTMLButtonElement;
  expect(suggestion.disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Ask" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(suggestion);
  await act(async () => fireEvent.submit(screen.getByRole("textbox").closest("form")!));
  expect(askShopper).not.toHaveBeenCalled();
});
