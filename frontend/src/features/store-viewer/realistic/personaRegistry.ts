// Frame-to-frame bridge between PersonaRig (which sees the rendered persona
// groups) and consumers that need their live positions (automatic doors, the
// shopper-view camera). Plain mutable module state — never React state.

export interface PersonaRegistry {
  // Store-local x/z of every visible persona this frame.
  xs: number[];
  zs: number[];
  count: number;
  // Shopper view hides the persona nearest to this point (the camera's body).
  hideNear: { x: number; z: number } | null;
}

export const personaRegistry: PersonaRegistry = { xs: [], zs: [], count: 0, hideNear: null };
