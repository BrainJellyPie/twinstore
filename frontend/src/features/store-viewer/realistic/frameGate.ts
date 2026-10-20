// GPU back-pressure for the render loop. R3F issues a frame on every rAF; on a
// slow GPU (software GL, weak iGPU with the realistic scene) frames queue up in
// the GPU process and every synchronous GL call — context creation, disposal,
// shader status — then waits for the whole backlog, freezing the page for tens
// of seconds. The gate issues a new frame only once the previous one has
// finished on the GPU (EXT_disjoint_timer_query_webgl2 availability, which is
// non-blocking). Without the extension every frame is drawn, as before.

type Gl2 = WebGL2RenderingContext;

interface TimerExt {
  TIME_ELAPSED_EXT: number;
  GPU_DISJOINT_EXT: number;
}

export interface FrameGate {
  // Replaces the plain scene render (e.g. a post-processing composer).
  renderer: ((delta: number) => void) | null;
  // Last measured GPU frame time (ms), or null when unknown.
  gpuMs: number | null;
  // True while the previous frame is still executing on the GPU.
  busy: () => boolean;
  begin: () => void;
  end: () => void;
  attach: (gl: Gl2) => void;
  detach: () => void;
}

function createFrameGate(): FrameGate {
  let ctx: Gl2 | null = null;
  let ext: TimerExt | null = null;
  let pending: WebGLQuery | null = null;
  let active: WebGLQuery | null = null;

  const gate: FrameGate = {
    renderer: null,
    gpuMs: null,
    busy: () => {
      if (!ctx || !pending) return false;
      if (ctx.isContextLost()) {
        pending = null;
        return false;
      }
      if (!ctx.getQueryParameter(pending, ctx.QUERY_RESULT_AVAILABLE)) return true;
      if (ext && !ctx.getParameter(ext.GPU_DISJOINT_EXT)) {
        gate.gpuMs = Number(ctx.getQueryParameter(pending, ctx.QUERY_RESULT)) / 1e6;
      }
      ctx.deleteQuery(pending);
      pending = null;
      return false;
    },
    begin: () => {
      if (!ctx || !ext || active) return;
      const q = ctx.createQuery();
      if (!q) return;
      ctx.beginQuery(ext.TIME_ELAPSED_EXT, q);
      active = q;
    },
    end: () => {
      if (!ctx || !ext || !active) return;
      ctx.endQuery(ext.TIME_ELAPSED_EXT);
      pending = active;
      active = null;
    },
    attach: (gl) => {
      ctx = gl;
      ext = (gl.getExtension("EXT_disjoint_timer_query_webgl2") as TimerExt | null) ?? null;
      pending = null;
      active = null;
    },
    detach: () => {
      ctx = null;
      ext = null;
      pending = null;
      active = null;
      gate.gpuMs = null;
    },
  };
  return gate;
}

export const frameGate = createFrameGate();
