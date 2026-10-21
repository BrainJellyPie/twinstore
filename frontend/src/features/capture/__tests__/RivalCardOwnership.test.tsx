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
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { RivalCard } from "../RivalCard";
vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  getSetups: vi.fn(),
  getTown: vi.fn(),
  compareRival: vi.fn(),
}));
const capture = {
  image_size: [20, 20],
  currency: "USD",
  items: [{ id: "i", name: "Tea", labeled: true, price: 199 }],
} as api.CaptureResult;
const report: api.RivalReport = {
  venue_id: "v1",
  previous_attractiveness: null,
  attractiveness: null,
  comparison: {
    matched: 0,
    rival_products: 1,
    our_products_in_categories: 1,
    price_index: 0.8,
    overlap: 0,
    only_rival: ["Outdated unmatched product"],
    only_ours: [],
    prices: [],
    suggested_pull_factor: 1.25,
  },
};
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.getSetups).mockResolvedValue([
    { id: "b", name: "Layout B" },
    { id: "a", name: "Layout A" },
  ] as never);
  vi.mocked(api.getTown).mockResolvedValue({
    venues: [
      { id: "v1", name: "Rival one", category: "convenience", is_focal: false },
      { id: "v2", name: "Rival two", category: "convenience", is_focal: false },
    ],
  } as never);
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.clear());
  vi.resetAllMocks();
});
function deferred() {
  let resolve!: (v: api.RivalReport) => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<api.RivalReport>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { resolve, reject, promise };
}
async function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  clients.push(client);
  const draw = (projectId = "p", captureId = "c", result = capture) => (
    <QueryClientProvider client={client}>
      <RivalCard projectId={projectId} captureId={captureId} result={result} />
    </QueryClientProvider>
  );
  const view = render(draw());
  await screen.findByRole("option", { name: "Rival one" });
  fireEvent.change(screen.getByLabelText("Rival venue"), {
    target: { value: "v1" },
  });
  return {
    client,
    change(kind: string) {
      if (kind === "layout")
        fireEvent.change(screen.getByLabelText("Our layout"), {
          target: { value: "b" },
        });
      if (kind === "venue")
        fireEvent.change(screen.getByLabelText("Rival venue"), {
          target: { value: "v2" },
        });
      if (kind === "capture") view.rerender(draw("p", "other_capture"));
      if (kind === "project") view.rerender(draw("other_project"));
      if (kind === "correction")
        view.rerender(
          draw("p", "c", {
            ...capture,
            items: capture.items.map((i) => ({ ...i, price: 299 })),
          }),
        );
    },
  };
}
function compare() {
  fireEvent.click(
    screen.getByRole("button", { name: "Compare with our store" }),
  );
}
const CHANGES = ["layout", "venue", "capture", "project", "correction"];
it.each(CHANGES)(
  "discards a late comparison after changing %s",
  async (kind) => {
    const request = deferred();
    vi.mocked(api.compareRival).mockReturnValue(request.promise);
    const view = await mount();
    compare();
    await waitFor(() => expect(api.compareRival).toHaveBeenCalled());
    view.change(kind);
    await act(async () => {
      request.resolve(report);
      await request.promise;
    });
    await waitFor(() => expect(view.client.isMutating()).toBe(0));
    expect(screen.queryByText(/Outdated unmatched product/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Apply ×/ })).toBeNull();
  },
);
it.each(CHANGES)(
  "discards an obsolete error after changing %s",
  async (kind) => {
    const request = deferred();
    vi.mocked(api.compareRival).mockReturnValue(request.promise);
    const view = await mount();
    compare();
    await waitFor(() => expect(api.compareRival).toHaveBeenCalled());
    view.change(kind);
    await act(async () =>
      request.reject(new Error("Previous comparison failed")),
    );
    await waitFor(() => expect(view.client.isMutating()).toBe(0));
    expect(screen.queryByText("Previous comparison failed")).toBeNull();
    expect(
      (
        screen.getByRole("button", {
          name: "Compare with our store",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  },
);
it.each(CHANGES)(
  "hides an accepted comparison when %s changes",
  async (kind) => {
    vi.mocked(api.compareRival).mockResolvedValue(report);
    const view = await mount();
    compare();
    await screen.findByText(/Outdated unmatched product/);
    view.change(kind);
    expect(screen.queryByRole("button", { name: /Apply ×/ })).toBeNull();
    expect(screen.queryByText(/Outdated unmatched product/)).toBeNull();
  },
);
it("applies only the latest comparison when responses finish in reverse order", async () => {
  const old = deferred(),
    current = deferred();
  vi.mocked(api.compareRival)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(current.promise);
  const view = await mount();
  compare();
  await waitFor(() => expect(api.compareRival).toHaveBeenCalledTimes(1));
  view.change("layout");
  compare();
  await waitFor(() => expect(api.compareRival).toHaveBeenCalledTimes(2));
  await act(async () => {
    current.resolve({
      ...report,
      comparison: {
        ...report.comparison,
        only_rival: ["Current unmatched product"],
      },
    });
    await current.promise;
  });
  await screen.findByText(/Current unmatched product/);
  await act(async () => {
    old.resolve(report);
    await old.promise;
  });
  await waitFor(() => expect(view.client.isMutating()).toBe(0));
  expect(screen.queryByText(/Outdated unmatched product/)).toBeNull();
  expect(screen.getByText(/Current unmatched product/)).toBeTruthy();
});
it("refreshes the original town when an apply finishes after changing projects", async () => {
  const request = deferred();
  vi.mocked(api.compareRival)
    .mockResolvedValueOnce(report)
    .mockReturnValueOnce(request.promise);
  const view = await mount();
  compare();
  fireEvent.click(await screen.findByRole("button", { name: /Apply ×/ }));
  await waitFor(() => expect(api.compareRival).toHaveBeenCalledTimes(2));
  const refresh = vi.spyOn(view.client, "invalidateQueries");
  view.change("project");
  await act(async () => {
    request.resolve(report);
    await request.promise;
  });
  expect(refresh).toHaveBeenCalledWith({ queryKey: ["projects", "p", "town"] });
});
it("does not display a positive price index as zero", async () => {
  vi.mocked(api.compareRival).mockResolvedValue({
    ...report,
    comparison: { ...report.comparison, price_index: 1e-9 },
  });
  await mount();
  compare();
  await screen.findByText(/Outdated unmatched product/);
  expect(screen.getByText("<0.01")).toBeTruthy();
  expect(screen.queryByText("0.00")).toBeNull();
});
