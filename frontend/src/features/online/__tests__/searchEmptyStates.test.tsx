// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { OnlineRunResult, OnlineTemplate } from "@/shared/api/online";
import { ShopperGallery } from "../ShopperGallery";
import { TemplateGallery } from "../TemplateGallery";

afterEach(cleanup);

it("announces that no template matches the search", () => {
  render(<QueryClientProvider client={new QueryClient()}>
    <TemplateGallery projectId="p" currency="USD" templates={[] as OnlineTemplate[]} loading={false} error={null} setups={[]} onCreated={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Search templates"), { target: { value: "zzz" } });
  expect(screen.getByRole("status").textContent).toBe("No template matches. Try another word.");
});

it("announces that no shopper card matches the search", () => {
  const result = {
    shoppers: [{ id: "s1", identity: "Student", mission: "browse", age_group: "20s", gender: "Female", device: "mobile" }],
    variants: [{ site_name: "Shop" }], visits: {}, rival_name: null,
  } as unknown as OnlineRunResult;
  render(<ShopperGallery result={result} money={String} onWatch={vi.fn()} onCompare={vi.fn()} onSteps={vi.fn()} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "zzz" } });
  expect(screen.getByRole("status").textContent).toBe("No shopper matches.");
});
