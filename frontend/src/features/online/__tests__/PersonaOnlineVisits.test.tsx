// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { PersonaOnlineVisits } from "../PersonaOnlineVisits";

vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getPersonaVisits: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, search, className }: { children: ReactNode; className?: string; search: { run: string; shopper: string; variant: number } }) =>
    <a className={className} href={`/online/p?run=${search.run}&shopper=${search.shopper}&variant=${search.variant}`}>{children}</a>,
}));
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <PersonaOnlineVisits projectId="p" personaId="persona_1" />
  </QueryClientProvider>);
}

it("lists the customer's online visits, each linking to its replay", async () => {
  vi.mocked(online.getPersonaVisits).mockResolvedValue([
    { run_id: "r1", run_name: "Coupon test", created_at: "", variant: 1, site_name: "Tea shop B", shopper_id: "os0003",
      outcome: "purchased", order_total: 1299, currency: "USD" },
  ]);
  show();
  const link = await screen.findByRole("link", { name: /Tea shop B/ });
  expect(link.getAttribute("href")).toBe("/online/p?run=r1&shopper=os0003&variant=1");
  expect(link.textContent).toContain("Coupon test");
  expect(link.textContent).toContain("Ordered · $12.99");
  expect(online.getPersonaVisits).toHaveBeenCalledWith("p", "persona_1", expect.anything());
});

it("shows nothing for a customer who never shopped online", async () => {
  vi.mocked(online.getPersonaVisits).mockResolvedValue([]);
  show();
  await new Promise((r) => setTimeout(r, 20));
  expect(screen.queryByRole("region")).toBeNull();
});
