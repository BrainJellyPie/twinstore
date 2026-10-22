// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { suggestTests } from "@/shared/api/interview";
import { useAssistStore } from "@/stores/assistStore";
import { TestIdeas } from "../TestIdeas";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => navigate }));
vi.mock("@/shared/api/interview", async (original) => ({ ...await original<typeof import("@/shared/api/interview")>(), suggestTests: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); useAssistStore.setState({ pending: null }); });

it("turns what shoppers said into tests and opens the picked one as a draft", async () => {
  vi.mocked(suggestTests).mockResolvedValue([
    { question: "Would 20 % off Ice cream 1 sell more than today's price?", kind: "ab_test", why: "prices felt high" },
    { question: "Does a SALE sign make the ice cream stand out?", kind: "shelf_test", why: "hard to find" },
  ]);
  render(<TestIdeas projectId="p" runId="r" source="group" groupId="grp_1" />);
  fireEvent.click(screen.getByRole("button", { name: "Turn this into tests" }));
  const shelf = await screen.findByRole("button", { name: /Does a SALE sign make the ice cream stand out\?/ });
  expect(suggestTests).toHaveBeenCalledWith("p", "r", { source: "group", group_id: "grp_1" });
  expect(shelf.textContent).toContain("Shelf test · hard to find");
  fireEvent.click(shelf);
  expect(useAssistStore.getState().pending).toMatchObject({ projectId: "p", destination: "shelf_test", text: "Does a SALE sign make the ice cream stand out?" });
  await waitFor(() => expect(navigate).toHaveBeenCalledWith({ to: "/marketing/$pid", params: { pid: "p" } }));
});

it("asks for tests from the analyst's answer and says when nothing points to one", async () => {
  vi.mocked(suggestTests).mockResolvedValue([]);
  render(<TestIdeas projectId="p" runId="r" source="analyst" />);
  fireEvent.click(screen.getByRole("button", { name: "Turn this into tests" }));
  expect(await screen.findByText("Nothing here points to a test yet.")).toBeTruthy();
  expect(suggestTests).toHaveBeenCalledWith("p", "r", { source: "analyst" });
});
