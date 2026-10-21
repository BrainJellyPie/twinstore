// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { RealisticLighting } from "../RealisticLighting";
import { personaRegistry } from "../personaRegistry";

interface RenderState {
  gl: {
    shadowMap: { autoUpdate: boolean; needsUpdate: boolean };
    getPixelRatio: () => number;
    toneMappingExposure: number;
    toneMapping: THREE.ToneMapping;
  };
  scene: THREE.Scene;
  setDpr: (value: number) => void;
}

const context = vi.hoisted(() => ({
  get: vi.fn<() => RenderState>(),
  frame: null as ((state: RenderState) => void) | null,
}));
vi.mock("@react-three/fiber", () => ({
  useThree: (selector: (state: { get: typeof context.get }) => unknown) => selector({ get: context.get }),
  useFrame: (callback: (state: RenderState) => void) => { context.frame = callback; },
}));
vi.mock("../envCache", () => ({
  acquireRoomEnvironment: () => null,
  acquirePhotographicEnvironment: () => Promise.resolve(null),
  retainRoomEnvironment: () => undefined,
  releaseRoomEnvironment: () => undefined,
}));

afterEach(() => { personaRegistry.count = 0; });

describe("cached shopper shadows", () => {
  const cases = (["medium", "high"] as const).flatMap((quality) =>
    [0, 1, 2].flatMap((phase) => [0, 1, 3].map((remaining) => ({ quality, phase, remaining }))),
  );
  it.each(cases)("refreshes $quality shadows at phase $phase when 2 shoppers become $remaining", ({ quality, phase, remaining }) => {
    const state: RenderState = {
      gl: { shadowMap: { autoUpdate: true, needsUpdate: false }, getPixelRatio: () => 1,
        toneMappingExposure: 1, toneMapping: THREE.NoToneMapping },
      scene: new THREE.Scene(), setDpr: vi.fn(),
    };
    context.get.mockReturnValue(state);
    personaRegistry.count = 0;
    const hook = renderHook(() => RealisticLighting({ width: 4, depth: 5, quality, dark: false }));
    const tick = () => {
      // The renderer consumes the dirty flag after each frame.
      state.gl.shadowMap.needsUpdate = false;
      context.frame!(state);
      return state.gl.shadowMap.needsUpdate;
    };
    for (let i = 0; i < 40; i++) tick();
    expect(tick()).toBe(false);
    personaRegistry.count = 2;
    for (let i = 0; i < 12 + phase; i++) tick();
    personaRegistry.count = remaining;
    const refreshed = tick();
    const idleFrames = remaining === 0 ? Array.from({ length: 12 }, tick) : [];
    hook.unmount();
    expect(refreshed).toBe(true);
    expect(idleFrames.every((refresh) => !refresh)).toBe(true);
    expect(state.gl.shadowMap.autoUpdate).toBe(true);
  });
});
