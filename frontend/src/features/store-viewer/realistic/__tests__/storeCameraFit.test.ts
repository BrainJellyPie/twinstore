import { expect, it } from "vitest";
import { OrthographicCamera, Vector3 } from "three";
import { storeCameraFit } from "../storeCameraFit";

it.each([
  [8, 6, 1200, 700], [24, 18, 1000, 650], [40, 40, 390, 600],
  [8, 40, 320, 500], [40, 6, 1200, 350], [40, 40, 1920, 1080],
])("frames %i×%i cells on a %i×%i canvas with room for the HUD", (width, depth, vw, vh) => {
  const fit = storeCameraFit(width, depth, vw, vh, 140);
  const camera = new OrthographicCamera(-vw / 2, vw / 2, vh / 2, -vh / 2, -100, 200);
  camera.position.copy(fit.position);
  camera.lookAt(fit.target);
  camera.zoom = fit.zoom;
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  for (const x of [-width / 2 - 2, width / 2 + 2]) {
    for (const y of [-0.2, 3.4]) {
      for (const z of [-depth / 2 - 2, depth / 2 + 2]) {
        const projected = new Vector3(x, y, z).project(camera);
        expect(Math.abs(projected.x)).toBeLessThanOrEqual(1 - 80 / vw + 1e-10);
        expect(Math.abs(projected.y)).toBeLessThanOrEqual(1 - 176 / vh + 1e-10);
        expect(Math.abs(projected.z)).toBeLessThan(1);
      }
    }
  }
});

it("allows large stores below the former minimum zoom and caps small stores", () => {
  expect(storeCameraFit(40, 40, 390, 600, 140).zoom).toBeLessThan(20);
  expect(storeCameraFit(8, 6, 8000, 8000, 140).zoom).toBe(140);
});
