// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { ShopperChat } from "../ShopperChat";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getModels: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({
  ...await original<typeof online>(), getShopperInterview: vi.fn(), askOnlineShopper: vi.fn(), clearShopperInterview: vi.fn(),
}));

const shopper = { id: "os0004", identity: "Night-shift nurse, saving up" } as online.OnlineShopper;
const empty: online.OnlineInterview = { run_id: "r", variant: 1, shopper_id: "os0004", model: "", messages: [] };
const question = "What made you leave without buying?";

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
  useLocale.getState().setLocale("en");
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(online.getShopperInterview).mockResolvedValue(empty);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function mount() {
  const onStep = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <ShopperChat projectId="p1" runId="r" variant={1} shopper={shopper} outcome="left" onStep={onStep} />
  </QueryClientProvider>);
  return onStep;
}

it("asks a suggested question and opens the step the answer points at", async () => {
  vi.mocked(online.askOnlineShopper).mockResolvedValue({ ...empty, model: "m", messages: [
    { role: "interviewer", text: question, steps: [], created_at: "" },
    { role: "shopper", text: "The delivery fee was more than the item.", steps: [6], created_at: "" },
  ] });
  const onStep = mount();
  expect(await screen.findByText(/Ask Night-shift nurse about this visit/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: question }));
  expect(await screen.findByText("The delivery fee was more than the item.")).toBeTruthy();
  expect(online.askOnlineShopper).toHaveBeenCalledWith("p1", "r", 1, "os0004", question, "");
  fireEvent.click(screen.getByRole("button", { name: "step 6" }));
  expect(onStep).toHaveBeenCalledWith(5);
});

it("keeps the question and explains what to do when the shopper cannot answer", async () => {
  vi.mocked(online.askOnlineShopper).mockRejectedValue(new Error("502 Bad Gateway: rate limited"));
  mount();
  const box = await screen.findByRole("textbox", { name: "Ask Night-shift nurse…" }) as HTMLTextAreaElement;
  fireEvent.change(box, { target: { value: "Was the price fair?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("The shopper could not answer.");
  expect(alert.textContent).toContain("rate limited");
  await waitFor(() => expect(box.value).toBe("Was the price fair?"));
});
