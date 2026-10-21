import { expect, it } from "vitest";
import { fileProblem, MAX_FILE_BYTES } from "../uploadFiles";
const metadata = (size: number, type = "image/png", name = "photo.png") =>
  ({ size, type, name }) as File;
it("checks empty, exact maximum, over-limit and format metadata without inventing image validity", () => {
  expect(fileProblem(metadata(0))).toContain("empty");
  expect(fileProblem(metadata(1))).toBeNull();
  expect(fileProblem(metadata(MAX_FILE_BYTES))).toBeNull();
  expect(fileProblem(metadata(MAX_FILE_BYTES + 1))).toContain("25 MB");
  expect(fileProblem(metadata(1, "", "사진.JPEG"))).toBeNull();
  expect(fileProblem(metadata(1, "text/plain"))).toContain("JPEG");
  expect(fileProblem(metadata(1, "", "file.exe"))).toContain("JPEG");
});
