// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { StorefrontCard } from "../StorefrontCard";
vi.mock("@/shared/api/client", () => ({ rateStorefront: vi.fn() }));
const clients: QueryClient[] = [];
const create = vi.fn(), revoke = vi.fn();
const town: api.Town = { id: "original", name: "Original", archetype: "residential", size_m: 800, buildings: [], roads: [], source: "procedural", center_lat: null, center_lon: null, focal_venue_id: "store", venues: [
  { id: "store", name: "Our store", category: "convenience", x: 400, y: 400, attractiveness: 1, open_hour: 0, close_hour: 24, is_focal: true },
  { id: "rival", name: "Rival", category: "supermarket", x: 300, y: 300, attractiveness: 1, open_hour: 0, close_hour: 24, is_focal: false },
] };
const result: api.StorefrontResult = { venue_id: "store", previous_attractiveness: 1, town, appeal: { method: "image_stats", model: "", signage: 5, entrance: 5, window: 5, upkeep: 5, overall: 5, attractiveness: 1.2, reasons: "Photo evaluation" } };
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
beforeEach(() => { let n = 0; create.mockImplementation(() => `blob:photo-${++n}`); vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke }); vi.mocked(api.rateStorefront).mockResolvedValue(result); });
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.resetAllMocks(); vi.unstubAllGlobals(); });
function mount(current = town) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } }); clients.push(client);
  const onTown = vi.fn(); const view = (t: api.Town, pid = "alpha") => <QueryClientProvider client={client}><StorefrontCard projectId={pid} town={t} onTown={onTown} /></QueryClientProvider>;
  return { ...render(view(current)), onTown, view };
}
function pick(name = "front.png") { const file = new File(["photo"], name, { type: "image/png" }); fireEvent.change(document.querySelector("input[type=file]")!, { target: { files: [file] } }); return file; }
it("uses an existing venue after the selected rival disappears", async () => {
  const { rerender, view } = mount(); fireEvent.change(screen.getByRole("combobox"), { target: { value: "rival" } });
  rerender(view({ ...town, venues: [town.venues[0]!] })); const file = pick();
  await waitFor(() => expect(api.rateStorefront).toHaveBeenCalledWith("alpha", "store", file));
});
it("clears a previous photo and score when the neighborhood is replaced", async () => {
  const { rerender, view } = mount(); pick(); await screen.findByText("Photo evaluation"); rerender(view({ ...town, id: "replacement", name: "Replacement" }));
  expect(screen.queryByText("Photo evaluation")).toBeNull(); expect(screen.queryByRole("img", { name: "Storefront" })).toBeNull(); expect(revoke).toHaveBeenCalledWith("blob:photo-1");
});
it("does not upload when no current venue can be rated", async () => {
  mount({ ...town, venues: [] }); expect((screen.getByRole("button", { name: "Upload a storefront photo" }) as HTMLButtonElement).disabled).toBe(true); pick(); await act(async () => {}); expect(api.rateStorefront).not.toHaveBeenCalled();
});
it("coalesces rapid file selections while a rating is pending", async () => {
  const pending = deferred<api.StorefrontResult>(); vi.mocked(api.rateStorefront).mockReturnValue(pending.promise); mount(); pick("first.png"); pick("second.png");
  await waitFor(() => expect(api.rateStorefront).toHaveBeenCalledTimes(1)); expect(create).toHaveBeenCalledTimes(1); expect((screen.getByRole("button", { name: /Rating…$/ }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => pending.resolve(result)); await screen.findByText("Photo evaluation");
});
it.each(["replace", "edit", "project", "unmount"])("does not apply a late photo response after %s", async kind => {
  const pending = deferred<api.StorefrontResult>(); vi.mocked(api.rateStorefront).mockReturnValue(pending.promise); const { rerender, view, unmount, onTown } = mount(); pick(); await waitFor(() => expect(api.rateStorefront).toHaveBeenCalledOnce());
  if (kind === "unmount") unmount(); else if (kind === "project") rerender(view(town, "beta")); else rerender(view({ ...town, id: kind === "replace" ? "other-town" : town.id, name: "Changed while rating" }));
  await act(async () => pending.resolve(result)); await act(async () => {}); expect(onTown).not.toHaveBeenCalled(); expect(screen.queryByText("Photo evaluation")).toBeNull();
});
it("releases previews when replacing photos, switching venues, and leaving the card", async () => {
  const { unmount } = mount(); pick(); await screen.findByText("Photo evaluation"); pick("second.png"); await waitFor(() => expect(api.rateStorefront).toHaveBeenCalledTimes(2)); await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:photo-1"));
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "rival" } }); expect(revoke).toHaveBeenCalledWith("blob:photo-2"); pick("rival.png"); await waitFor(() => expect(api.rateStorefront).toHaveBeenCalledTimes(3)); unmount(); expect(revoke).toHaveBeenCalledWith("blob:photo-3");
});
it("clears a failed rating when selecting another venue and supports a retry", async () => {
  vi.mocked(api.rateStorefront).mockRejectedValueOnce(new Error("Rating unavailable")); mount(); pick(); await screen.findByText("Rating unavailable"); fireEvent.change(screen.getByRole("combobox"), { target: { value: "rival" } }); expect(screen.queryByText("Rating unavailable")).toBeNull();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "store" } }); pick(); await screen.findByText("Photo evaluation"); expect(api.rateStorefront).toHaveBeenCalledTimes(2);
});
it("falls back to an eligible rival when the focal venue is absent", async () => {
  mount({ ...town, venues: [town.venues[1]!] }); const file = pick(); await waitFor(() => expect(api.rateStorefront).toHaveBeenCalledWith("alpha", "rival", file));
});
it("keeps an existing rival selection when other neighborhood data changes", async () => {
  const { rerender, view } = mount(); fireEvent.change(screen.getByRole("combobox"), { target: { value: "rival" } }); rerender(view({ ...town, name: "Renamed" })); const file = pick();
  await waitFor(() => expect(api.rateStorefront).toHaveBeenCalledWith("alpha", "rival", file));
});
it("ignores a cancelled picker without allocating a preview or sending a request", async () => {
  mount(); fireEvent.change(document.querySelector("input[type=file]")!, { target: { files: [] } }); await act(async () => {}); expect(create).not.toHaveBeenCalled(); expect(api.rateStorefront).not.toHaveBeenCalled();
});
it("applies a current response once and hides its old score while evaluating the next photo", async () => {
  const { onTown } = mount(); pick(); await screen.findByText("Photo evaluation"); expect(onTown).toHaveBeenCalledExactlyOnceWith(town);
  const pending = deferred<api.StorefrontResult>(); vi.mocked(api.rateStorefront).mockReturnValueOnce(pending.promise); pick("second.png"); expect(screen.queryByText("Photo evaluation")).toBeNull();
  await act(async () => pending.resolve(result)); await screen.findByText("Photo evaluation"); expect(onTown).toHaveBeenCalledTimes(2);
});
