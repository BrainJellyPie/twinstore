// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import * as api from "@/shared/api/client";
import type { PackageAsset } from "@/shared/api/client";
import { ProductDrop, ProductLibrary } from "../ProductLibrary";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  uploadPackage: vi.fn(), readPackage: vi.fn(), listPackages: vi.fn(), updatePackage: vi.fn(), getModelSetup: vi.fn(), deletePackage: vi.fn(),
}));
vi.mock("@tanstack/react-router", async (original) => ({
  ...await original<typeof import("@tanstack/react-router")>(), Link: ({ children }: { children: React.ReactNode }) => <a href="/settings">{children}</a>,
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [ASSET] }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const ASSET: PackageAsset = { asset_id: "pkg_1", name: "IMG 2041", width: 300, height: 400, brand: "", sku: "", cut_out: true, created_at: "" };
const READ = { asset: { ...ASSET, name: "Green Tea 500 ml", brand: "Leafy", sku: "A1" }, model: "m", linked: true,
  reading: { name: "Green Tea 500 ml", brand: "Leafy", size: "500 ml", category: "Tea", shelf_product: "Leafy Green Tea", confidence: 0.9 } };

const wrap = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

it("names uploaded packs from what they say, keeping the file name when a pack cannot be read", async () => {
  vi.mocked(api.uploadPackage).mockImplementation(async (_p, file) => ({ ...ASSET, asset_id: file.name, name: file.name }));
  vi.mocked(api.readPackage).mockImplementation(async (_p, id) => {
    if (id === "blurry.png") throw new Error("unreadable");
    return READ;
  });
  const uploaded = vi.fn();
  wrap(<ProductDrop projectId="p" setupId="s1" onUploaded={uploaded} />);
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const files = [new File(["a"], "IMG_2041.png", { type: "image/png" }), new File(["b"], "blurry.png", { type: "image/png" })];
  fireEvent.change(input, { target: { files } });
  await waitFor(() => expect(uploaded).toHaveBeenCalled());
  expect(api.readPackage).toHaveBeenCalledWith("p", "IMG_2041.png", { setup_id: "s1" });
  expect(uploaded.mock.calls[0]![0].map((a: PackageAsset) => a.name)).toEqual(["Green Tea 500 ml", "blurry.png"]);
  expect(await screen.findByText(/1 pack could not be read and kept the file name/)).toBeTruthy();
});

it("skips reading when the user turns it off", async () => {
  vi.mocked(api.uploadPackage).mockResolvedValue(ASSET);
  const uploaded = vi.fn();
  wrap(<ProductDrop projectId="p" onUploaded={uploaded} />);
  fireEvent.click(screen.getByLabelText("Name packs from what they say"));
  fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [new File(["a"], "x.png", { type: "image/png" })] } });
  await waitFor(() => expect(uploaded).toHaveBeenCalled());
  expect(api.readPackage).not.toHaveBeenCalled();
});

it("reads one pack from its card and says what it found", async () => {
  vi.mocked(api.readPackage).mockResolvedValue(READ);
  wrap(<ProductLibrary projectId="p" products={[]} setupId="s1" />);
  fireEvent.click(screen.getByRole("button", { name: "Read the pack" }));
  expect(await screen.findByText("500 ml · Tea · linked to the shelf product")).toBeTruthy();
  expect(api.readPackage).toHaveBeenCalledWith("p", "pkg_1", { setup_id: "s1" });
});

it("keeps uploading past a rejected file, names it with the server's reason and refreshes the library", async () => {
  vi.mocked(api.uploadPackage).mockImplementation(async (_p, file) => {
    if (file.name === "huge.png") throw new Error("image is larger than 20 MB");
    return { ...ASSET, asset_id: file.name, name: file.name };
  });
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const uploaded = vi.fn();
  render(<QueryClientProvider client={client}><ProductDrop projectId="p" onUploaded={uploaded} /></QueryClientProvider>);
  fireEvent.click(screen.getByLabelText("Name packs from what they say"));
  const files = ["a.png", "huge.png", "c.png"].map((name) => new File(["x"], name, { type: "image/png" }));
  fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files } });
  await waitFor(() => expect(uploaded).toHaveBeenCalledOnce());
  expect(api.uploadPackage).toHaveBeenCalledTimes(3);
  expect(uploaded.mock.calls[0]![0].map((a: PackageAsset) => a.asset_id)).toEqual(["a.png", "c.png"]);
  const alert = screen.getByRole("alert");
  expect(alert.textContent).toContain("1 image could not be uploaded:");
  expect(alert.textContent).toContain("huge.png: image is larger than 20 MB");
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects", "p", "lab-packages"] });
});

it("refreshes the library even when every file is rejected", async () => {
  vi.mocked(api.uploadPackage).mockRejectedValue(new Error("Unsupported image"));
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const uploaded = vi.fn();
  render(<QueryClientProvider client={client}><ProductDrop projectId="p" onUploaded={uploaded} /></QueryClientProvider>);
  const files = ["a.png", "b.png"].map((name) => new File(["x"], name, { type: "image/png" }));
  fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files } });
  expect((await screen.findByRole("alert")).textContent).toContain("2 images could not be uploaded:");
  await waitFor(() => expect(invalidate).toHaveBeenCalled());
  expect(uploaded).not.toHaveBeenCalled();
});

it("offers model setup when packs could not be read for want of a model", async () => {
  vi.mocked(api.getModelSetup).mockResolvedValue({ cloud_providers: [], local: { state: "stopped", downloaded: true, progress: null } } as unknown as api.ModelSetup);
  vi.mocked(api.uploadPackage).mockImplementation(async (_p, file) => ({ ...ASSET, asset_id: file.name, name: file.name }));
  vi.mocked(api.readPackage).mockRejectedValue(new Error("No model API key is set."));
  const { container } = wrap(<ProductDrop projectId="p" setupId="s1" />);
  fireEvent.change(container.querySelector("input[type=file]")!, { target: { files: [new File(["x"], "pack.png", { type: "image/png" })] } });
  expect(await screen.findByText(/1 pack could not be read/)).toBeTruthy();
  expect(await screen.findByTestId("needs-model")).toBeTruthy();
});

it("asks before deleting a pack, then moves focus to the drop zone", async () => {
  vi.mocked(api.deletePackage).mockResolvedValue(undefined as never);
  wrap(<ProductLibrary projectId="p" products={[]} />);
  fireEvent.click(screen.getByRole("button", { name: "Delete IMG 2041" }));
  expect(api.deletePackage).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Delete?" }));
  await waitFor(() => expect(api.deletePackage).toHaveBeenCalledWith("p", "pkg_1"));
  await waitFor(() => expect(document.activeElement?.textContent).toContain("Drop product images"));
});
