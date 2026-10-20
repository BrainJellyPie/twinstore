// Light ("day shift") / dark ("night shift") theme. The choice is remembered per browser; the
// first visit follows the operating system. index.html applies it before React renders, so
// there is no flash of the wrong theme.

import { create } from "zustand";

export type Theme = "light" | "dark";

const KEY = "parastore-theme";

function systemTheme(): Theme {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function storedTheme(): Theme | null {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function apply(theme: Theme, persist: boolean): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  if (!persist) return;
  try {
    window.localStorage.setItem(KEY, theme);
  } catch {
    // Private mode / blocked storage: the theme still applies for this session.
  }
}

const initial = storedTheme() ?? systemTheme();
apply(initial, false);

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

export const useTheme = create<ThemeState>((set, get) => ({
  theme: initial,
  setTheme: (theme) => {
    apply(theme, true);
    set({ theme });
  },
  toggle: () => get().setTheme(get().theme === "dark" ? "light" : "dark"),
}));
