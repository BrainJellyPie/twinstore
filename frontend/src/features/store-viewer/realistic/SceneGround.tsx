interface Props {
  color: string;
  y: number;
  size?: number;
}

const noRaycast = () => undefined;

// Ground around the store (theme --scene-floor); fades into the scene fog.
// Unlit on purpose: it fills most of the frame, so it must stay cheap.
export function SceneGround({ color, y, size = 220 }: Props) {
  return (
    <mesh name="scene-ground" position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]} raycast={noRaycast}>
      <planeGeometry args={[size, size]} />
      <meshBasicMaterial color={color} toneMapped={false} />
    </mesh>
  );
}
