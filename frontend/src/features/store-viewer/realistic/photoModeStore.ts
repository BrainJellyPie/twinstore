// Photo mode state shared by the path-tracing component (in the canvas) and the HUD.

import { create } from "zustand";

export type PhotoStatus = "off" | "building" | "tracing" | "done" | "error";

interface PhotoState {
  status: PhotoStatus;
  samples: number;
  target: number;
  progress: number;
  triangles: number;
  error: string;
  saveRequest: number;
  // Edge-aware smoothing of the accumulated image (strongest while samples are few).
  denoise: boolean;
  // Depth of field for perspective (shopper) views: focus on what sits at the centre of the frame.
  perspective: boolean;
  dof: boolean;
  fStop: number;
  start: () => void;
  stop: () => void;
  setTarget: (n: number) => void;
  save: () => void;
  setDenoise: (on: boolean) => void;
  setDof: (dof: boolean, fStop?: number) => void;
}

export const usePhotoMode = create<PhotoState>((set) => ({
  status: "off",
  samples: 0,
  target: 256,
  progress: 0,
  triangles: 0,
  error: "",
  saveRequest: 0,
  denoise: true,
  perspective: false,
  dof: false,
  fStop: 2.8,
  start: () => set({ status: "building", samples: 0, progress: 0, error: "" }),
  stop: () => set({ status: "off", samples: 0, progress: 0 }),
  setTarget: (target) => set((s) => ({ target, status: s.status === "done" && s.samples < target ? "tracing" : s.status })),
  save: () => set((s) => ({ saveRequest: s.saveRequest + 1 })),
  setDenoise: (denoise) => set({ denoise }),
  setDof: (dof, fStop) => set((s) => ({ dof, fStop: fStop ?? s.fStop, status: s.status === "done" ? "tracing" : s.status })),
}));
