// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { CreateStoreWizard } from "../components/CreateStoreWizard";

const picked = vi.hoisted(() => ({ value: null as null | { templateId: string; currency: string } }));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof import("@/shared/api/client")>(), draftStoreSetup: vi.fn() }));
vi.mock("@/shared/mutations/useCreateStore", () => ({ useCreateStore: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }) }));
vi.mock("@/features/layouts/components/TemplatePicker", () => ({
  TemplatePicker: ({ value }: { value: { templateId: string; currency: string } }) => { picked.value = value; return null; },
}));
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); picked.value = null; });

const DRAFT: api.StoreSetupDraft = {
  name: "Campus Mart", description: "A store students use between classes.", address: "Chung-Ang University, Seoul",
  store_type: "convenience", template_id: "campus_cvs", open_days: "weekday", open_hour: 7, close_hour: 23, currency: "KRW",
  rationale: "", warnings: [],
};
function deferred() {
  let resolve!: (v: api.StoreSetupDraft) => void;
  const promise = new Promise<api.StoreSetupDraft>((yes) => { resolve = yes; });
  return { promise, resolve };
}

it("fills the store form and the starting format from one description", async () => {
  vi.mocked(api.draftStoreSetup).mockResolvedValue(DRAFT);
  render(<CreateStoreWizard />);
  fireEvent.change(screen.getByLabelText("Describe the store in your own words"), { target: { value: "Campus store at CAU, weekdays 7 to 23" } });
  fireEvent.click(screen.getByRole("button", { name: "Fill in the form" }));
  expect(await screen.findByText(/Filled in from your description/)).toBeTruthy();
  expect(api.draftStoreSetup).toHaveBeenCalledWith({ text: "Campus store at CAU, weekdays 7 to 23", locale: "en" });
  expect((screen.getByLabelText("Store name") as HTMLInputElement).value).toBe("Campus Mart");
  expect((screen.getByLabelText("Address") as HTMLInputElement).value).toBe("Chung-Ang University, Seoul");
  expect(picked.value).toMatchObject({ templateId: "campus_cvs", currency: "KRW" });
});

it("drops an answer requested before the user edited the form", async () => {
  const request = deferred();
  vi.mocked(api.draftStoreSetup).mockReturnValue(request.promise);
  render(<CreateStoreWizard />);
  fireEvent.change(screen.getByLabelText("Describe the store in your own words"), { target: { value: "A campus store" } });
  fireEvent.click(screen.getByRole("button", { name: "Fill in the form" }));
  fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "My own name" } });
  await act(async () => { request.resolve(DRAFT); await request.promise; });
  expect((screen.getByLabelText("Store name") as HTMLInputElement).value).toBe("My own name");
  expect(screen.queryByText(/Filled in from your description/)).toBeNull();
});
