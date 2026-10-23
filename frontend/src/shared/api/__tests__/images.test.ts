import { afterEach, expect, it, vi } from "vitest";

import { uploadSkuImages } from "../images";

afterEach(() => vi.unstubAllGlobals());

it.each(["tea", "A/B", "../tea", ".", "..", "%2F", "%25", "coffee 100%", "tea?size=1#box", "차/대형", ""])(
  "preserves SKU %j when uploading a photo",
  async (sku) => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ sku, url: "/photo" })));
    vi.stubGlobal("fetch", fetch);

    const result = await uploadSkuImages("Project-A", { [sku]: { bytes: new Uint8Array([1, 2, 3]), extension: "png" } });

    expect(result).toEqual([{ sku, url: "/photo" }]);
    const [address, options] = fetch.mock.calls[0]!;
    const url = new URL(address as string, "http://localhost");
    expect(url.pathname).toBe("/api/projects/Project-A/sku-images");
    expect(url.searchParams.get("sku")).toBe(sku);
    expect(options).toEqual({ method: "POST", body: expect.any(FormData) });
  },
);

it.each([[0, false], [1, false], [0, true], [1, true]] as const)(
  "waits for remaining image requests after failure at index %s (other failure: %s)", async (failedIndex, otherFailure) => {
    let resolve!: (response: Response) => void;
    const delayed = new Promise<Response>((done) => { resolve = done; });
    const fetch = vi.fn();
    for (let i = 0; i < 2; i += 1) {
      fetch.mockReturnValueOnce(i === failedIndex ? Promise.resolve(new Response("bad photo", { status: 422 })) : delayed);
    }
    vi.stubGlobal("fetch", fetch);
    let settled = false;
    const request = uploadSkuImages("p", {
      first: { bytes: new Uint8Array([1]), extension: "png" },
      second: { bytes: new Uint8Array([2]), extension: "png" },
    }).then(() => { settled = true; return null; }, (error: unknown) => { settled = true; return error; });
    await new Promise((done) => setTimeout(done, 0));
    const returnedBeforeRemainingUpload = settled;
    resolve(otherFailure ? new Response("also failed", { status: 500 }) : new Response(JSON.stringify({ sku: "late", url: "/photo" })));
    const error = await request;
    expect(returnedBeforeRemainingUpload).toBe(false);
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toContain("SKU image upload failed");
  },
);
