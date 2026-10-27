// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { PAGE_STYLES, type PageStyle } from "@/shared/api/online";
import { StylePicker } from "../StylePicker";

afterEach(cleanup);

function Harness() {
  const [style, setStyle] = useState<PageStyle>(PAGE_STYLES[0]!);
  return <StylePicker projectId="p" siteId="s" storeName="Shop" version="1" saved={PAGE_STYLES[0]!} value={style} onChange={setStyle} />;
}

it("picks the next page style with the arrow keys and keeps only the picked one in the Tab order", () => {
  render(<Harness />);
  const radios = screen.getAllByRole("radio");
  expect(radios.filter((r) => r.tabIndex === 0)).toEqual([radios[0]]);
  radios[0]!.focus();
  fireEvent.keyDown(radios[0]!, { key: "ArrowRight" });
  expect(radios[1]!.getAttribute("aria-checked")).toBe("true");
  expect(document.activeElement).toBe(radios[1]);
  fireEvent.keyDown(radios[1]!, { key: "End" });
  expect(radios[radios.length - 1]!.getAttribute("aria-checked")).toBe("true");
  expect(screen.getAllByRole("radio").filter((r) => r.tabIndex === 0)).toEqual([radios[radios.length - 1]]);
});
