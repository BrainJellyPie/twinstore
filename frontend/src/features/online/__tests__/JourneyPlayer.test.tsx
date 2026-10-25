// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { JourneyPlayer } from "../JourneyPlayer";

vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getPlayback: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => { useLocale.getState().setLocale("en"); vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.useRealTimers(); vi.resetAllMocks(); });

function step(index: number, page: online.PageKind, choice: online.PageOption | null, thought = "", search = ""): online.SessionStep {
  return { index, url: `/${page}`, page, state: {} as online.BrowserState, options: 3, choice, search_text: search, thought,
    seconds: 2, load_seconds: 1, source: "rule", error: "", mark_seed: 0, screen: null, ads: [] };
}

const option = (number: number, kind: online.ActionKind, label: string) => ({ number, kind, label, target: "", ad_id: "" }) as online.PageOption;
const view: online.SessionView = {
  variant: 0, site_id: "s1", site_name: "Shop", shopper: { id: "os0001", device: "desktop", vision: "typical" } as online.OnlineShopper,
  session: {
    shopper_id: "os0001", site_id: "s1", outcome: "purchased", order_total: 4200, order: [], subtotal: 4200, seconds: 30,
    reached: ["visit"], viewed_products: [], searches: [], exit_page: "order_complete", exit_thought: "Done, that was easy.",
    model_requests: 0, fallbacks: 0, survey: null, addon_paid: 0, discount: 0, reminded: false, returned_at: null,
    steps: [
      step(0, "home", option(4, "search", "Search box"), "Let me look for dog food.", "dog food"),
      step(1, "search", option(2, "open_product", "Open product: Dog Food"), "This one looks right."),
      step(2, "order_complete", null),
    ],
  },
};

function Harness() {
  const [index, setIndex] = useState(0);
  return <JourneyPlayer projectId="p1" runId="r1" view={view} index={index} onIndex={setIndex} money={(x) => `$${(x / 100).toFixed(2)}`}
    rival="" onRival={vi.fn()} />;
}

function mount() {
  vi.mocked(online.getPlayback).mockResolvedValue([
    { step: 0, width: 1024, height: 2000, box: [100, 1500, 300, 1540] },
    { step: 1, width: 1024, height: 900, box: [500, 200, 700, 400] },
    { step: 2, width: 1024, height: 700, box: null },
  ]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>);
}

async function load() {
  const img = await screen.findByRole("img");
  expect(img.getAttribute("src")).toContain("highlight=false");
  fireEvent.load(img);
}

async function wait(ms: number) { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); }

it("plays the visit page by page: scrolls to the pick, clicks, shows the thought, and ends on the outcome", async () => {
  mount();
  await load();
  expect(screen.getByText("Now on: Home page")).toBeTruthy();
  await wait(800);  // arrive → aim: the page scrolls so the far-down search box is in view
  const page = screen.getByRole("img").parentElement!;
  expect(page.style.transform).not.toBe("translateY(-0%)");
  await wait(1100);  // aim → click
  expect(screen.getByText("Searches for “dog food”")).toBeTruthy();
  expect(screen.getByText("“Let me look for dog food.”")).toBeTruthy();
  await wait(600);  // click → read
  await wait(4500);  // read → the next page
  expect(screen.getByText("Step 2 of 3")).toBeTruthy();
  expect(screen.getByText("Loading the page…")).toBeTruthy();  // waits for the page before going on
  await wait(4500);
  expect(screen.getByText("Step 2 of 3")).toBeTruthy();
  await load();
  for (const ms of [800, 1100, 600, 4500]) await wait(ms);
  expect(screen.getByText("Step 3 of 3")).toBeTruthy();
  await load();
  await wait(800);  // the last page has no click: straight to reading
  await wait(4500);
  expect(screen.getByText("“Done, that was easy.”")).toBeTruthy();
  expect(screen.getByText("Ordered · $42.00")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Play again" }));
  expect(screen.getByText("Step 1 of 3")).toBeTruthy();
});

it("pauses, changes speed and jumps to a step", async () => {
  mount();
  await load();
  fireEvent.click(screen.getByRole("button", { name: "Pause" }));
  await wait(20000);
  expect(screen.getByText("Step 1 of 3")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "2×" }));
  expect(screen.getByRole("button", { name: "2×" }).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: "Go to step 2: Search results" }));
  expect(screen.getByText("Step 2 of 3")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Play" }));
  await load();
  for (const ms of [800, 1100, 600, 4500]) await wait(ms / 2);
  expect(screen.getByText("Step 3 of 3")).toBeTruthy();
});

it("reports a failed screenshot and retries without losing the paused visit", async () => {
  mount();
  const first = await screen.findByRole("img");
  fireEvent.click(screen.getByRole("button", { name: "Pause" }));
  fireEvent.error(first);
  expect(screen.getByRole("alert").textContent).toContain("This page could not be loaded.");
  await wait(20000);
  expect(screen.getByText("Step 1 of 3")).toBeTruthy();
  let previous = first.getAttribute("src");
  for (let attempt = 0; attempt < 2; attempt++) {
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    const current = screen.getByRole("img");
    expect(current.getAttribute("src")).not.toBe(previous);
    previous = current.getAttribute("src");
    if (attempt === 0) fireEvent.error(current);
    else fireEvent.load(current);
  }
  expect(screen.queryByRole("alert")).toBeNull();
  await wait(20000);
  expect(screen.getByText("Step 1 of 3")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Play" }));
  for (const ms of [800, 1100, 600, 4500]) await wait(ms);
  expect(screen.getByText("Step 2 of 3")).toBeTruthy();
});

it("retries failed playback metadata without reopening the visit", async () => {
  vi.mocked(online.getPlayback).mockRejectedValueOnce(new Error("Playback temporarily unavailable"));
  mount();
  expect((await screen.findByRole("alert")).textContent).toContain("Playback temporarily unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await load();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(online.getPlayback).toHaveBeenCalledTimes(2);
  for (const ms of [800, 1100, 600, 4500]) await wait(ms);
  expect(screen.getByText("Step 2 of 3")).toBeTruthy();
});

it("shows the first page before the click boxes arrive and starts once they do", async () => {
  let resolve: (frames: online.PlaybackFrame[]) => void = () => {};
  vi.mocked(online.getPlayback).mockReturnValue(new Promise((done) => { resolve = done; }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>);
  await load();
  expect(screen.queryByText("Loading the page…")).toBeNull();
  expect(screen.getByRole("img").className).toContain("opacity-100");
  await wait(20000);
  expect(screen.getByText("Step 1 of 3")).toBeTruthy();
  expect(screen.getByText("Now on: Home page")).toBeTruthy();
  await act(async () => { resolve([
    { step: 0, width: 1024, height: 2000, box: [100, 1500, 300, 1540] },
    { step: 1, width: 1024, height: 900, box: [500, 200, 700, 400] },
    { step: 2, width: 1024, height: 700, box: null },
  ]); });
  for (const ms of [800, 1100]) await wait(ms);
  expect(screen.getByText("Searches for “dog food”")).toBeTruthy();
});
