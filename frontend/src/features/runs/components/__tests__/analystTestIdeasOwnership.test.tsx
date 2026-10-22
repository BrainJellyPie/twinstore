// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/interview";
import { RunAnalystSection } from "../RunAnalystSection";
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@/shared/api/interview", async original => ({ ...await original<typeof import("@/shared/api/interview")>(), getAnalyst: vi.fn(), suggestTests: vi.fn() }));
let client: QueryClient;
const thread: api.AnalystThread = { run_id: "r", model: "test", messages: [
  { role: "user", text: "Old question", figures: [], follow_ups: [], created_at: "old" },
  { role: "analyst", text: "Old answer", figures: [], follow_ups: [], created_at: "old" },
] };
beforeEach(() => { client = new QueryClient({ defaultOptions: { queries: { retry: false } } });vi.mocked(api.getAnalyst).mockResolvedValue(thread); });
afterEach(() => { cleanup();client.clear();vi.resetAllMocks(); });
it.each([false,true])("drops test ideas when another tab replaces the same-size analyst thread (pending=%s)", async pending => {
  let resolve!: (ideas: api.TestIdea[]) => void;
  vi.mocked(api.suggestTests).mockReturnValue(new Promise(yes => { resolve=yes; }));
  render(<QueryClientProvider client={client}><RunAnalystSection projectId="p" runId="r" /></QueryClientProvider>);
  await screen.findByText("Old answer");fireEvent.click(screen.getByRole("button", { name:"Turn this into tests" }));
  const ideas: api.TestIdea[] = [{ question:"Test for the old answer",kind:"ab_test",why:"Old evidence" }];
  if(!pending){ await act(async()=>resolve(ideas));await screen.findByText("Test for the old answer"); }
  act(()=>client.setQueryData(api.analystKey("p","r"),{...thread,messages:thread.messages.map(m=>({...m,text:m.role==="user"?"Current question":"Current answer",created_at:"new"}))}));
  await screen.findByText("Current answer");
  if(pending)await act(async()=>resolve(ideas));
  expect(screen.queryByText("Test for the old answer")).toBeNull();
  expect(screen.getByRole("button",{name:"Turn this into tests"})).toBeTruthy();
});
