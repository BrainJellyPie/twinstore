// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { TemplateChoice } from "@/features/layouts/templateOptions";
import * as api from "@/shared/api/client";
import type { StoreTemplate } from "@/shared/api/client";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { CreateStoreWizard } from "../components/CreateStoreWizard";

const { create } = vi.hoisted(() => ({ create: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ useBlocker: () => ({ status: "idle" }) }));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), draftCustomerProfile: vi.fn(),
}));
vi.mock("@/shared/mutations/useCreateStore", () => ({ useCreateStore: () => ({ mutateAsync: create, isPending: false, error: null }) }));
vi.mock("@/features/layouts/components/TemplatePicker", () => ({
  TemplatePicker: ({ value, onChange, onTemplateSelected }: { value: TemplateChoice; onChange: (v: TemplateChoice) => void; onTemplateSelected?: (t: StoreTemplate) => void }) =>
    <div><button type="button" onClick={() => {
      onChange({ ...value, templateId: "community_pharmacy", width: 24, design_theme: "minimal", weekly_hours: Array.from({ length: 7 }, (_, index) => ({ day: index + 1, is_open: index === 6, open_hour: 23, close_hour: 24 })) });
      onTemplateSelected?.({ id: "community_pharmacy", name: "Community pharmacy", description: "Care", store_type: "pharmacy", grid: [14, 12], racks: 20, skus: 30, open_hours: [9, 21], default_style: "aisles", default_design: "minimal", default_dining_tables: 0 });
    }}>Choose pharmacy</button><button type="button" onClick={() => onChange({ ...value, width: 99 })}>Invalid size</button></div>,
}));
beforeEach(() => { create.mockResolvedValue({ metadata: { project_id: "proj_new" }, setup: { id: "setup_new" }, personaGenId: "gen_new" }); });
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.clearAllMocks(); });

function fillStore() {
  fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "My Pharmacy" } });
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "12 Market Street" } });
}

async function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"), { target: { value: "Local residents" } });
  fireEvent.click(screen.getByRole("button", { name: "Create new store" }));
  fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
}

it("creates the selected initial format with the wizard metadata", async () => {
  const created = vi.fn();
  render(<CreateStoreWizard onCreated={created} />);
  fillStore();
  fireEvent.click(screen.getByRole("button", { name: "Choose pharmacy" }));
  await submit();
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ meta: expect.objectContaining({
    name: "My Pharmacy", store_type: "pharmacy", layout: expect.objectContaining({ template_id: "community_pharmacy", width: 24, design_theme: "minimal", weekly_hours: null, open_hour: 0, close_hour: 24, closed_days: [] }),
  }) })));
  await waitFor(() => expect(created).toHaveBeenCalledWith("proj_new"));
});

it("preserves the empty-layout starting option", async () => {
  render(<CreateStoreWizard />);
  fillStore();
  fireEvent.click(screen.getByRole("checkbox", { name: "Start with a furnished store template" }));
  await submit();
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ meta: expect.objectContaining({ layout: null }) })));
});

it("does not advance with invalid template dimensions", () => {
  render(<CreateStoreWizard />);
  fillStore();
  fireEvent.click(screen.getByRole("button", { name: "Invalid size" }));
  expect((screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled).toBe(true);
  expect(create).not.toHaveBeenCalled();
});

it.each([
  ["Weekday (Mon-Fri)", [1, 2, 3, 4, 5]],
  ["Weekend (Sat-Sun)", [6, 7]],
  ["7 Days", [1, 2, 3, 4, 5, 6, 7]],
])("preserves the %s schedule through back navigation", async (label, days) => {
  render(<CreateStoreWizard />); fillStore();
  fireEvent.click(screen.getByLabelText(label));
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"), { target: { value: "Local residents" } });
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect((screen.getByLabelText("Store name") as HTMLInputElement).value).toBe("My Pharmacy");
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Local residents");
  fireEvent.click(screen.getByRole("button", { name: "Create new store" }));
  fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
  await waitFor(() => expect(create).toHaveBeenCalledOnce());
  const request = create.mock.calls[0]![0] as { meta: { weekly_schedule: { day: number; is_open: boolean }[] } };
  expect(request.meta.weekly_schedule.filter((day) => day.is_open).map((day) => day.day)).toEqual(days);
});

it("allows an empty layout without losing invalid template settings on reselect", () => {
  render(<CreateStoreWizard />); fillStore();
  fireEvent.click(screen.getByRole("button", { name: "Invalid size" }));
  expect((screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox", { name: "Start with a furnished store template" }));
  expect((screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole("checkbox", { name: "Start with a furnished store template" }));
  expect((screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled).toBe(true);
  expect(create).not.toHaveBeenCalled();
});

it.each(LOCALES)("guides required fields, reviews data and preserves request identifiers in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  render(<CreateStoreWizard />);
  const text = (key: Parameters<typeof translate>[1]) => translate(code, key);
  fireEvent.click(screen.getByRole("button", { name: text("next") }));
  expect(screen.getAllByRole("alert").map((el) => el.textContent)).toEqual([text("nameRequired"), text("addressRequired")]);
  expect(document.activeElement?.id).toBe("setup-store-name");
  fireEvent.change(screen.getByLabelText(text("storeName")), { target: { value: "  한글 매장  " } });
  fireEvent.click(screen.getByRole("button", { name: text("next") }));
  expect(document.activeElement?.id).toBe("setup-store-address");
  fireEvent.change(screen.getByLabelText(text("address")), { target: { value: "  12 Market Street  " } });
  fireEvent.click(screen.getByLabelText(text("weekdays")));
  fireEvent.click(screen.getByRole("button", { name: text("next") }));
  expect(document.activeElement?.id).toBe("setup-customer-profile");
  fireEvent.click(screen.getByRole("button", { name: text("createNewStore") }));
  expect(screen.getByRole("alert").textContent).toBe(text("profileRequired"));
  fireEvent.change(screen.getByLabelText(text("customerProfile")), { target: { value: "  동네 고객  " } });
  fireEvent.click(screen.getByRole("button", { name: text("createNewStore") }));
  const review = screen.getByRole("alertdialog");
  expect(review.textContent).toContain("한글 매장"); expect(review.textContent).toContain("12 Market Street"); expect(review.textContent).toContain("동네 고객");
  expect(create).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: text("cancel") }));
  expect(create).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: text("createNewStore") }));
  fireEvent.click(screen.getByRole("button", { name: text("generate") }));
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ meta: expect.objectContaining({ name: "한글 매장", address: "12 Market Street", customer_profile: "동네 고객", store_type: "convenience", layout: expect.objectContaining({ template_id: "urban_cvs", closed_days: [6, 7] }) }) })));
});

it("updates visible validation messages when the language changes without clearing input", () => {
  render(<CreateStoreWizard />);
  fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "My store" } });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(document.activeElement?.id).toBe("setup-store-address");
  act(() => useLocale.getState().setLocale("ja"));
  expect(screen.getByRole("alert").textContent).toBe(translate("ja", "addressRequired"));
  expect((screen.getByLabelText(translate("ja", "storeName")) as HTMLInputElement).value).toBe("My store");
  expect(document.activeElement?.id).toBe("setup-store-address");
});

it.each(LOCALES)("explains and removes an unsupported attachment in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  render(<CreateStoreWizard />);
  fireEvent.change(screen.getByLabelText(translate(code, "storeName")), { target: { value: "Test shop" } });
  fireEvent.change(screen.getByLabelText(translate(code, "address")), { target: { value: "12 Market Street" } });
  fireEvent.click(screen.getByRole("button", { name: translate(code, "next") }));
  fireEvent.change(screen.getByLabelText(translate(code, "customerProfile")), { target: { value: "Local residents" } });
  const file = new File(["data"], "wrong.txt", { type: "text/plain" });
  fireEvent.change(screen.getByLabelText(translate(code, "supplementalData")), { target: { files: [file] } });
  expect(screen.getByText("wrong.txt")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "createNewStore") }));
  expect(screen.getByRole("alert").textContent).toBe(translate(code, "supplementalFormatError"));
  expect(document.activeElement?.id).toBe("setup-supplemental-remove");
  expect(create).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "removeSelectedFile") }));
  expect(screen.queryByText("wrong.txt")).toBeNull();
  expect(document.activeElement?.id).toBe("setup-supplemental-choose");
  expect((screen.getByLabelText(translate(code, "customerProfile")) as HTMLTextAreaElement).value).toBe("Local residents");
  fireEvent.click(screen.getByRole("button", { name: translate(code, "createNewStore") }));
  await screen.findByRole("alertdialog"); expect(create).not.toHaveBeenCalled();
});

it("preserves a selected file and customer profile through Back and submits the original file", async () => {
  render(<CreateStoreWizard />); fillStore();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"), { target: { value: "Local residents" } });
  const file = new File(["age\n30"], "고객.CSV", { type: "text/csv" });
  fireEvent.change(screen.getByLabelText("Supplemental data (Optional)"), { target: { files: [file] } });
  expect(screen.getByText("File selected")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(document.activeElement?.id).toBe("setup-store-name");
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText(file.name)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Create new store" }));
  expect(screen.getByRole("alertdialog").textContent).toContain(file.name);
  fireEvent.click(screen.getByRole("button", { name: "Generate" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ supplemental: file })));
});


it("drafts the customer profile from the store details, in the form's language", async () => {
  vi.mocked(api.draftCustomerProfile).mockResolvedValue({ profile: "Pharmacy regulars and evening commuters." });
  render(<CreateStoreWizard />);
  fillStore();
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.click(screen.getByRole("button", { name: "Write one from the store details" }));
  await waitFor(() => expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value)
    .toBe("Pharmacy regulars and evening commuters."));
  expect(api.draftCustomerProfile).toHaveBeenCalledWith(expect.objectContaining({ name: "My Pharmacy", address: "12 Market Street", locale: "en" }));
  expect(screen.getByText(/Drafted from the store details/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"), { target: { value: "Edited" } });
  expect(screen.queryByText(/Drafted from the store details/)).toBeNull();
});
