// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { getLibraryPhotos } from "@/shared/api/libraryPhotos";
import { getProductCatalog } from "@/shared/api/productEdits";
import { getRackCopyOptions } from "@/shared/api/rackCopy";
import { getStarterCatalog } from "@/shared/api/starterFill";
import { RequestError } from "@/shared/components/RequestError";
import { useLocale, translate } from "../i18n";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); });
const clients = [
  { name: "library photos", run: () => getLibraryPhotos("p", "s") },
  { name: "bulk editor", run: () => getProductCatalog("p", "s") },
  { name: "rack copies", run: () => getRackCopyOptions("p", "s", "") },
  { name: "starter fill", run: () => getStarterCatalog("p", "s") },
];
const failures = [
  { status: 409, key: "requestConflict" },
  { status: 422, key: "requestInvalid" },
  { status: 413, key: "requestLarge" },
] as const;
it.each(clients.flatMap(client => failures.map(failure => ({ ...client, ...failure }))))(
  "$name preserves HTTP $status through the real client to the translated error UI", async ({ run, status, key }) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Original server explanation" }), { status })));
    const error: unknown = await run().catch((cause: unknown) => cause);
    useLocale.getState().setLocale("ja");
    render(<RequestError error={error} />);
    expect(screen.getByRole("alert").textContent).toContain(translate("ja", key));
    expect(screen.getByText("Original server explanation")).toBeTruthy();
  },
);
