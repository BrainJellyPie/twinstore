// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { ProjectListItem } from "@/shared/api/client";
import { StoreTile } from "../StoreTile";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, params, children, ...props }: { to: string; params: { pid: string }; children: ReactNode; className?: string }) =>
    <a href={to.replace("$pid", params.pid)} {...props}>{children}</a>,
}));

afterEach(cleanup);

const project: ProjectListItem = {
  project_id: "shop-1", name: "Test shop", description: "", store_type: "cafe", grid_size: [12, 10],
  weekly_schedule: [], created_at: "2026-10-21", updated_at: "2026-10-21", status: "Ready",
};

it.each([
  ["__proto__", "Proto"], ["constructor", "Constructor"], ["toString", "ToString"],
  ["hasOwnProperty", "HasOwnProperty"], ["cafe", "Café"], ["pizza_shop", "Pizza shop"],
  ["two-floor shop", "Two floor shop"], ["", "Store"],
])("renders the custom store type %j without losing access to its pages", (type, label) => {
  const onOpen = vi.fn();
  render(<StoreTile project={{ ...project, store_type: type }} onOpen={onOpen} />);
  expect(screen.getByText(label)).toBeTruthy();
  fireEvent.click(screen.getByRole("button"));
  expect(onOpen).toHaveBeenCalledTimes(1);
  for (const [name, href] of [["Floor", "/projects/shop-1"], ["Market", "/marketing/shop-1"], ["Capture", "/capture/shop-1"], ["Area", "/town/shop-1"]]) {
    expect(screen.getByRole("link", { name }).getAttribute("href")).toBe(href);
  }
});
