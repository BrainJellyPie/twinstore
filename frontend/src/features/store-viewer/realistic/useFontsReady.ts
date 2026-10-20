import { useEffect, useState } from "react";
import { FONT_STACK } from "./canvasArt";

// Canvas text is drawn before the web font may have loaded; flips to true once
// it has, so atlases can redraw with the proper typeface.
export function useFontsReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let alive = true;
    const fonts = typeof document !== "undefined" ? document.fonts : undefined;
    if (!fonts?.load) return;
    Promise.all([fonts.load(`800 32px ${FONT_STACK}`), fonts.load(`600 32px ${FONT_STACK}`)])
      .catch(() => undefined)
      .then(() => {
        if (alive) setReady(true);
      });
    return () => {
      alive = false;
    };
  }, []);
  return ready;
}
