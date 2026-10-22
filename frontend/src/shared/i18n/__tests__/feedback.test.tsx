// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ApiError } from "@/shared/api/errors";
import { RequestError } from "@/shared/components/RequestError";
import { Dialog, DialogContent, DialogFooter, DialogTitle, DialogDescription } from "@/shared/components/ui/dialog";
import { LOCALES } from "../messages";
import { translate, useLocale } from "../i18n";
import { UserMessageError } from "../userMessage";

afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });
it.each(LOCALES)("translates footer dismissal and validation after switching to $code", ({ code }) => {
  useLocale.getState().setLocale("en");
  render(<Dialog open><DialogContent showCloseButton={false}>
    <DialogTitle>Fixture</DialogTitle><DialogDescription>Fixture description</DialogDescription>
    <RequestError error={new UserMessageError("photosMissingSelection")} />
    <DialogFooter showCloseButton />
  </DialogContent></Dialog>);
  act(() => useLocale.getState().setLocale(code));
  expect(screen.getByRole("button", { name: translate(code, "close") })).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toBe(translate(code, "photosMissingSelection"));
});
it.each([
  [409, "requestConflict"], [404, "requestMissing"], [413, "requestLarge"],
  [400, "requestInvalid"], [422, "requestInvalid"], [503, "requestFailed"],
] as const)("gives actionable localized guidance for HTTP %s without altering diagnostics", (status, key) => {
  const detail = 'SKU <script>alert(1)</script> {count} 茶';
  useLocale.getState().setLocale("ko");
  render(<RequestError error={new ApiError(detail, status)} />);
  expect(screen.getByRole("alert").textContent).toContain(translate("ko", key));
  expect(screen.getByText(detail)).toBeTruthy();
  expect(document.querySelector("script")).toBeNull();
  const details = screen.getByText(translate("ko", "requestDetails")).closest("details");
  expect(details?.open).toBe(false);
  act(() => useLocale.getState().setLocale("es"));
  expect(screen.getByRole("alert").textContent).toContain(translate("es", key));
  expect(screen.getByText(detail)).toBeTruthy();
});
