import { expect, it } from "vitest";
import { productNamedIn } from "../productMatch";

const products = [{ sku: "cb", name: "Cold Brew 300ml" }, { sku: "cola", name: "Cola 500 ml" }, { sku: "zero", name: "Cola Zero 500 ml" }];

it("finds the product a request names, preferring the fullest name", () => {
  expect(productNamedIn("A friendlier pitch for Cola Zero 500 ml", products)).toBe("zero");
  expect(productNamedIn("Lead with taste for the cold brew", products)).toBe("cb");
  expect(productNamedIn("Write a warmer staff script", products)).toBeNull();
});
