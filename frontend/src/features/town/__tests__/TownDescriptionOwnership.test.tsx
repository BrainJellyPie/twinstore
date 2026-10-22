// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import * as api from "@/shared/api/client";
import { TownPage } from "../TownPage";
import { useAssistStore } from "@/stores/assistStore";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getTown: vi.fn(), getTownDemand: vi.fn(), getScenarios: vi.fn(), describeTown: vi.fn(), generateTown: vi.fn(),
}));
vi.mock("../TownMap", () => ({ TownMap: () => null }));
vi.mock("../StorefrontCard", () => ({ StorefrontCard: () => null }));
vi.mock("../VlmSynergyDialog", () => ({ VlmSynergyDialog: () => null }));
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getTownDemand).mockImplementation(() => new Promise(() => {}));
  vi.mocked(api.getScenarios).mockResolvedValue([]);
});
afterEach(() => { useAssistStore.setState({ pending: null }); cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); vi.restoreAllMocks(); });
const RESULT = { spec: { archetype: "university" as const, size_m: 650, density: 0.8, n_competitors: 2, neighbor_categories: ["bank" as const], seed: 1, name: "Campus" }, rationale: "Old area rationale" };
function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject };
}
async function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  const root = createRootRoute({ component: () => <TownPage projectId="alpha" /> });
  const router = createRouter({ routeTree: root, history: createMemoryHistory({ initialEntries: ["/"] }) });
  await router.load();
  const view = render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByLabelText("Describe the area"); return view;
}
function begin() {
  fireEvent.change(screen.getByLabelText("Describe the area"), { target: { value: "A busy university area" } });
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
}
const EDITS = ["description", "archetype", "size", "density", "rivals", "seed", "neighbors"] as const;
function edit(kind: typeof EDITS[number]) {
  if (kind === "description") fireEvent.change(screen.getByLabelText("Describe the area"), { target: { value: "A quiet residential area" } });
  if (kind === "archetype") fireEvent.change(screen.getByLabelText("Archetype"), { target: { value: "suburban" } });
  if (kind === "size") fireEvent.change(screen.getAllByRole("slider")[0]!, { target: { value: "1200" } });
  if (kind === "density") fireEvent.change(screen.getAllByRole("slider")[1]!, { target: { value: "0.2" } });
  if (kind === "rivals") fireEvent.change(screen.getByPlaceholderText("auto"), { target: { value: "9" } });
  if (kind === "seed") fireEvent.change(screen.getAllByRole("spinbutton")[1]!, { target: { value: "17" } });
  if (kind === "neighbors") fireEvent.click(screen.getByRole("button", { name: "Café" }));
}
const values = () => Array.from(document.querySelectorAll('select, input, textarea')).map((node) => (node as HTMLInputElement).value);

it.each(EDITS)("preserves a newer %s when a description finishes late", async (kind) => {
  const request = deferred<typeof RESULT>(); vi.mocked(api.describeTown).mockReturnValue(request.promise);
  await mount(); begin(); await waitFor(() => expect(api.describeTown).toHaveBeenCalledTimes(1));
  edit(kind); const expected = values();
  await act(async () => { request.resolve(RESULT); await request.promise; });
  expect(values()).toEqual(expected); expect(screen.queryByText(/Old area rationale/)).toBeNull();
  expect(api.generateTown).not.toHaveBeenCalled();
});

it.each(["description", "density"] as const)("preserves a newer %s after a routed description finishes late", async (kind) => {
  const request = deferred<typeof RESULT>(); vi.mocked(api.describeTown).mockReturnValue(request.promise);
  const text = "a".repeat(799) + "🛒x";
  useAssistStore.getState().send({ projectId: "alpha", destination: "area", text });
  await mount();
  await waitFor(() => expect(api.describeTown).toHaveBeenCalledTimes(1));
  expect(api.describeTown).toHaveBeenCalledWith("alpha", { text: "a".repeat(799) + "🛒", seed: 1 });
  edit(kind); const expected = values();
  await act(async () => { request.resolve(RESULT); await request.promise; });
  expect(values()).toEqual(expected); expect(screen.queryByText(/Old area rationale/)).toBeNull();
  expect(api.generateTown).not.toHaveBeenCalled();
});

it.each(EDITS)("ignores an old failure after changing %s", async (kind) => {
  const request = deferred<typeof RESULT>(); vi.mocked(api.describeTown).mockReturnValue(request.promise);
  await mount(); begin(); await waitFor(() => expect(api.describeTown).toHaveBeenCalledTimes(1)); edit(kind);
  await act(async () => request.reject(new Error("Old area failed")));
  expect(screen.queryByText("Old area failed")).toBeNull();
  expect((screen.getByRole("button", { name: "Set up" }) as HTMLButtonElement).disabled).toBe(false);
});

it.each(["사람이 많은 대학가", "人の多い大学の周辺", "繁忙的大学附近", "A busy university area", "Una zona universitaria", "Un quartier universitaire"])("preserves composition Enter: %s", async (text) => {
  vi.mocked(api.describeTown).mockResolvedValue(RESULT); await mount(); const input = screen.getByLabelText("Describe the area");
  fireEvent.change(input, { target: { value: text } });
  for (const flags of [{ isComposing: true }, { keyCode: 229 }]) {
    const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true, ...flags });
    fireEvent(input, event); expect(event.defaultPrevented).toBe(false);
  }
  await act(async () => {}); expect(api.describeTown).not.toHaveBeenCalled(); expect(api.generateTown).not.toHaveBeenCalled();
});

it.each(["a".repeat(799) + "🛒", "a".repeat(799) + "🛒x", "𠮷".repeat(802)])("preserves complete Unicode characters at the description limit", async (text) => {
  await mount(); const input = screen.getByLabelText("Describe the area"); fireEvent.change(input, { target: { value: text } });
  expect((input as HTMLTextAreaElement).value).toBe(text.startsWith("a") ? "a".repeat(799) + "🛒" : "𠮷".repeat(800));
});
it("does not send a description shorter than the server's five-character minimum", async () => {
  await mount(); fireEvent.change(screen.getByLabelText("Describe the area"), { target: { value: "🛒".repeat(4) } });
  expect((screen.getByRole("button", { name: "Set up" }) as HTMLButtonElement).disabled).toBe(true);
});

it("applies only the newest of two requests completed in reverse order", async () => {
  const old = deferred<typeof RESULT>(); const current = deferred<typeof RESULT>();
  vi.mocked(api.describeTown).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  await mount(); begin(); await waitFor(() => expect(api.describeTown).toHaveBeenCalledTimes(1)); edit("description");
  fireEvent.click(screen.getByRole("button", { name: "Set up" })); await waitFor(() => expect(api.describeTown).toHaveBeenCalledTimes(2));
  await act(async () => { current.resolve({ ...RESULT, spec: { ...RESULT.spec, size_m: 1400 } }); await current.promise; });
  await act(async () => { old.resolve(RESULT); await old.promise; });
  expect((screen.getAllByRole("slider")[0] as HTMLInputElement).value).toBe("1400");
});

it.each([[200, 0], [250, 0.01], [650, 0.83], [2050, 0.99], [2950, 0.5], [3000, 1]])(
  "represents a described size of %s and density of %s without rounding or clipping",
  async (size, density) => {
    vi.mocked(api.describeTown).mockResolvedValue({ ...RESULT, spec: { ...RESULT.spec, size_m: size!, density: density! } });
    await mount(); begin();
    await screen.findByText(/Old area rationale/);
    const sliders = screen.getAllByRole("slider") as HTMLInputElement[];
    expect(Number(sliders[0]!.value)).toBe(size);
    expect(Number(sliders[1]!.value)).toBe(density);
    expect(sliders[0]!.validity.valid).toBe(true);
    expect(sliders[1]!.validity.valid).toBe(true);
    expect(api.generateTown).not.toHaveBeenCalled();
  },
);
it("keeps a newer routed description while the previous request is pending",async()=>{
 const old=deferred<typeof RESULT>(),current=deferred<typeof RESULT>();vi.mocked(api.describeTown).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
 await mount();act(()=>useAssistStore.getState().send({projectId:"alpha",destination:"area",text:"An older busy university area"}));await waitFor(()=>expect(api.describeTown).toHaveBeenCalledTimes(1));
 act(()=>useAssistStore.getState().send({projectId:"alpha",destination:"area",text:"A newer quiet residential area"}));await waitFor(()=>expect(api.describeTown).toHaveBeenCalledTimes(2));
 await act(async()=>{current.resolve({...RESULT,spec:{...RESULT.spec,size_m:1400},rationale:"Current routed rationale"});await current.promise;});await screen.findByText(/Current routed rationale/);
 await act(async()=>{old.resolve(RESULT);await old.promise;});await waitFor(()=>expect(clients[0]!.isMutating()).toBe(0));
 expect((screen.getAllByRole("slider")[0] as HTMLInputElement).value).toBe("1400");expect(screen.getByText(/Current routed rationale/)).toBeTruthy();expect(api.generateTown).not.toHaveBeenCalled();
});
