// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { OptimizeDialog } from "../OptimizeDialog";
vi.mock("@/shared/api/client", () => ({ getScenarios: vi.fn(), startOptimization: vi.fn(), getOptimization: vi.fn(), readOptimizeGoal: vi.fn(), applyOptimization: vi.fn(), cancelOptimization: vi.fn(), getModels: vi.fn() }));
vi.mock("../../hooks", () => ({ useAvailableModels: () => ({ data: [], isError: false }) }));
vi.mock("../ModelPicker", () => ({ ModelPicker: () => null }));
let client: QueryClient;
beforeEach(() => { client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });vi.mocked(api.getScenarios).mockResolvedValue([]); });
afterEach(() => { cleanup();client.clear();vi.resetAllMocks(); });
const goal: api.OptimizeGoal = { objective: "impulse_revenue", scope: "both", max_moves: 5, keep_fridges_on_walls: false, lock_rack_ids: ["old_rack"], locked: ["Old rack"], min_improvement: 0.02, rationale: "Old goal rationale", warnings: [] };
function deferred() {
  let resolve!: (value: api.OptimizeGoal) => void, reject!: (error: Error) => void;
  return { promise: new Promise<api.OptimizeGoal>((yes,no) => { resolve=yes;reject=no; }), resolve: (value = goal) => resolve(value), reject: () => reject(new Error("Obsolete goal failure")) };
}
function tree(projectId="p",setupId="s",prefill?: {id:number;text:string}) { return <QueryClientProvider client={client}><OptimizeDialog open onOpenChange={() => {}} projectId={projectId} setupId={setupId} goalPrefill={prefill} /></QueryClientProvider>; }
function ask(text="More impulse purchases") { fireEvent.change(screen.getByLabelText("Optimization goal"),{target:{value:text}});fireEvent.click(screen.getByRole("button",{name:"Set up"})); }
const changes=["text","clear","objective","scope","moves","walls","algorithm","budget","customers","judge","project","layout"];
it.each(changes)("does not replace current settings after changing %s", async change => {
  const pending=deferred();vi.mocked(api.readOptimizeGoal).mockReturnValue(pending.promise);
  const view=render(tree());ask();await waitFor(()=>expect(api.readOptimizeGoal).toHaveBeenCalled());
  if(change==="text"||change==="clear")fireEvent.change(screen.getByLabelText("Optimization goal"),{target:{value:change==="clear"?"":"Current goal"}});
  if(change==="objective")fireEvent.change(screen.getByLabelText("Improve"),{target:{value:"conversion_rate"}});
  if(change==="scope")fireEvent.click(screen.getByRole("button",{name:/Rack positions Racks|Rack positions Move/}));
  if(change==="moves")fireEvent.change(screen.getByLabelText("Max. changes"),{target:{value:"12"}});
  if(change==="walls")fireEvent.click(screen.getByLabelText("Fridges stay on walls"));
  if(change==="algorithm")fireEvent.change(screen.getByLabelText("Search method"),{target:{value:"anneal"}});
  if(change==="budget")fireEvent.change(screen.getByLabelText("Candidates to try"),{target:{value:"120"}});
  if(change==="customers")fireEvent.change(screen.getByLabelText("Shoppers per candidate"),{target:{value:"500"}});
  if(change==="judge")fireEvent.click(screen.getByRole("button",{name:/Vision shoppers decide/}));
  if(change==="project")view.rerender(tree("new","s"));
  if(change==="layout")view.rerender(tree("p","new"));
  const objective=(screen.getByLabelText("Improve") as HTMLSelectElement).value,moves=(screen.getByLabelText("Max. changes") as HTMLInputElement).value;
  await act(async()=>pending.resolve());await waitFor(()=>expect(client.isMutating()).toBe(0));
  expect((screen.getByLabelText("Improve") as HTMLSelectElement).value).toBe(objective);expect((screen.getByLabelText("Max. changes") as HTMLInputElement).value).toBe(moves);
  expect(screen.queryByText("Old rack")).toBeNull();expect(screen.queryByText(/Old goal rationale/)).toBeNull();
});
it("keeps a newer routed goal when responses arrive in reverse order",async()=>{
  const old=deferred(),current=deferred();vi.mocked(api.readOptimizeGoal).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  const view=render(tree("p","s",{id:1,text:"Old goal"}));await waitFor(()=>expect(api.readOptimizeGoal).toHaveBeenCalledTimes(1));
  view.rerender(tree("p","s",{id:2,text:"Current goal"}));await waitFor(()=>expect(api.readOptimizeGoal).toHaveBeenCalledTimes(2));
  await act(async()=>current.resolve({...goal,objective:"conversion_rate",rationale:"Current rationale"}));await screen.findByText(/Current rationale/);
  await act(async()=>old.resolve());await waitFor(()=>expect(client.isMutating()).toBe(0));
  expect((screen.getByLabelText("Improve") as HTMLSelectElement).value).toBe("conversion_rate");expect(screen.queryByText(/Old goal rationale/)).toBeNull();
});
it("keeps starting disabled until the requested goal has been read",async()=>{
  const pending=deferred();vi.mocked(api.readOptimizeGoal).mockReturnValue(pending.promise);render(tree());ask();
  await waitFor(()=>expect((screen.getByRole("button",{name:"Start"}) as HTMLButtonElement).disabled).toBe(true));
  await act(async()=>pending.resolve());await screen.findByText(/Old goal rationale/);expect((screen.getByRole("button",{name:"Start"}) as HTMLButtonElement).disabled).toBe(false);
});
it("drops a failed reading after editing the goal",async()=>{
  const pending=deferred();vi.mocked(api.readOptimizeGoal).mockReturnValue(pending.promise);render(tree());ask();
  fireEvent.change(screen.getByLabelText("Optimization goal"),{target:{value:"Revised goal"}});await act(async()=>pending.reject());await waitFor(()=>expect(client.isMutating()).toBe(0));expect(screen.queryByText("Obsolete goal failure")).toBeNull();
});
