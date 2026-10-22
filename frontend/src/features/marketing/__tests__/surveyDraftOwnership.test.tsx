// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { designSurvey, type SurveyDesign } from "@/shared/api/marketing";
import { SurveyBuilder } from "../SurveyBuilder";
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  getModels: vi.fn().mockResolvedValue([{ ref: "other", label: "Other vision", vision: true }]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), designSurvey: vi.fn(), startSurvey: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [
  { asset_id: "gold", name: "Label Gold" }, { asset_id: "leaf", name: "Label Leaf" },
] }) }));
vi.mock("../ProductLibrary", () => ({ ProductDrop: () => null }));
const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.clearAllMocks(); });
const result: SurveyDesign = {
  name: "Old suggested test", stimuli: ["leaf"], stimulus_names: ["Old leaf"], questions: ["value"],
  context: "Old suggested brief", reference_price: 199, currency: "USD", age_groups: ["20s"], genders: ["Male"],
  rationale: "Old survey rationale", warnings: [],
};
function deferred() {
  let resolve!: (d: SurveyDesign) => void, reject!: (e: Error) => void;
  const promise = new Promise<SurveyDesign>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
const brief = () => screen.getByPlaceholderText(/What respondents are told/);
const question = () => screen.getByLabelText("Question for the concept test");
const button = () => screen.getByRole("button", { name: "Draft the test" }) as HTMLButtonElement;
const change = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } });
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  let props: ComponentProps<typeof SurveyBuilder> = {
    projectId: "p", setupId: "s", personaCount: 60, defaultCurrency: "USD", onStarted: vi.fn(),
    initial: { name: "My test", stimuli: ["gold"], stimulus_names: ["My gold"], questions: ["appeal"],
      context: "My brief", currency: "USD", reference_price: 299, panel: 60, age_groups: [], genders: [], model: "", seed: 0 },
  };
  const draw = () => <QueryClientProvider client={client}><SurveyBuilder {...props} /></QueryClientProvider>;
  const view = render(draw());
  return { client, change(kind: string) {
    if (kind === "question") change(question(), "Would a different concept work?");
    if (kind === "stimuli") fireEvent.click(screen.getByTitle("Label Leaf"));
    if (kind === "label") change(screen.getByLabelText("Name of A"), "My new label");
    if (kind === "questions") fireEvent.click(screen.getByRole("button", { name: /Stand-out/ }));
    if (kind === "brief") change(brief(), "My new brief");
    if (kind === "price") change(screen.getByLabelText("Shelf price shown with A (optional)"), "8.99");
    if (kind === "currency") change(screen.getByLabelText("Currency"), "KRW");
    if (kind === "panel") change(screen.getByLabelText("Respondents"), "75");
    if (kind === "age") fireEvent.click(screen.getByRole("button", { name: "40s" }));
    if (kind === "gender") fireEvent.click(screen.getByRole("button", { name: "Female" }));
    if (kind === "model") change(screen.getByLabelText("Vision model"), "other");
    if (kind === "name") change(screen.getByPlaceholderText("Test name (optional)"), "My new name");
    if (kind === "project") props = { ...props, projectId: "other" };
    if (kind === "layout") props = { ...props, setupId: "other" };
    if (kind === "default_currency") props = { ...props, defaultCurrency: "KRW" };
    view.rerender(draw());
  } };
}
function begin() { change(question(), "Which label would customers choose?"); fireEvent.click(button()); }
function values() {
  return Array.from(document.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>("input,select,textarea"))
    .map(e => [e.getAttribute("aria-label") ?? e.getAttribute("placeholder"), e.value]);
}
const changes = ["question", "stimuli", "label", "questions", "brief", "price", "currency", "panel", "age", "gender", "model", "name", "project", "layout", "default_currency"];
it.each(changes)("preserves a newer %s after a late success", async kind => {
  const pending = deferred(); vi.mocked(designSurvey).mockReturnValue(pending.promise);
  const view = mount(); await screen.findByRole("option", { name: "Other vision" }); begin();
  await waitFor(() => expect(designSurvey).toHaveBeenCalledTimes(1)); view.change(kind); const before = values();
  await act(async () => { pending.resolve(result); await pending.promise; });
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(values()).toEqual(before); expect(screen.queryByText(/Old survey rationale/)).toBeNull();
});
it.each(changes)("hides an obsolete error after changing %s", async kind => {
  const pending = deferred(); vi.mocked(designSurvey).mockReturnValue(pending.promise);
  const view = mount(); await screen.findByRole("option", { name: "Other vision" }); begin();
  await waitFor(() => expect(designSurvey).toHaveBeenCalledTimes(1)); view.change(kind);
  await act(async () => pending.reject(new Error("Old survey failed")));
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(screen.queryByText("Old survey failed")).toBeNull(); expect(button().disabled).toBe(false);
});
it.each(["brief", "price", "label", "questions", "project", "layout"])("hides an accepted rationale after changing %s", async kind => {
  vi.mocked(designSurvey).mockResolvedValue(result); const view = mount(); begin();
  await screen.findByText(/Old survey rationale/); view.change(kind);
  expect(screen.queryByText(/Old survey rationale/)).toBeNull();
});
it("keeps the latest response when drafts finish in reverse order", async () => {
  const old = deferred(), current = deferred(); vi.mocked(designSurvey).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  const view = mount(); begin(); await waitFor(() => expect(designSurvey).toHaveBeenCalledTimes(1));
  view.change("question"); fireEvent.click(button()); await waitFor(() => expect(designSurvey).toHaveBeenCalledTimes(2));
  await act(async () => { current.resolve({ ...result, context: "Current brief", rationale: "Current rationale" }); await current.promise; });
  await screen.findByDisplayValue("Current brief");
  await act(async () => { old.resolve(result); await old.promise; });
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(screen.getByDisplayValue("Current brief")).toBeTruthy(); expect(screen.getByText(/Current rationale/)).toBeTruthy();
});
it("preserves complete Unicode characters at the brief limit", () => {
  mount(); change(brief(), "a".repeat(299) + "🛒x"); expect((brief() as HTMLTextAreaElement).value).toBe("a".repeat(299) + "🛒");
});
it.each(["상품 포장을 비교해줘", "比较商品包装设计", "商品の包装を比較して", "Compare product labels", "Comparar los envases", "Comparer les emballages"])("ignores composition Enter: %s", async text => {
  mount(); change(question(), text);
  for (const flags of [{ isComposing: true }, { keyCode: 229 }]) fireEvent.keyDown(question(), { key: "Enter", ...flags });
  await act(async () => {}); expect(designSurvey).not.toHaveBeenCalled();
});
it("keeps question code points at the limit and requires five characters", () => {
  mount(); change(question(), "a".repeat(499) + "🛒x");
  expect((question() as HTMLInputElement).value).toBe("a".repeat(499) + "🛒");
  change(question(), "🛒".repeat(4)); expect(button().disabled).toBe(true);
  change(question(), "🛒".repeat(5)); expect(button().disabled).toBe(false);
});
it("retries a current failure with the same question and clears its error", async () => {
  vi.mocked(designSurvey).mockRejectedValueOnce(new Error("Retry this draft")).mockResolvedValueOnce(result);
  const view = mount(); begin(); await screen.findByRole("alert");
  expect(screen.getByRole("alert").textContent).toContain("Retry this draft");
  fireEvent.click(button()); await screen.findByText(/Old survey rationale/);
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(vi.mocked(designSurvey).mock.calls[1]).toEqual(vi.mocked(designSurvey).mock.calls[0]);
  expect(screen.queryByRole("alert")).toBeNull();
});
