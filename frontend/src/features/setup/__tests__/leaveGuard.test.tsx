// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createBrowserHistory, createMemoryHistory, createRootRoute, createRoute, createRouter, Link, Outlet, RouterProvider } from "@tanstack/react-router";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { CreateStoreWizard } from "../components/CreateStoreWizard";
vi.mock("@/features/settings/useModelSetup", () => import("@/features/settings/__tests__/modelSetupWithKey"));

const created = vi.hoisted(() => ({ isSuccess: false, mutateAsync: vi.fn() }));
vi.mock("@/shared/mutations/useCreateStore", () => ({ useCreateStore: () => ({ ...created, isPending: false, error: null }) }));
vi.mock("@/features/layouts/components/TemplatePicker", () => ({ TemplatePicker: () => null }));
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); created.isSuccess = false; vi.clearAllMocks(); });

function show(history = createMemoryHistory({ initialEntries: ["/projects/new"] })) {
  const root = createRootRoute({ component: () => <><Link to="/">Stores</Link><Outlet /></> });
  const home = createRoute({ getParentRoute: () => root, path: "/", component: () => <h1>Store list</h1> });
  const wizard = createRoute({ getParentRoute: () => root, path: "/projects/new", component: () => <CreateStoreWizard /> });
  const router = createRouter({ routeTree: root.addChildren([home, wizard]), history });
  render(<RouterProvider router={router} />);
  return router;
}

it("leaves a pristine form without asking", async () => {
  const router = show();
  await screen.findByLabelText("Store name");
  fireEvent.click(screen.getByRole("link", { name: "Stores" }));
  await screen.findByRole("heading", { name: "Store list" });
  expect(router.state.location.pathname).toBe("/");
});

it("keeps an explicit automatic-product preference when the user cancels leaving", async () => {
  const router = show();
  const label = translate("en", "automaticStarterProducts");
  fireEvent.click(await screen.findByLabelText(label));
  fireEvent.click(screen.getByRole("link", { name: "Stores" }));
  await screen.findByRole("alertdialog");
  fireEvent.click(screen.getByRole("button", { name: translate("en", "keepEditing") }));
  expect(router.state.location.pathname).toBe("/projects/new");
  expect((screen.getByLabelText(label) as HTMLInputElement).checked).toBe(false);
});

it("asks before leaving entered details and stays when the user keeps editing", async () => {
  useLocale.getState().setLocale("ko");
  const router = show();
  fireEvent.change(await screen.findByLabelText(translate("ko", "storeName")), { target: { value: "Corner shop" } });
  fireEvent.click(screen.getByRole("link", { name: "Stores" }));
  const dialog = await screen.findByRole("alertdialog");
  expect(dialog.textContent).toContain(translate("ko", "leaveNewStoreTitle"));
  fireEvent.click(screen.getByRole("button", { name: translate("ko", "keepEditing") }));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(router.state.location.pathname).toBe("/projects/new");
  expect((screen.getByLabelText(translate("ko", "storeName")) as HTMLInputElement).value).toBe("Corner shop");

  fireEvent.click(screen.getByRole("link", { name: "Stores" }));
  fireEvent.click(await screen.findByRole("button", { name: translate("ko", "leaveNewStore") }));
  await screen.findByRole("heading", { name: "Store list" });
});

it("warns before the tab closes or reloads only once details were entered", async () => {
  window.history.replaceState(null, "", "/projects/new");
  show(createBrowserHistory());
  const unload = async () => {
    const event = new Event("beforeunload", { cancelable: true });
    await act(async () => { window.dispatchEvent(event); });
    return event.defaultPrevented;
  };
  await screen.findByLabelText("Store name");
  expect(await unload()).toBe(false);
  fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "Corner shop" } });
  expect(await unload()).toBe(true);
});

it("does not block leaving once the store was created", async () => {
  show();
  fireEvent.change(await screen.findByLabelText("Store name"), { target: { value: "Corner shop" } });
  created.isSuccess = true;
  // A re-render picks up the finished mutation, as it does when the real mutation resolves.
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "12 Market Street" } });
  fireEvent.click(screen.getByRole("link", { name: "Stores" }));
  await screen.findByRole("heading", { name: "Store list" });
  expect(screen.queryByRole("alertdialog")).toBeNull();
});
