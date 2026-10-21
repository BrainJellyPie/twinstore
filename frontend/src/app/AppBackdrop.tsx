// Ambient light behind every page: three drifting aurora blobs, a fading dot grid and film
// grain. Calm mode freezes the blobs while the 3D store is on screen.

export function AppBackdrop({ calm = false }: { calm?: boolean }) {
  return (
    <div className="app-backdrop" data-calm={calm || undefined} aria-hidden>
      <div className="blob animate-aurora" style={{ width: "52vw", height: "52vw", left: "-14vw", top: "-26vw", background: "var(--backdrop-a)" }} />
      <div className="blob animate-aurora-slow" style={{ width: "42vw", height: "42vw", right: "-12vw", top: "8vh", background: "var(--backdrop-b)" }} />
      <div className="blob animate-aurora" style={{ width: "36vw", height: "36vw", left: "28vw", bottom: "-22vw", background: "var(--backdrop-c)" }} />
      <div className="dot-grid absolute inset-0 [mask-image:radial-gradient(ellipse_80%_60%_at_50%_0%,black_10%,transparent_75%)]" />
      <div className="grain" />
    </div>
  );
}
