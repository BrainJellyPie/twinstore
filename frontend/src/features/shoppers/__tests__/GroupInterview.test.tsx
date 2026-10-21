// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { listGroups, type GroupAnswer, type GroupInterview } from "@/shared/api/interview";
import { GroupInterviewPanel } from "../GroupInterview";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(), listGroups: vi.fn(), askGroup: vi.fn(), deleteGroup: vi.fn(),
}));
vi.mock("@/shared/api/client", () => ({ BASE: "", getModels: vi.fn().mockResolvedValue([]) }));
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
