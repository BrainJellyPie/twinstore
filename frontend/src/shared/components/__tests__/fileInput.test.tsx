// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Input } from "@/shared/components/ui/input";
import { useLocale } from "@/shared/i18n/i18n";

afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

it("words a file field in the app's language and names the chosen file, keeping its label's own text", () => {
  useLocale.getState().setLocale("ko");
  const onChange = vi.fn();
  const { container } = render(<label>Inventory CSV<Input type="file" accept=".csv" onChange={onChange} /></label>);
  const words = () => [...container.querySelectorAll("[data-text]")].map((node) => node.getAttribute("data-text"));
  expect(words()).toEqual(["파일 선택", "선택한 파일 없음"]);
  const input = screen.getByLabelText("Inventory CSV");
  fireEvent.change(input, { target: { files: [new File(["a"], "stock.csv")] } });
  expect(words()).toEqual(["파일 선택", "stock.csv"]);
  expect(onChange).toHaveBeenCalledOnce();
});
