// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { designConjoint, type ConjointDesign } from "@/shared/api/marketing";
import { ConjointBuilder } from "../ConjointBuilder";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), designConjoint: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const QUESTION = "Would shoppers pay more for tea?";
const RESULT: ConjointDesign = { name: "Generated study", product: "Generated tea", context: "Generated context", attributes: [{ name: "Sugar", levels: ["Regular", "Zero"] }], prices: [149, 199], currency: "USD", rationale: "Old request rationale", comparable: [] };
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function mount() {
  function Harness() {
    const [project, setProject] = useState("p1");
    const [setup, setSetup] = useState("s1");
    const [currency, setCurrency] = useState("USD");
    return <>
      <button onClick={() => setProject("p2")}>Switch project</button>
      <button onClick={() => setSetup("s2")}>Switch layout</button>
      <button onClick={() => setCurrency("KRW")}>Switch currency</button>
      <ConjointBuilder projectId={project} setupId={setup} defaultCurrency={currency} personaCount={60} onStarted={vi.fn()} />
    </>;
  }
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><Harness /></QueryClientProvider>);
}
function begin() {
  fireEvent.change(screen.getByLabelText("Question for the study"), { target: { value: QUESTION } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the study" }));
}
const EDITS = ["question", "product", "context", "attribute", "levels", "price", "name", "example", "project", "layout", "currency"] as const;
function edit(kind: typeof EDITS[number]) {
  if (kind === "question") fireEvent.change(screen.getByLabelText("Question for the study"), { target: { value: "Would shoppers prefer coffee instead?" } });
  if (kind === "product") fireEvent.change(screen.getByPlaceholderText("a bottle of iced tea"), { target: { value: "My chosen product" } });
  if (kind === "context") fireEvent.change(screen.getByPlaceholderText("Sold in the drinks fridge next to the sodas."), { target: { value: "My chosen context" } });
  if (kind === "attribute") fireEvent.change(screen.getByLabelText("Attribute 1 name"), { target: { value: "My attribute" } });
  if (kind === "levels") fireEvent.change(screen.getByLabelText("Levels of attribute 1"), { target: { value: "One, Two" } });
  if (kind === "price") fireEvent.change(screen.getByLabelText("Price levels"), { target: { value: "10, 20" } });
  if (kind === "name") fireEvent.change(screen.getByPlaceholderText("Study name (optional)"), { target: { value: "My study" } });
  if (kind === "example") fireEvent.click(screen.getByRole("button", { name: "Iced tea" }));
  if (kind === "project") fireEvent.click(screen.getByRole("button", { name: "Switch project" }));
  if (kind === "layout") fireEvent.click(screen.getByRole("button", { name: "Switch layout" }));
  if (kind === "currency") fireEvent.click(screen.getByRole("button", { name: "Switch currency" }));
}
const values = () => screen.getAllByRole("textbox").map((input) => (input as HTMLInputElement).value);

it.each(EDITS)("keeps a newer %s instead of applying a late draft", async (kind) => {
  const request = deferred<ConjointDesign>();
  vi.mocked(designConjoint).mockReturnValue(request.promise);
  mount(); begin();
  await waitFor(() => expect(designConjoint).toHaveBeenCalledTimes(1));
  edit(kind);
  const expected = values();
  await act(async () => { request.resolve(RESULT); await request.promise; });
  expect(values()).toEqual(expected);
  expect(screen.queryByText(/Old request rationale/)).toBeNull();
});

it.each(EDITS)("discards an obsolete failure after editing %s", async (kind) => {
  const request = deferred<ConjointDesign>();
  vi.mocked(designConjoint).mockReturnValue(request.promise);
  mount(); begin();
  await waitFor(() => expect(designConjoint).toHaveBeenCalledTimes(1));
  edit(kind);
  await act(async () => { request.reject(new Error("Old draft failed")); });
  expect(screen.queryByRole("alert")).toBeNull();
  expect((screen.getByRole("button", { name: "Draft the study" }) as HTMLButtonElement).disabled).toBe(false);
});

it.each(["무설탕 차를 더 선호할까요?", "是否愿意购买无糖茶？", "無糖のお茶が好まれますか？", "Would shoppers prefer tea?", "¿Prefieren té sin azúcar?", "Préféreraient-ils du thé ?"])("does not submit composition Enter: %s", async (text) => {
  vi.mocked(designConjoint).mockResolvedValue(RESULT);
  mount(); const input = screen.getByLabelText("Question for the study");
  fireEvent.change(input, { target: { value: text } });
  for (const flags of [{ isComposing: true }, { keyCode: 229 }]) {
    const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true, ...flags });
    fireEvent(input, event); expect(event.defaultPrevented).toBe(false);
  }
  await act(async () => {});
  expect(designConjoint).not.toHaveBeenCalled();
});

it("applies only the newest request when replies arrive in reverse order", async () => {
  const old = deferred<ConjointDesign>(); const current = deferred<ConjointDesign>();
  vi.mocked(designConjoint).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  mount(); begin();
  await waitFor(() => expect(designConjoint).toHaveBeenCalledTimes(1));
  edit("question"); fireEvent.click(screen.getByRole("button", { name: "Draft the study" }));
  await waitFor(() => expect(designConjoint).toHaveBeenCalledTimes(2));
  await act(async () => { current.resolve({ ...RESULT, product: "Coffee instead" }); await current.promise; });
  await act(async () => { old.resolve(RESULT); await old.promise; });
  expect((screen.getByPlaceholderText("a bottle of iced tea") as HTMLInputElement).value).toBe("Coffee instead");
});
