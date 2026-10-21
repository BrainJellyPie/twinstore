// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { getInterview, interviewKeys, suggestQuestions, type Interview, type Journey } from "@/shared/api/interview";
import { InterviewChat } from "../InterviewChat";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(),
  askShopper: vi.fn(), clearInterview: vi.fn(), getInterview: vi.fn(), suggestQuestions: vi.fn(),
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
  vi.mocked(suggestQuestions).mockRejectedValue(new Error("no model"));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <InterviewChat projectId="project" runId="r" journey={journey} onCite={vi.fn()} />
  </QueryClientProvider>);
  return client;
}


const restarted: Interview = { ...answered, messages: [
  { role: "interviewer", text: "What mattered this time?", steps: [], created_at: "later" },
  { role: "shopper", text: "The price mattered.", steps: [], created_at: "later" },
] };
const oldIdeas: Interview = { ...answered, suggestions: ["Why were you in a hurry?"], suggested_after: 2 };
const freshIdeas: Interview = { ...restarted, suggestions: ["Which price felt too high?"], suggested_after: 2 };

it("does not reuse cached follow-ups for a different conversation of the same length", async () => {
  vi.mocked(getInterview).mockResolvedValue(answered);
  vi.mocked(suggestQuestions).mockResolvedValueOnce(oldIdeas).mockImplementation(() => new Promise(() => {}));
  const client = mount(); await screen.findByRole("button", { name: "Why were you in a hurry?" });
  act(() => client.setQueryData(interviewKeys.interview("project", "r", "p"), restarted));
  await screen.findByText("The price mattered.");
  await waitFor(() => expect(screen.queryByRole("button", { name: "Why were you in a hurry?" })).toBeNull());
  expect(suggestQuestions).toHaveBeenCalledTimes(2);
});

it("ignores late suggestions for an earlier conversation with the same number of messages", async () => {
  let release!: (value: Interview) => void;
  vi.mocked(getInterview).mockResolvedValue(answered);
  vi.mocked(suggestQuestions).mockImplementationOnce(() => new Promise(resolve => { release = resolve; })).mockResolvedValue(freshIdeas);
  const client = mount(); await waitFor(() => expect(suggestQuestions).toHaveBeenCalledOnce());
  act(() => client.setQueryData(interviewKeys.interview("project", "r", "p"), restarted));
  await act(async () => release(oldIdeas));
  await screen.findByRole("button", { name: "Which price felt too high?" });
  expect(screen.queryByRole("button", { name: "Why were you in a hurry?" })).toBeNull();
});

it.each([empty, answered])("keeps trip-based suggestions when all model suggestions were filtered out: $messages.length messages", async current => {
  vi.mocked(getInterview).mockResolvedValue(current);
  vi.mocked(suggestQuestions).mockResolvedValue({ ...current, suggestions: [], suggested_after: current.messages.length });
  mount(); await waitFor(() => expect(suggestQuestions).toHaveBeenCalled());
  expect(await screen.findByRole("button", { name: "How did the prices feel to you today?" })).toBeTruthy();
});

it.each([
  { current: answered, response: freshIdeas, unexpected: "Which price felt too high?" },
  { current: restarted, response: oldIdeas, unexpected: "Why were you in a hurry?" },
])("does not display a response for a different conversation: $unexpected", async ({ current, response, unexpected }) => {
  vi.mocked(getInterview).mockResolvedValue(current);
  vi.mocked(suggestQuestions).mockResolvedValue(response);
  const client = mount();
  await waitFor(() => expect(suggestQuestions).toHaveBeenCalled());
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(screen.queryByRole("button", { name: unexpected })).toBeNull();
  expect(screen.getByRole("button", { name: "How did the prices feel to you today?" })).toBeTruthy();
});
