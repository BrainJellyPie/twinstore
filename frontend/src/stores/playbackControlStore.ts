import { create } from "zustand";

export type PlaybackSpeed = 1 | 60 | 600 | 3600;

interface PlaybackControlState {
  playing: boolean;
  speed: PlaybackSpeed;
  seekTarget: number | null;
  currentDay: number;
  availableDays: number[];

  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  seek: (target: number) => void;
  consumeSeek: () => number | null;
  setDay: (day: number) => void;
  nextDay: () => void;
  prevDay: () => void;
  setAvailableDays: (days: number[]) => void;
  reset: () => void;
}

export const usePlaybackControlStore = create<PlaybackControlState>((set, get) => ({
  playing: false,
  speed: 60,
  seekTarget: null,
  currentDay: 1,
  availableDays: [1],

  play: () => set({ playing: true }),
  pause: () => set({ playing: false }),
  togglePlay: () => set((s) => ({ playing: !s.playing })),
  setSpeed: (speed) => set({ speed }),
  seek: (target) => set({ seekTarget: target }),
  consumeSeek: () => {
    const target = get().seekTarget;
    if (target !== null) set({ seekTarget: null });
    return target;
  },
  setDay: (day) => set({ currentDay: day }),
  nextDay: () => {
    const { currentDay, availableDays } = get();
    const idx = availableDays.indexOf(currentDay);
    if (idx >= 0 && idx < availableDays.length - 1) {
      set({ currentDay: availableDays[idx + 1]! });
    }
  },
  prevDay: () => {
    const { currentDay, availableDays } = get();
    const idx = availableDays.indexOf(currentDay);
    if (idx > 0) {
      set({ currentDay: availableDays[idx - 1]! });
    }
  },
  setAvailableDays: (days) => set({ availableDays: days, currentDay: days[0] ?? 1 }),
  reset: () => set({ playing: false, speed: 60, seekTarget: null, currentDay: 1, availableDays: [1] }),
}));
