// @vitest-environment jsdom
import { useState } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { DEFAULT_VALUES, type WizardValues } from "../validate";
import { Step2Fields } from "../components/Step2Fields";
import { CreateStoreWizard } from "../components/CreateStoreWizard";
vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(), draftCustomerProfile: vi.fn() }));
vi.mock("@/shared/mutations/useCreateStore", () => ({ useCreateStore: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }) }));
vi.mock("@/features/layouts/components/TemplatePicker", () => ({ TemplatePicker: () => null }));
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); });
const BASE: WizardValues = { ...DEFAULT_VALUES, name: "Campus store", address: "12 Main Street", storeType: "convenience", customerProfile: "Original profile" };
function deferred() {
  let resolve!: (value: { profile: string }) => void; let reject!: (error: Error) => void;
  const promise = new Promise<{ profile: string }>((yes,no) => { resolve=yes; reject=no; }); return { promise,resolve,reject };
}
function Form({ changes = {}, disabled = false }: { changes?: Partial<WizardValues>; disabled?: boolean }) {
  const [profile,setProfile] = useState(BASE.customerProfile);
  return <Step2Fields values={{ ...BASE,...changes,customerProfile:profile }} errors={undefined} disabled={disabled} onChange={(key,value) => { if(key==="customerProfile") setProfile(value as string); }} />;
}
function begin() { fireEvent.click(screen.getByRole("button", { name: translate(useLocale.getState().locale, "draftCustomerProfile") })); }
const CHANGES = ["name","description","address","storeType","openHour","closeHour","workingDayPreset"] as const;
const NEXT: Partial<WizardValues> = { name:"Changed store",description:"New description",address:"99 Other Street",storeType:"pharmacy",openHour:8,closeHour:20,workingDayPreset:"weekday" };
it.each(CHANGES)("does not apply a profile drafted before changing %s", async key => {
  const request=deferred();vi.mocked(api.draftCustomerProfile).mockReturnValue(request.promise);const view=render(<Form />);begin();
  view.rerender(<Form changes={{ [key]: NEXT[key] }} />);
  await act(async () => { request.resolve({ profile:"Outdated profile" });await request.promise; });
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Original profile");
  expect(screen.queryByText(/Drafted from the store details/)).toBeNull();
});
it.each(["success","failure"])("preserves profile edits while an old draft ends with %s", async outcome => {
  const request=deferred();vi.mocked(api.draftCustomerProfile).mockReturnValue(request.promise);render(<Form />);begin();
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"),{target:{value:"My newer profile"}});
  await act(async () => { if(outcome==="success") request.resolve({profile:"Old profile"});else request.reject(new Error("Old failure")); });
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("My newer profile");
  expect(screen.queryByText("Old failure")).toBeNull();
  expect((screen.getByRole("button",{name:"Write one from the store details"}) as HTMLButtonElement).disabled).toBe(false);
});
it.each(["ko","zh","ja","es","fr"] as const)("does not apply a draft requested before switching to %s", async locale => {
  const request=deferred();vi.mocked(api.draftCustomerProfile).mockReturnValue(request.promise);render(<Form />);begin();
  act(() => useLocale.getState().setLocale(locale));
  await act(async () => {request.resolve({profile:"Old English profile"});await request.promise;});
  expect((screen.getByLabelText(translate(locale,"customerProfile")) as HTMLTextAreaElement).value).toBe("Original profile");
});
it("ignores an answer after leaving the customer step and returning",async () => {
  const request=deferred();vi.mocked(api.draftCustomerProfile).mockReturnValue(request.promise);render(<CreateStoreWizard />);
  fireEvent.change(screen.getByLabelText("Store name"),{target:{value:"First store"}});fireEvent.change(screen.getByLabelText("Address"),{target:{value:"12 Main Street"}});
  fireEvent.click(screen.getByRole("button",{name:"Next"}));begin();fireEvent.click(screen.getByRole("button",{name:"Back"}));
  fireEvent.change(screen.getByLabelText("Store name"),{target:{value:"Second store"}});fireEvent.click(screen.getByRole("button",{name:"Next"}));
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"),{target:{value:"Second store customers"}});
  await act(async () => {request.resolve({profile:"First store customers"});await request.promise;});
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Second store customers");
});
it("allows a revised request and applies only its answer when responses reverse",async () => {
  const old=deferred(),current=deferred();vi.mocked(api.draftCustomerProfile).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);render(<Form />);begin();
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"),{target:{value:"Changed profile"}});begin();
  await waitFor(() => expect(api.draftCustomerProfile).toHaveBeenCalledTimes(2));
  await act(async () => {current.resolve({profile:"Newest result"});await current.promise;old.resolve({profile:"Old result"});await old.promise;});
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Newest result");
});
it("leaves a current failure retryable without losing the original profile",async () => {
  vi.mocked(api.draftCustomerProfile).mockRejectedValueOnce(new Error("Temporary failure")).mockResolvedValueOnce({profile:"Retry result"});render(<Form />);begin();await screen.findByText("Temporary failure");
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Original profile");begin();
  await waitFor(() => expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Retry result"));
  expect(screen.getByText(/Drafted from the store details/)).toBeTruthy();
});
it("invalidates a draft when the form becomes disabled for submission",async () => {
  const request=deferred();vi.mocked(api.draftCustomerProfile).mockReturnValue(request.promise);const view=render(<Form />);begin();view.rerender(<Form disabled />);
  await act(async () => {request.resolve({profile:"Late submission draft"});await request.promise;});
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Original profile");
});
