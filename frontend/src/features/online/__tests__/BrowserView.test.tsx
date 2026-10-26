// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { BrowserView } from "../BrowserView";

vi.mock("@/shared/api/online", async (importOriginal) => ({ ...(await importOriginal<typeof online>()), browse: vi.fn() }));

const state = (page: online.PageKind, extra: Partial<online.BrowserState> = {}): online.BrowserState => ({
  at: { page, category_id: "", query: "", product_id: "", sort: null, page_index: 0, checkout_step: "address" },
  history: [], overlay: "none", cart: [], wishlist: [], viewed: [], reviews_open: false, welcome_seen: false,
  cookies_answered: true, coupon_known: false, coupon_applied: false, signed_in: false, guest: false, address_added: false,
  payment_method: null, addon_removed: false, large_text: false, device: "desktop", notice: "", order_id: "", order: [],
  order_total: 0, ...extra,
});
const view = (page: online.PageKind, options: online.PageOption[]): online.PageView => ({
  url: `https://www.shop.shop/${page}`, title: page, page, options, outline: ["Page: Home"], state: state(page),
  image: "data:image/png;base64,AAAA", width: 1024, height: 800,
});
const home = view("home", [
  { kind: "search", target: "", label: "Search box: type words to search the shop", number: 3, box: [10, 10, 200, 40], ad_id: "" },
  { kind: "open_product", target: "p001", label: "Open product: Canvas Tote Bag ($14.99)", number: 7, box: [20, 300, 220, 500], ad_id: "" },
]);

beforeEach(() => { useLocale.getState().setLocale("en"); vi.mocked(online.browse).mockResolvedValue(home); });
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.restoreAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><BrowserView projectId="p1" siteId="s1" /></QueryClientProvider>);
}

it("opens a new visit and clicks an option on the screenshot by its number", async () => {
  mount();
  await waitFor(() => expect(online.browse).toHaveBeenCalledWith("p1", "s1", expect.objectContaining({ state: null, option: null, device: "desktop" })));
  const overlay = await screen.findByRole("button", { name: "7. Open product: Canvas Tote Bag ($14.99)" });
  expect(overlay.style.left).toBe(`${(20 / 1024) * 100}%`);
  vi.mocked(online.browse).mockResolvedValueOnce(view("product", []));
  fireEvent.click(overlay);
  await waitFor(() => expect(online.browse).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({ state: home.state, option: 7 })));
  expect(await screen.findByText(/Home page → \[7\] Open product/)).toBeTruthy();
});

it("asks what to type before using the search box", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /^3\. Search box/ }));
  expect(online.browse).toHaveBeenCalledTimes(1);
  const input = screen.getByRole("textbox", { name: "What does the shopper type?" });
  fireEvent.change(input, { target: { value: "tote bag" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => expect(online.browse).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({ option: 3, query: "tote bag" })));
});

it("starts a mobile visit and shows server errors", async () => {
  mount();
  await screen.findByRole("button", { name: /^7\./ });
  vi.mocked(online.browse).mockRejectedValueOnce(new Error("That option is not on this page"));
  fireEvent.click(screen.getByRole("button", { name: "Mobile" }));
  await waitFor(() => expect(online.browse).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({ state: null, device: "mobile" })));
  expect((await screen.findByRole("alert")).textContent).toContain("That option is not on this page");
});

it("shows the page through a shopper's eyesight without leaving the page", async () => {
  mount();
  await screen.findByRole("button", { name: /^7\./ });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "low_vision" } });
  await waitFor(() => expect(online.browse).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({ state: home.state, vision: "low_vision", option: null })));
});

it.each([false, true])("keeps the displayed numbers after a failed shuffle transition from %s", async (alreadyShuffled) => {
  vi.spyOn(Math, "random").mockReturnValue(0.5);
  mount();
  await screen.findByRole("button", { name: /^7\./ });
  const shuffle = screen.getByRole("checkbox", { name: "Shuffle numbers" }) as HTMLInputElement;
  if (alreadyShuffled) {
    fireEvent.click(shuffle);
    await waitFor(() => expect(online.browse).toHaveBeenCalledTimes(2));
    await waitFor(() => expect((screen.getByRole("button", { name: /Open a product/ }) as HTMLButtonElement).disabled).toBe(false));
  }
  vi.mocked(online.browse).mockRejectedValueOnce(new Error("Rendering failed"));
  fireEvent.click(shuffle);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: /^7\./ }));
  await waitFor(() => expect(online.browse).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({
    option: 7, mark_seed: alreadyShuffled ? 500001 : 0,
  })));
});

it("keeps the current device and visit when a new-device request fails", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /^7\./ }));
  await screen.findByText(/Home page → \[7\] Open product/);
  await waitFor(() => expect(online.browse).toHaveBeenCalledTimes(2));
  await waitFor(() => expect((screen.getByRole("button", { name: /Open a product/ }) as HTMLButtonElement).disabled).toBe(false));
  vi.mocked(online.browse).mockRejectedValueOnce(new Error("Offline"));
  fireEvent.click(screen.getByRole("button", { name: "Mobile" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Desktop" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText(/Home page → \[7\] Open product/)).toBeTruthy();
});

it("does not start a second page transition while the first is pending", async () => {
  let release: (page: online.PageView) => void = () => {};
  vi.mocked(online.browse).mockReturnValueOnce(new Promise((resolve) => { release = resolve; }));
  mount();
  await waitFor(() => expect(online.browse).toHaveBeenCalledTimes(1));
  const mobile = screen.getByRole("button", { name: "Mobile" }) as HTMLButtonElement;
  const shuffle = screen.getByRole("checkbox", { name: "Shuffle numbers" }) as HTMLInputElement;
  const restart = screen.getByRole("button", { name: "New visit" }) as HTMLButtonElement;
  expect(mobile.disabled && shuffle.disabled && restart.disabled).toBe(true);
  fireEvent.click(mobile);
  fireEvent.click(shuffle);
  fireEvent.click(restart);
  expect(online.browse).toHaveBeenCalledTimes(1);
  await act(async () => { release(home); });
  expect(mobile.disabled || shuffle.disabled || restart.disabled).toBe(false);
});

it("starts with the store's mobile page on a phone-sized screen", async () => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query === "(max-width: 639px)", media: query } as MediaQueryList));
  mount();
  await waitFor(() => expect(online.browse).toHaveBeenCalledWith("p1", "s1", expect.objectContaining({ state: null, device: "mobile" })));
  vi.unstubAllGlobals();
});

it("brings keyboard focus back to the options after choosing one from the list or searching", async () => {
  mount();
  const listed = (await screen.findAllByRole("button", { name: /Open product: Canvas Tote Bag/ })).find((b) => b.tabIndex !== -1)!;
  listed.focus();
  vi.mocked(online.browse).mockResolvedValueOnce(home);
  fireEvent.click(listed);
  await waitFor(() => expect(document.activeElement?.textContent).toBe("Options on this page: 2"));

  fireEvent.click(screen.getAllByRole("button", { name: /Search box/ }).find((b) => b.tabIndex !== -1)!);
  fireEvent.change(screen.getByRole("textbox", { name: "What does the shopper type?" }), { target: { value: "tote" } });
  (document.activeElement as HTMLElement).blur();
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => expect(online.browse).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({ query: "tote" })));
  await waitFor(() => expect(document.activeElement?.textContent).toBe("Options on this page: 2"));
});
