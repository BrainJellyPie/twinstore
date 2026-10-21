// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { deleteStudyReading, getStudyReading, writeStudyReading, studyReadingKey, type StudyPath, type StudyReading as Reading } from "@/shared/api/marketing";
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


const original = { projectId: "p", study: "shelf-tests" as StudyPath, jobId: "first", answers: 7 };
function mount(props = original, cached = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  if (cached) client.setQueryData(studyReadingKey(props.projectId, props.study, props.jobId), READING);
  const view = render(<QueryClientProvider client={client}><StudyReading {...props} /></QueryClientProvider>);
  return { client, change: (next: typeof props) => view.rerender(<QueryClientProvider client={client}><StudyReading {...next} /></QueryClientProvider>) };
}
const changed = [{ ...original, projectId: "other" }, { ...original, study: "surveys" as StudyPath }, { ...original, jobId: "second" }];
const destination = { ...READING, summary: "The destination reading stays here." };
const rewritten = { ...READING, summary: "The first reading was rewritten." };

it.each(changed)("keeps a late rewrite in its own study after navigation: %j", async next => {
  let finish!: (value: Reading) => void;
  vi.mocked(getStudyReading).mockResolvedValueOnce(READING).mockResolvedValue(destination);
  vi.mocked(writeStudyReading).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const { client, change } = mount(); fireEvent.click(await screen.findByRole("button", { name: "Rewrite" }));
  await waitFor(() => expect(writeStudyReading).toHaveBeenCalled()); change(next); await screen.findByText(destination.summary);
  expect((screen.getByRole("button", { name: "Rewrite" }) as HTMLButtonElement).disabled).toBe(false);
  await act(async () => finish(rewritten)); await waitFor(() => expect(client.isMutating()).toBe(0));
  expect(screen.getByText(destination.summary)).toBeTruthy();
  expect(client.getQueryData(studyReadingKey("p", "shelf-tests", "first"))).toEqual(rewritten);
  expect(client.getQueryData(studyReadingKey(next.projectId, next.study, next.jobId))).toEqual(destination);
});

it.each(changed)("keeps a late removal in its own study after navigation: %j", async next => {
  let finish!: () => void;
  vi.mocked(getStudyReading).mockResolvedValueOnce(READING).mockResolvedValue(destination);
  vi.mocked(deleteStudyReading).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const { client, change } = mount(); fireEvent.click(await screen.findByRole("button", { name: "Remove the reading" }));
  await waitFor(() => expect(deleteStudyReading).toHaveBeenCalled()); change(next); await screen.findByText(destination.summary);
  await act(async () => finish()); await waitFor(() => expect(client.isMutating()).toBe(0));
  expect(screen.getByText(destination.summary)).toBeTruthy();
  expect(client.getQueryData(studyReadingKey("p", "shelf-tests", "first"))).toBeNull();
  expect(client.getQueryData(studyReadingKey(next.projectId, next.study, next.jobId))).toEqual(destination);
});

it.each(["rewrite", "remove"])("keeps the completed %s when a cached reading refetch arrives late", async action => {
  let finish!: (value: Reading) => void;
  vi.mocked(getStudyReading).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  vi.mocked(writeStudyReading).mockResolvedValue(rewritten); vi.mocked(deleteStudyReading).mockResolvedValue(undefined);
  const { client } = mount(original, true); await waitFor(() => expect(getStudyReading).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: action === "rewrite" ? "Rewrite" : "Remove the reading" }));
  if (action === "rewrite") await screen.findByText(rewritten.summary);
  else await screen.findByRole("button", { name: "Read the answers" });
  await act(async () => finish(READING)); await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(screen.queryByText(READING.summary)).toBeNull();
});

it("recovers a failed reading load before offering to replace the saved result", async () => {
  vi.mocked(getStudyReading).mockRejectedValueOnce(new Error("Saved reading unavailable")).mockResolvedValue(READING);
  mount(); expect((await screen.findByRole("alert")).textContent).toContain("Saved reading unavailable");
  expect(screen.queryByRole("button", { name: "Read the answers" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry loading reading" })); await screen.findByText(READING.summary);
  expect(writeStudyReading).not.toHaveBeenCalled();
});

it.each(changed)("keeps a previous study's late failure out of the destination: %j", async next => {
  let fail!: (error: Error) => void;
  vi.mocked(getStudyReading).mockResolvedValueOnce(READING).mockResolvedValue(destination);
  vi.mocked(writeStudyReading).mockImplementation(() => new Promise((_resolve, reject) => { fail = reject; }));
  const { client, change } = mount(); fireEvent.click(await screen.findByRole("button", { name: "Rewrite" }));
  await waitFor(() => expect(writeStudyReading).toHaveBeenCalled()); change(next); await screen.findByText(destination.summary);
  await act(async () => fail(new Error("Previous study failed"))); await waitFor(() => expect(client.isMutating()).toBe(0));
  expect(screen.queryByText("Previous study failed")).toBeNull(); expect(screen.getByText(destination.summary)).toBeTruthy();
});

it("preserves a cached reading when a background load fails and allows retry", async () => {
  vi.mocked(getStudyReading).mockResolvedValueOnce(READING).mockRejectedValueOnce(new Error("Refresh unavailable")).mockResolvedValue(rewritten);
  const { client } = mount(); await screen.findByText(READING.summary);
  await act(async () => { await client.invalidateQueries({ queryKey: studyReadingKey("p", "shelf-tests", "first"), exact: true }); });
  expect((await screen.findByRole("alert")).textContent).toContain("Refresh unavailable"); expect(screen.getByText(READING.summary)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Retry loading reading" })); await screen.findByText(rewritten.summary);
});
