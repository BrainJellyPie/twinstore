// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useLayoutEffect, useState } from "react";

import * as api from "@/shared/api/client";
import { LayoutBriefField } from "../components/LayoutBriefField";
import { DEFAULT_TEMPLATE_CHOICE, type TemplateChoice } from "../templateOptions";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), readLayoutBrief: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

let latest: TemplateChoice = DEFAULT_TEMPLATE_CHOICE;
function Harness() {
  const [value, setValue] = useState<TemplateChoice>({ ...DEFAULT_TEMPLATE_CHOICE, density: "dense" });
  useLayoutEffect(() => { latest = value; }, [value]);
  return <LayoutBriefField value={value} onApply={(patch) => setValue((v) => ({ ...v, ...patch }))}
    onBriefChange={(requirements) => setValue((v) => ({ ...v, requirements }))} />;
}

it("applies the options a brief asks for and lists what the options cannot express", async () => {
  vi.mocked(api.readLayoutBrief).mockResolvedValue({
    options: { style: "loop", checkouts: 2, design_theme: "botanical" }, applied: ["Style: loop", "Tills: 2", "Theme: botanical"],
    not_expressible: ["warm task lighting"], warnings: ['No category "Moon rocks" in this format; nothing was left out for it.'],
    rationale: "A calm loop with two tills.",
  });
  render(<QueryClientProvider client={new QueryClient()}><Harness /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "A calm loop with two tills, botanical, warm task lighting" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply to the options" }));
  expect(await screen.findByText("Tills: 2")).toBeTruthy();
  await waitFor(() => expect(latest.style).toBe("loop"));
  expect(latest.checkouts).toBe(2);
  expect(latest.density).toBe("dense");  // options the brief did not mention stay as chosen
  expect(latest.requirements).toBe("A calm loop with two tills, botanical, warm task lighting");
  const [templateId, req] = vi.mocked(api.readLayoutBrief).mock.calls[0]!;
  expect(templateId).toBe("urban_cvs");
  expect(req.brief).toBe("A calm loop with two tills, botanical, warm task lighting");
  expect(req.options).toMatchObject({ density: "dense" });
  expect(req.options).not.toHaveProperty("templateId");
  expect(screen.getByText(/Not set by the options \(kept in the brief\): warm task lighting\./)).toBeTruthy();
  // Editing the brief retires the reading shown for the old words.
  fireEvent.change(screen.getByLabelText("Additional design brief"), { target: { value: "A dense grid" } });
  expect(screen.queryByText("Tills: 2")).toBeNull();
});
