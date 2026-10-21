// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps } from "react";
import { afterEach, expect, it, vi } from "vitest";
import {
  draftPitchScript,
  startPitch,
  type ScriptDraft,
} from "@/shared/api/marketing";
import { StaffPitchBuilder } from "../StaffPitchBuilder";
vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...(await original<typeof import("@/shared/api/marketing")>()),
  draftPitchScript: vi.fn(),
  startPitch: vi.fn(),
}));
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.clear());
  vi.clearAllMocks();
});
const products = [
  {
    sku: "tea",
    name: "Tea",
    price: 199,
    regularPrice: 299,
    promo: "",
    facings: 1,
    racks: ["Drinks"],
  },
  {
    sku: "coffee",
    name: "Coffee",
    price: 299,
    regularPrice: 399,
    promo: "",
    facings: 1,
    racks: ["Drinks"],
  },
];
const result: ScriptDraft = {
  name: "Old suggested name",
  script: "Old suggested script",
  differs_by: "Old rationale",
};
function deferred() {
  let resolve!: (d: ScriptDraft) => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<ScriptDraft>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  clients.push(client);
  let props: ComponentProps<typeof StaffPitchBuilder> = {
    projectId: "p",
    setupId: "s",
    products,
    currency: "USD",
    personaCount: 40,
    onStarted: vi.fn(),
  };
  const draw = () => (
    <QueryClientProvider client={client}>
      <StaffPitchBuilder {...props} />
    </QueryClientProvider>
  );
  const view = render(draw());
  return {
    client,
    change(kind: string) {
      const fields: Record<string, string> = {
        script: "Script B text",
        name: "Script B name",
        current: "Script A text",
        context: "Encounter context",
        facts: "Verified product facts (optional)",
        direction: "Direction for script B",
      };
      if (fields[kind])
        fireEvent.change(screen.getByLabelText(fields[kind]), {
          target: { value: "My newer manual input" },
        });
      if (kind === "product")
        fireEvent.change(screen.getByLabelText("Product held constant"), {
          target: { value: "coffee" },
        });
      if (kind === "project") props = { ...props, projectId: "other" };
      if (kind === "layout") props = { ...props, setupId: "other" };
      if (kind === "currency") props = { ...props, currency: "KRW" };
      if (kind === "catalog")
        props = {
          ...props,
          products: products.map((p) => ({ ...p, price: p.price + 100 })),
        };
      view.rerender(draw());
    },
  };
}
function draft() {
  fireEvent.click(screen.getByRole("button", { name: "Write an alternative" }));
}
const changes = [
  "script",
  "name",
  "current",
  "context",
  "facts",
  "direction",
  "product",
  "project",
  "layout",
  "currency",
  "catalog",
];
it.each(changes)("keeps newer %s when the old script arrives", async (kind) => {
  const request = deferred();
  vi.mocked(draftPitchScript).mockReturnValue(request.promise);
  const view = mount();
  draft();
  await waitFor(() => expect(draftPitchScript).toHaveBeenCalledTimes(1));
  view.change(kind);
  const before = screen
    .getAllByRole("textbox")
    .map((e) => (e as HTMLInputElement).value);
  await act(async () => {
    request.resolve(result);
    await request.promise;
  });
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(
    screen.getAllByRole("textbox").map((e) => (e as HTMLInputElement).value),
  ).toEqual(before);
  expect(screen.queryByText(/Old rationale/)).toBeNull();
});
it.each(changes)(
  "discards an obsolete draft error after changing %s",
  async (kind) => {
    const request = deferred();
    vi.mocked(draftPitchScript).mockReturnValue(request.promise);
    const view = mount();
    draft();
    await waitFor(() => expect(draftPitchScript).toHaveBeenCalledTimes(1));
    view.change(kind);
    await act(async () => request.reject(new Error("Old script failed")));
    await waitFor(() => expect(view.client.isMutating()).toBe(0));
    expect(screen.queryByText("Old script failed")).toBeNull();
    expect(
      (
        screen.getByRole("button", {
          name: "Write an alternative",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  },
);
it.each(["script", "name", "direction", "facts"])(
  "hides the previous explanation after a %s edit",
  async (kind) => {
    vi.mocked(draftPitchScript).mockResolvedValue(result);
    const view = mount();
    draft();
    await screen.findByText(/Old rationale/);
    view.change(kind);
    expect(screen.queryByText(/Old rationale/)).toBeNull();
  },
);
it.each([
  "가치를 강조하는 안내",
  "强调商品价值",
  "価値を伝える案内",
  "Lead with value",
  "Destacar el valor",
  "Souligner la valeur",
])("does not draft or submit the study while composing: %s", async (text) => {
  mount();
  const input = screen.getByLabelText("Direction for script B");
  fireEvent.change(input, { target: { value: text } });
  for (const flags of [{ isComposing: true }, { keyCode: 229 }]) {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
      ...flags,
    });
    fireEvent(input, event);
    expect(event.defaultPrevented).toBe(true);
  }
  await act(async () => {});
  expect(draftPitchScript).not.toHaveBeenCalled();
  expect(startPitch).not.toHaveBeenCalled();
});
it("uses direction Enter only to draft the alternative", async () => {
  vi.mocked(draftPitchScript).mockResolvedValue(result);
  mount();
  fireEvent.change(screen.getByLabelText("Script A text"), {
    target: { value: "Can I help?" },
  });
  fireEvent.change(screen.getByLabelText("Script B text"), {
    target: { value: "A different greeting" },
  });
  const input = screen.getByLabelText("Direction for script B");
  fireEvent.change(input, { target: { value: "Lead with value" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() => expect(draftPitchScript).toHaveBeenCalledTimes(1));
  expect(startPitch).not.toHaveBeenCalled();
});
it("preserves a full supplementary character at the 200-character boundary", () => {
  mount();
  fireEvent.change(screen.getByLabelText("Direction for script B"), {
    target: { value: "a".repeat(199) + "🛒x" },
  });
  expect(
    (screen.getByLabelText("Direction for script B") as HTMLInputElement).value,
  ).toBe("a".repeat(199) + "🛒");
});
it("keeps the current script when an older request finishes last", async () => {
  const old = deferred(),
    current = deferred();
  vi.mocked(draftPitchScript)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(current.promise);
  const view = mount();
  draft();
  await waitFor(() => expect(draftPitchScript).toHaveBeenCalledTimes(1));
  view.change("direction");
  draft();
  await waitFor(() => expect(draftPitchScript).toHaveBeenCalledTimes(2));
  await act(async () => {
    current.resolve({
      ...result,
      name: "Current name",
      script: "Current script",
    });
    await current.promise;
  });
  await screen.findByDisplayValue("Current script");
  await act(async () => {
    old.resolve(result);
    await old.promise;
  });
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(screen.getByDisplayValue("Current script")).toBeTruthy();
});
