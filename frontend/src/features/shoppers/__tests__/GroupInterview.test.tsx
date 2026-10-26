// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { askGroup, deleteGroup, listGroups, suggestGroupQuestions, type GroupAnswer, type GroupInterview } from "@/shared/api/interview";
import { GroupInterviewPanel } from "../GroupInterview";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(), listGroups: vi.fn(), askGroup: vi.fn(), deleteGroup: vi.fn(), suggestGroupQuestions: vi.fn(),
}));
vi.mock("@/shared/api/client", () => ({
  BASE: "", getModels: vi.fn().mockResolvedValue([]),
  // A provider is set up, so no "needs a model" hint shows.
  getModelSetup: vi.fn().mockResolvedValue({ cloud_providers: ["openai"], local: { state: "off" } }),
  startLocalModel: vi.fn(), stopLocalModel: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const answer = (id: string, theme: number): GroupAnswer => ({
  persona_id: id, identity: id, age_group: "20s", gender: "Female", spent: 0, units: 0,
  answer: `${id} response`, steps: [], theme, error: "",
});
const first: GroupInterview = {
  group_id: "first", run_id: "r", question: "First question", segment: "all", model: "fake", created_at: "", errors: 0,
  answers: [answer("A", 0), answer("B", 1)],
  themes: [{ label: "Price", count: 1, share: 0.5 }, { label: "Selection", count: 1, share: 0.5 }],
};
const second: GroupInterview = {
  ...first, group_id: "second", question: "Second question", answers: [answer("C", 0)],
  themes: [{ label: "Location", count: 1, share: 1 }],
};

it("clears the theme filter when switching to a different group interview", async () => {
  vi.mocked(listGroups).mockResolvedValue([first, second]);
  render(<QueryClientProvider client={new QueryClient()}>
    <GroupInterviewPanel projectId="project" runId="r" currency="USD" onOpen={vi.fn()} onBack={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: /^First question/ }));
  fireEvent.click(screen.getByRole("button", { name: /^Selection/ }));
  expect(screen.queryByText("A response")).toBeNull();
  expect(screen.getByText("B response")).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: /^Second question/ }));

  expect(screen.getByText("C response")).toBeTruthy();
});


it("suggests questions from the run and fills in the question and group", async () => {
  vi.mocked(listGroups).mockResolvedValue([]);
  vi.mocked(suggestGroupQuestions).mockResolvedValue([
    { question: "Why did you stop at the snacks but not buy?", segment: "empty_handed", why: "many stops, few buys" },
    { question: "What made you grab the jerky?", segment: "impulse", why: "top impulse pick" },
  ]);
  vi.mocked(askGroup).mockImplementation(() => new Promise(() => {}));
  render(<QueryClientProvider client={new QueryClient()}>
    <GroupInterviewPanel projectId="project" runId="r" currency="USD" onOpen={vi.fn()} onBack={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Suggest questions from this run" }));
  fireEvent.click(await screen.findByRole("button", { name: /What made you grab the jerky\?/ }));
  expect((screen.getByLabelText("Question") as HTMLTextAreaElement).value).toBe("What made you grab the jerky?");
  expect(screen.getByText("Impulse buyers · top impulse pick")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /^Ask / }));
  await waitFor(() => expect(askGroup).toHaveBeenCalledWith("project", "r", expect.objectContaining({ question: "What made you grab the jerky?", segment: "impulse" })));
});

it("asks before deleting a group interview and deletes it on the second click", async () => {
  vi.mocked(listGroups).mockResolvedValue([first]);
  vi.mocked(deleteGroup).mockResolvedValue(undefined);
  render(<QueryClientProvider client={new QueryClient()}>
    <GroupInterviewPanel projectId="project" runId="r" currency="USD" onOpen={vi.fn()} onBack={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Delete group interview" }));
  expect(deleteGroup).not.toHaveBeenCalled();
  fireEvent.blur(screen.getByRole("button", { name: "Delete?" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete group interview" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete?" }));
  await waitFor(() => expect(deleteGroup).toHaveBeenCalledWith("project", "r", "first"));
});
