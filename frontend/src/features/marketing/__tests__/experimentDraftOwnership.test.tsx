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
  designExperiment,
  type ExperimentDesign,
} from "@/shared/api/marketing";
import { ExperimentBuilder } from "../ExperimentBuilder";
vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...(await original<typeof import("@/shared/api/marketing")>()),
  designExperiment: vi.fn(),
  startExperiment: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [] }) }));
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
];
const store = {
  racks: [
    { id: "r", type: "shelf", rack_name: "Drinks", levels: 4, slots: [] },
  ],
} as unknown as ComponentProps<typeof ExperimentBuilder>["store"];
const result: ExperimentDesign = {
  name: "Old suggested test",
  engine: "rule",
  rationale: "Old test rationale",
  focus_skus: ["tea"],
  warnings: [],
  variants: [
    {
      name: "Old suggested variant",
      changes: [{ kind: "discount", sku: "tea", percent: -20 }],
    },
  ],
};
function deferred() {
  let resolve!: (d: ExperimentDesign) => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<ExperimentDesign>((a, b) => {
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
  let props: ComponentProps<typeof ExperimentBuilder> = {
    projectId: "p",
    setupId: "s",
    products,
    store,
    currency: "USD",
    onStarted: vi.fn(),
  };
  const draw = () => (
    <QueryClientProvider client={client}>
      <ExperimentBuilder {...props} />
    </QueryClientProvider>
  );
  const view = render(draw());
  return {
    client,
    change(kind: string) {
      if (kind === "question")
        fireEvent.change(screen.getByLabelText("Question for the test"), {
          target: { value: "Would a different promotion work?" },
        });
      if (kind === "variant")
        fireEvent.change(screen.getByLabelText("Variant name"), {
          target: { value: "My newer variant" },
        });
      if (kind === "name")
        fireEvent.change(screen.getByPlaceholderText("Summer price test"), {
          target: { value: "My newer test" },
        });
      if (kind === "engine")
        fireEvent.click(
          screen.getByRole("button", { name: /Vision shoppers/ }),
        );
      if (kind === "extra_variant")
        fireEvent.click(screen.getByRole("button", { name: "Add a variant" }));
      if (kind === "project") props = { ...props, projectId: "other" };
      if (kind === "layout") props = { ...props, setupId: "other" };
      if (kind === "currency") props = { ...props, currency: "KRW" };
      if (kind === "catalog")
        props = {
          ...props,
          products: products.map((p) => ({ ...p, price: 299 })),
        };
      view.rerender(draw());
    },
  };
}
function begin() {
  fireEvent.change(screen.getByLabelText("Question for the test"), {
    target: { value: "Would a discount increase tea sales?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Draft the test" }));
}
const changes = [
  "question",
  "variant",
  "name",
  "engine",
  "extra_variant",
  "project",
  "layout",
  "currency",
  "catalog",
];
it.each(changes)(
  "keeps a newer %s when a draft finishes late",
  async (kind) => {
    const request = deferred();
    vi.mocked(designExperiment).mockReturnValue(request.promise);
    const view = mount();
    begin();
    await waitFor(() => expect(designExperiment).toHaveBeenCalledTimes(1));
    view.change(kind);
    const values = screen
      .getAllByRole("textbox")
      .map((e) => (e as HTMLInputElement).value);
    await act(async () => {
      request.resolve(result);
      await request.promise;
    });
    await waitFor(() => expect(view.client.isMutating()).toBe(0));
    expect(
      screen.getAllByRole("textbox").map((e) => (e as HTMLInputElement).value),
    ).toEqual(values);
    expect(screen.queryByText(/Old test rationale/)).toBeNull();
  },
);
it.each(changes)(
  "hides an obsolete failure after changing %s",
  async (kind) => {
    const request = deferred();
    vi.mocked(designExperiment).mockReturnValue(request.promise);
    const view = mount();
    begin();
    await waitFor(() => expect(designExperiment).toHaveBeenCalledTimes(1));
    view.change(kind);
    await act(async () => request.reject(new Error("Old test failed")));
    await waitFor(() => expect(view.client.isMutating()).toBe(0));
    expect(screen.queryByText("Old test failed")).toBeNull();
    expect(
      (
        screen.getByRole("button", {
          name: "Draft the test",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  },
);
it.each([
  "할인 효과를 비교해줘",
  "比较商品降价效果",
  "値下げ効果を比較して",
  "Compare discount effects",
  "Comparar los descuentos",
  "Comparer les remises",
])("does not draft on a composition Enter: %s", async (text) => {
  mount();
  const input = screen.getByLabelText("Question for the test");
  fireEvent.change(input, { target: { value: text } });
  for (const flags of [{ isComposing: true }, { keyCode: 229 }])
    fireEvent.keyDown(input, { key: "Enter", ...flags });
  await act(async () => {});
  expect(designExperiment).not.toHaveBeenCalled();
});
it("limits the question by code points and enforces the five-character minimum", () => {
  mount();
  const input = screen.getByLabelText(
    "Question for the test",
  ) as HTMLInputElement;
  fireEvent.change(input, { target: { value: "a".repeat(499) + "🛒x" } });
  expect(input.value).toBe("a".repeat(499) + "🛒");
  fireEvent.change(input, { target: { value: "🛒🧃🛍" } });
  expect(
    (
      screen.getByRole("button", {
        name: "Draft the test",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});
it("keeps the latest draft when replies finish in reverse order", async () => {
  const old = deferred(),
    current = deferred();
  vi.mocked(designExperiment)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(current.promise);
  const view = mount();
  begin();
  await waitFor(() => expect(designExperiment).toHaveBeenCalledTimes(1));
  view.change("question");
  fireEvent.click(screen.getByRole("button", { name: "Draft the test" }));
  await waitFor(() => expect(designExperiment).toHaveBeenCalledTimes(2));
  await act(async () => {
    current.resolve({
      ...result,
      variants: [{ ...result.variants[0]!, name: "Current variant" }],
    });
    await current.promise;
  });
  await screen.findByDisplayValue("Current variant");
  await act(async () => {
    old.resolve(result);
    await old.promise;
  });
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(screen.getByDisplayValue("Current variant")).toBeTruthy();
});
