import { Box3, Matrix4, Vector3 } from "three";

// Include the exterior walkway, compass labels and signs above the walls.
export function storeCameraFit(width: number, depth: number, viewportWidth: number, viewportHeight: number, maxZoom: number) {
  const target = new Vector3(0, 1.6, 0);
  const position = new Vector3(17, 14.1, 22);
  const rotation = new Matrix4().lookAt(position, target, new Vector3(0, 1, 0)).invert();
  const bounds = new Box3();
  for (const x of [-width / 2 - 2, width / 2 + 2]) {
    for (const y of [-0.2, 3.4]) {
      for (const z of [-depth / 2 - 2, depth / 2 + 2]) {
        bounds.expandByPoint(new Vector3(x, y, z).sub(target).applyMatrix4(rotation));
      }
    }
  }
  const size = bounds.getSize(new Vector3());
  // Screen-space room for labels and the controls at the bottom of the canvas.
  const zoom = Math.min(
    Math.max(1, viewportWidth - 80) / size.x,
    Math.max(1, viewportHeight - 176) / size.y,
    maxZoom,
  );
  return { position, target, zoom };
}
