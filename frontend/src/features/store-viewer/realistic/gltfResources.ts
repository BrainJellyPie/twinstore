import * as THREE from "three";

/** Release a privately loaded glTF, including shared maps and decoded bitmaps. */
export function disposeOwnedGltf(scene: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  const images = new Set<ImageBitmap>();
  scene.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material);
  });
  for (const material of materials) for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
  for (const texture of textures) {
    const image: unknown = texture.image;
    if (typeof ImageBitmap !== "undefined" && image instanceof ImageBitmap) images.add(image);
    texture.dispose();
  }
  images.forEach((image) => image.close());
  materials.forEach((material) => material.dispose());
  geometries.forEach((geometry) => geometry.dispose());
}
