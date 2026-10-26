// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";

afterEach(cleanup);

function OpenedFromState({ choose }: { choose?: (event: Event) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Watch a shopper</button>
      <button type="button">Elsewhere</button>
      {open && (
        <Dialog open onOpenChange={(next) => { if (!next) setOpen(false); }}>
          <DialogContent onCloseAutoFocus={choose}>
            <DialogTitle>Visit</DialogTitle>
            <DialogDescription>Replay</DialogDescription>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}

it("gives focus back to the button that opened a dialog from state", async () => {
  render(<OpenedFromState />);
  const opener = screen.getByRole("button", { name: "Watch a shopper" });
  opener.focus();
  fireEvent.click(opener);
  await waitFor(() => expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(true));
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  await waitFor(() => expect(document.activeElement).toBe(opener));
});

it("leaves the choice to a dialog that places focus itself", async () => {
  const elsewhere = () => screen.getByRole("button", { name: "Elsewhere" });
  render(<OpenedFromState choose={(event) => { event.preventDefault(); elsewhere().focus(); }} />);
  const opener = screen.getByRole("button", { name: "Watch a shopper" });
  opener.focus();
  fireEvent.click(opener);
  await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
  fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  await waitFor(() => expect(document.activeElement).toBe(elsewhere()));
});
