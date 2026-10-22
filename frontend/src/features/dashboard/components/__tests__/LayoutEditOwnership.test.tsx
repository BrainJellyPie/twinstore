// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { applyLayoutEdit, draftLayoutEdit, type LayoutEditDraft } from "@/shared/api/marketing";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { LayoutEditInWords } from "../LayoutEditInWords";
vi.mock("@/shared/api/marketing", async original => ({
  ...await original<typeof import("@/shared/api/marketing")>(), draftLayoutEdit: vi.fn(), applyLayoutEdit: vi.fn(),
}));
const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.clearAllMocks(); useAssistStore.setState({ pending: null }); useSimulationStore.getState().setSelectedSetupId(null); });
const result: LayoutEditDraft = { source_sha256: "a".repeat(64), name: "Old suggested name", summary: "Old edit summary", changes: [{ kind: "promo", sku: "tea", promo: "SALE" }], applied: ["Tea: SALE sign"], warnings: [] };
function deferred<T>() { let resolve!: (v: T) => void, reject!: (e: Error) => void; const promise = new Promise<T>((a,b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
  let props: ComponentProps<typeof LayoutEditInWords> = { projectId: "p", setupId: "s" };
  const draw = () => <QueryClientProvider client={client}><LayoutEditInWords {...props} /></QueryClientProvider>;
  const view = render(draw());
  return { client, unmount: view.unmount, change(kind: string) {
    if (kind === "text") fireEvent.change(screen.getByLabelText("Layout changes in words"), { target: { value: "A newer instruction about coffee" } });
    if (kind === "name") fireEvent.change(screen.getByLabelText("Name of the new layout"), { target: { value: "My newer layout name" } });
    if (kind === "project") props = { ...props, projectId: "other" };
    if (kind === "layout") props = { ...props, setupId: "other" };
    view.rerender(draw());
  } };
}
function begin() { fireEvent.change(screen.getByLabelText("Layout changes in words"), { target: { value: "Add a SALE sign to the tea" } }); fireEvent.click(screen.getByRole("button", { name: "Draft the edits" })); }
it.each(["text", "project", "layout"])("drops a late draft after changing %s", async kind => {
  const pending = deferred<LayoutEditDraft>(); vi.mocked(draftLayoutEdit).mockReturnValue(pending.promise);
  const view = mount(); begin(); await waitFor(() => expect(draftLayoutEdit).toHaveBeenCalledTimes(1)); view.change(kind);
  await act(async () => { pending.resolve(result); await pending.promise; });
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(screen.queryByRole("list", { name: "Drafted edits" })).toBeNull();
});
it.each(["text", "project", "layout"])("hides an obsolete draft error after changing %s", async kind => {
  const pending = deferred<LayoutEditDraft>(); vi.mocked(draftLayoutEdit).mockReturnValue(pending.promise);
  const view = mount(); begin(); await waitFor(() => expect(draftLayoutEdit).toHaveBeenCalledTimes(1)); view.change(kind);
  await act(async () => pending.reject(new Error("Obsolete draft failure")));
  await waitFor(() => expect(view.client.isMutating()).toBe(0)); expect(screen.queryByText("Obsolete draft failure")).toBeNull();
});
it("allows a newer instruction to complete before an old draft", async () => {
  const old = deferred<LayoutEditDraft>(), current = deferred<LayoutEditDraft>();
  vi.mocked(draftLayoutEdit).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  const view = mount(); begin(); await waitFor(() => expect(draftLayoutEdit).toHaveBeenCalledTimes(1)); view.change("text");
  fireEvent.click(screen.getByRole("button", { name: "Draft the edits" })); await waitFor(() => expect(draftLayoutEdit).toHaveBeenCalledTimes(2));
  await act(async () => { current.resolve({ ...result, name: "Current name", summary: "Current summary" }); await current.promise; }); await screen.findByText("Current summary");
  await act(async () => { old.resolve(result); await old.promise; }); await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(screen.getByText("Current summary")).toBeTruthy(); expect((screen.getByLabelText("Name of the new layout") as HTMLInputElement).value).toBe("Current name");
});
it.each(["text", "name", "project", "layout", "unmount"])("does not navigate or discard newer work after save: %s", async kind => {
  vi.mocked(draftLayoutEdit).mockResolvedValue(result);
  const pending = deferred<Awaited<ReturnType<typeof applyLayoutEdit>>>(); vi.mocked(applyLayoutEdit).mockReturnValue(pending.promise);
  const view = mount(); begin(); await screen.findByRole("list", { name: "Drafted edits" });
  fireEvent.click(screen.getByRole("button", { name: "Save as a new layout" })); await waitFor(() => expect(applyLayoutEdit).toHaveBeenCalledTimes(1));
  if (kind === "unmount") view.unmount(); else view.change(kind);
  useSimulationStore.getState().setSelectedSetupId("newer-layout");
  await act(async () => { pending.resolve({ id: "saved-old", name: "Old saved", applied: result.applied, warnings: [] }); await pending.promise; });
  await waitFor(() => expect(view.client.isMutating()).toBe(0)); expect(useSimulationStore.getState().selectedSetupId).toBe("newer-layout");
  if (kind === "text") expect((screen.getByLabelText("Layout changes in words") as HTMLTextAreaElement).value).toBe("A newer instruction about coffee");
  if (kind === "name") expect((screen.getByLabelText("Name of the new layout") as HTMLInputElement).value).toBe("My newer layout name");
});
it.each(["상품 진열을 바꿔줘", "调整商品陈列位置", "商品の陳列を変更して", "Move the tea to eye level", "Mover el té al nivel de los ojos", "Déplacer le thé à hauteur des yeux"])("does not submit composition Enter: %s", async text => {
  mount(); const input=screen.getByLabelText("Layout changes in words"); fireEvent.change(input,{target:{value:text}});
  for(const flags of [{isComposing:true},{keyCode:229}])fireEvent.keyDown(input,{key:"Enter",...flags});
  await act(async()=>{});expect(draftLayoutEdit).not.toHaveBeenCalled();expect(applyLayoutEdit).not.toHaveBeenCalled();
});
it("keeps full Unicode characters in the saved layout name", async () => {
  vi.mocked(draftLayoutEdit).mockResolvedValue(result);mount();begin();const input=await screen.findByLabelText("Name of the new layout");
  fireEvent.change(input,{target:{value:"a".repeat(79)+"🛒x"}});expect((input as HTMLInputElement).value).toBe("a".repeat(79)+"🛒");
});
it.each(["text", "name", "project", "layout"])("hides an obsolete save error after changing %s", async kind => {
  vi.mocked(draftLayoutEdit).mockResolvedValue(result);
  const pending=deferred<Awaited<ReturnType<typeof applyLayoutEdit>>>();vi.mocked(applyLayoutEdit).mockReturnValue(pending.promise);
  const view=mount();begin();await screen.findByRole("list",{name:"Drafted edits"});fireEvent.click(screen.getByRole("button",{name:"Save as a new layout"}));
  await waitFor(()=>expect(applyLayoutEdit).toHaveBeenCalledTimes(1));view.change(kind);
  await act(async()=>pending.reject(new Error("Obsolete save failure")));await waitFor(()=>expect(view.client.isMutating()).toBe(0));
  expect(screen.queryByText("Obsolete save failure")).toBeNull();
});
it("retries an uncertain save with the identical reviewed snapshot and request ID", async()=>{
  vi.mocked(draftLayoutEdit).mockResolvedValue(result);
  vi.mocked(applyLayoutEdit).mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValueOnce({id:"saved",name:result.name,applied:result.applied,warnings:[]});
  const view=mount();begin();await screen.findByRole("list",{name:"Drafted edits"});
  fireEvent.click(screen.getByRole("button",{name:"Save as a new layout"}));await screen.findByText("Connection lost");
  fireEvent.click(screen.getByRole("button",{name:"Save as a new layout"}));await waitFor(()=>expect(view.client.isMutating()).toBe(0));
  expect(applyLayoutEdit).toHaveBeenCalledTimes(2);expect(vi.mocked(applyLayoutEdit).mock.calls[0]).toEqual(vi.mocked(applyLayoutEdit).mock.calls[1]);
  expect(vi.mocked(applyLayoutEdit).mock.calls[0]?.[2]).toMatchObject({source_sha256:result.source_sha256,request_id:expect.stringMatching(/^[0-9a-f]{32}$/)});
  expect(useSimulationStore.getState().selectedSetupId).toBe("saved");
});
it("invalidates the saved project's lists after navigation without changing the new selection",async()=>{
  vi.mocked(draftLayoutEdit).mockResolvedValue(result);const pending=deferred<Awaited<ReturnType<typeof applyLayoutEdit>>>();vi.mocked(applyLayoutEdit).mockReturnValue(pending.promise);
  const view=mount();const invalidate=vi.spyOn(view.client,"invalidateQueries");begin();await screen.findByRole("list",{name:"Drafted edits"});fireEvent.click(screen.getByRole("button",{name:"Save as a new layout"}));
  await waitFor(()=>expect(applyLayoutEdit).toHaveBeenCalledTimes(1));view.change("project");
  await act(async()=>{pending.resolve({id:"saved",name:result.name,applied:result.applied,warnings:[]});await pending.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));
  expect(invalidate).toHaveBeenCalledTimes(2);expect(invalidate.mock.calls.every(([options])=>JSON.stringify(options?.queryKey).includes('"p"')&&!JSON.stringify(options?.queryKey).includes('"other"'))).toBe(true);
  expect(useSimulationStore.getState().selectedSetupId).toBeNull();
});
it("enforces the minimum and maximum by Unicode characters",()=>{
  mount();const input=screen.getByLabelText("Layout changes in words");fireEvent.change(input,{target:{value:"a".repeat(799)+"🛒x"}});
  expect((input as HTMLTextAreaElement).value).toBe("a".repeat(799)+"🛒");fireEvent.change(input,{target:{value:"🛒".repeat(4)}});
  expect((screen.getByRole("button",{name:"Draft the edits"}) as HTMLButtonElement).disabled).toBe(true);
});
it("owns a second routed request while the first draft is still pending",async()=>{
  const old=deferred<LayoutEditDraft>(),current=deferred<LayoutEditDraft>();vi.mocked(draftLayoutEdit).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  const view=mount();act(()=>useAssistStore.getState().send({projectId:"p",destination:"layout_edit",text:"Old instructions about tea"}));await waitFor(()=>expect(draftLayoutEdit).toHaveBeenCalledTimes(1));
  act(()=>useAssistStore.getState().send({projectId:"p",destination:"layout_edit",text:"New instructions about coffee"}));await waitFor(()=>expect(draftLayoutEdit).toHaveBeenCalledTimes(2));
  await act(async()=>{current.resolve({...result,summary:"Current routed summary"});await current.promise;});await screen.findByText("Current routed summary");
  await act(async()=>{old.resolve(result);await old.promise;});await waitFor(()=>expect(view.client.isMutating()).toBe(0));expect(screen.getByText("Current routed summary")).toBeTruthy();
});
