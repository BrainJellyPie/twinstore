// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { onTabKeys } from "../tabKeys";

afterEach(cleanup);
const IDS = ["ab", "shelf", "concept"] as const;

function Tabs() {
  const [tab, setTab] = useState<(typeof IDS)[number]>("ab");
  return (
    <div role="tablist" aria-label="Tools" onKeyDown={(e) => onTabKeys(e, IDS, tab, setTab)}>
      {IDS.map((id) => <button key={id} type="button" role="tab" aria-selected={tab === id} tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}>{id}</button>)}
    </div>
  );
}

it("moves the selection and focus with the arrow, Home and End keys, wrapping at the ends", () => {
  render(<Tabs />);
  const tab = (name: string) => screen.getByRole("tab", { name });
  tab("ab").focus();
  for (const [key, expected] of [["ArrowRight", "shelf"], ["ArrowRight", "concept"], ["ArrowRight", "ab"], ["ArrowLeft", "concept"], ["Home", "ab"], ["End", "concept"]]) {
    fireEvent.keyDown(document.activeElement!, { key });
    expect(document.activeElement).toBe(tab(expected!));
    expect(tab(expected!).getAttribute("aria-selected")).toBe("true");
    expect(screen.getAllByRole("tab").filter((t) => t.tabIndex === 0)).toEqual([tab(expected!)]);
  }
  fireEvent.keyDown(document.activeElement!, { key: "a" });
  expect(document.activeElement).toBe(tab("concept"));
});
