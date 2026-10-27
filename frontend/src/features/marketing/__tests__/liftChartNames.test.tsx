// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { LiftChart } from "../charts";

afterEach(cleanup);

it("keeps a long arm name whole in a tooltip where the row cuts it off", () => {
  const label = "Coca-Cola Classic 1 Liter: -30 % off, tag shows the was-price";
  render(<LiftChart rows={[{ key: "b", label, sub: "Price cut test", diff: 0.1, lo: 0.05, hi: 0.15 }]} format={String} axisLabel="Spend" />);
  expect(screen.getByText(label).getAttribute("title")).toBe(label);
  expect(screen.getByText("Price cut test").getAttribute("title")).toBe("Price cut test");
});
