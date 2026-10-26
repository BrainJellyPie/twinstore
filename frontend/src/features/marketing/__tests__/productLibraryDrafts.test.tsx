// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { marketingKeys } from "@/shared/api/marketing";
import { ProductLibrary } from "../ProductLibrary";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), listPackages: vi.fn(), updatePackage: vi.fn(),
}));
const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.clearAllMocks(); });
const ASSET: api.PackageAsset = { asset_id: "pkg_test", name: "Original name", brand: "Original brand", sku: "", width: 300, height: 400, cut_out: false, created_at: "" };
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } }); clients.push(client);
  client.setQueryData(marketingKeys.packages("p"), [ASSET]);
  vi.mocked(api.listPackages).mockResolvedValue([ASSET]);
  vi.mocked(api.updatePackage).mockImplementation(() => new Promise(() => {}));
  render(<QueryClientProvider client={client}><ProductLibrary projectId="p" setupId="s" products={[]} /></QueryClientProvider>);
  return client;
}
async function refresh(client: QueryClient, patch: Partial<api.PackageAsset>) {
  const asset = { ...ASSET, ...patch };
  await act(async () => { client.setQueryData(marketingKeys.packages("p"), [asset]); });
  await waitFor(() => expect(screen.getByRole("img").getAttribute("alt")).toBe(asset.name));
  await waitFor(() => expect(screen.getByText(`300×400px · ${asset.brand}`)).toBeTruthy());
}

it.each([
  { label: "Name", field: "name", patch: { name: "Read name", brand: "Read brand" } },
  { label: "Brand", field: "brand", patch: { name: "Read name", brand: "Read brand" } },
  { label: "Name", field: "name", patch: { brand: "Read brand" } },
  { label: "Brand", field: "brand", patch: { name: "Read name" } },
])("preserves an unfinished $label when saved product data refreshes ($patch)", async ({ label, field, patch }) => {
  const client = mount(); const input = screen.getByLabelText(label);
  fireEvent.change(input, { target: { value: "My unfinished edit" } });
  await refresh(client, patch);
  expect((input as HTMLInputElement).value).toBe("My unfinished edit");
  fireEvent.blur(input);
  await waitFor(() => expect(api.updatePackage).toHaveBeenCalledWith("p", "pkg_test", { [field]: "My unfinished edit" }));
});

it("keeps both unfinished fields while adopting the saved product link", async () => {
  const client = mount();
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "My name" } });
  fireEvent.change(screen.getByLabelText("Brand"), { target: { value: "My brand" } });
  await refresh(client, { name: "Read name", brand: "Read brand", sku: "new-sku" });
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("My name");
  expect((screen.getByLabelText("Brand") as HTMLInputElement).value).toBe("My brand");
  expect((screen.getByLabelText("Shown on the shelf as") as HTMLSelectElement).value).toBe("new-sku");
});

it("shows new model values in fields that have not been edited", async () => {
  const client = mount(); await refresh(client, { name: "Read name", brand: "Read brand" });
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Read name");
  expect((screen.getByLabelText("Brand") as HTMLInputElement).value).toBe("Read brand");
});

it("accepts a later saved update after the draft has been acknowledged", async () => {
  const client = mount(); fireEvent.change(screen.getByLabelText("Name"), { target: { value: "My saved name" } });
  await refresh(client, { name: "My saved name" });
  await refresh(client, { name: "Later model name" });
  expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Later model name");
});

it("keeps a newer draft when an earlier save is acknowledged", async () => {
  const client = mount(); const input = screen.getByLabelText("Name");
  fireEvent.change(input, { target: { value: "First saved name" } }); fireEvent.blur(input);
  await waitFor(() => expect(api.updatePackage).toHaveBeenCalledTimes(1));
  fireEvent.change(input, { target: { value: "Newer unsaved name" } });
  await refresh(client, { name: "First saved name" });
  expect((input as HTMLInputElement).value).toBe("Newer unsaved name");
});

it("does not carry drafts into another project's image with the same local ID", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } }); clients.push(client);
  client.setQueryData(marketingKeys.packages("p"), [ASSET]);
  client.setQueryData(marketingKeys.packages("other"), [{ ...ASSET, name: "Other project name", brand: "Other project brand" }]);
  const view = render(<QueryClientProvider client={client}><ProductLibrary projectId="p" products={[]} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Unfinished old project name" } });
  view.rerender(<QueryClientProvider client={client}><ProductLibrary projectId="other" products={[]} /></QueryClientProvider>);
  await waitFor(() => expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("Other project name"));
});

it("keeps a failed save visible and allows the same draft to be retried", async () => {
  mount();
  vi.mocked(api.updatePackage).mockRejectedValueOnce(new Error("Image changed elsewhere"));
  const input = screen.getByLabelText("Name");
  fireEvent.change(input, { target: { value: "My retryable name" } }); fireEvent.blur(input);
  expect((await screen.findByRole("alert")).textContent).toContain("Image changed elsewhere");
  expect((input as HTMLInputElement).value).toBe("My retryable name");
  vi.mocked(api.listPackages).mockResolvedValue([{ ...ASSET, name: "My retryable name" }]);
  vi.mocked(api.updatePackage).mockResolvedValue({ ...ASSET, name: "My retryable name" });
  fireEvent.focus(input); fireEvent.blur(input);
  await waitFor(() => expect(api.updatePackage).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

it("puts the saved name back when the name is emptied, since a pack needs one", async () => {
  mount(); const input = screen.getByLabelText("Name") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "   " } });
  fireEvent.blur(input);
  expect(input.value).toBe("Original name");
  expect(api.updatePackage).not.toHaveBeenCalled();
});
