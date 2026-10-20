import { useMemo } from "react";
import { useTheme } from "@/app/theme";

export interface SceneColors {
  dark: boolean;
  // Background / clear / fog colour (CSS --scene).
  scene: string;
  // Ground around the store (CSS --scene-floor).
  sceneFloor: string;
  // Muted text colour for in-scene labels (CSS --muted-foreground).
  muted: string;
}

const FALLBACK: Record<"light" | "dark", Omit<SceneColors, "dark">> = {
  light: { scene: "#e8ebf4", sceneFloor: "#f6f7fb", muted: "#4f5a7a" },
  dark: { scene: "#0a1028", sceneFloor: "#131a3d", muted: "#a3add0" },
};

function cssVar(style: CSSStyleDeclaration | null, name: string, fallback: string): string {
  const v = style?.getPropertyValue(name).trim();
  return v ? v : fallback;
}

// Scene colours from the theme's CSS variables, re-read whenever the theme
// toggles (the `dark` class is applied before the store updates).
export function useSceneColors(): SceneColors {
  const theme = useTheme((s) => s.theme);
  return useMemo(() => {
    const fb = FALLBACK[theme];
    const style = typeof document !== "undefined" ? getComputedStyle(document.documentElement) : null;
    return {
      dark: theme === "dark",
      scene: cssVar(style, "--scene", fb.scene),
      sceneFloor: cssVar(style, "--scene-floor", fb.sceneFloor),
      muted: cssVar(style, "--muted-foreground", fb.muted),
    };
  }, [theme]);
}
