import { useRef, useMemo, useCallback, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import type { CustomerResult, TimelineEvent } from "@/shared/types/domain";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import {
  buildEventQueue,
  buildDayCheckpoints,
  MetricsAccumulator,
  type ScheduledEvent,
  type MetricsSnapshot,
} from "../utils/eventQueue";
import { parseTimeToSeconds } from "../utils/playback";
import { colorForCustomer } from "@/shared/utils/hashColor";
import { facingForEvent, positionBetweenEvents } from "@/features/store-viewer/realistic/shopperPose";

export interface PersonaFrame {
  id: string;
  gender: string;
  x: number;
  y: number;
  facing: number;
  isMoving: boolean;
  color: string;
  label: string;
  trail: { x: number; y: number }[];
  currentEvent: TimelineEvent | null;
}

interface CustomerLoopState {
  prevIdx: number;
  // Trail accumulated from timeline events (excludes the interpolated tail).
  // Push on each newly crossed event.
  trail: { x: number; y: number }[];
  // Facing accumulated from event-to-event direction changes; used when stationary.
  trailFacing: number;
}

interface LoopOptions {
  customers: CustomerResult[] | null;
  personaNames: Map<string, string>;
  personaGenders: Map<string, string>;
  minTime: number;
  maxTime: number;
  availableDays: number[];
}

export function useSimulationLoop({ customers, personaNames, personaGenders, minTime, maxTime, availableDays }: LoopOptions) {
  const playbackTimeRef = useRef(minTime);
  const lastMinuteRef = useRef(-1);
  const eventIndexRef = useRef(0);
  const accumulatorRef = useRef(new MetricsAccumulator());
  const personaFramesRef = useRef<PersonaFrame[]>([]);
  const activeDayRef = useRef(availableDays[0] ?? 1);

  // Per-customer playback state carried across frames so forward play does not
  // rescan the full timeline each frame. Cleared on seek / loadDay.
  const customerStatesRef = useRef<Map<string, CustomerLoopState>>(new Map());

  const dayCheckpoints = useMemo<Map<number, MetricsSnapshot>>(
    () => (customers?.length ? buildDayCheckpoints(customers, availableDays) : new Map()),
    [customers, availableDays],
  );

  const customersByDay = useMemo(() => {
    const map = new Map<number, CustomerResult[]>();
    if (!customers) return map;
    for (const c of customers) {
      const day = c.day ?? 1;
      const list = map.get(day) ?? [];
      list.push(c);
      map.set(day, list);
    }
    return map;
  }, [customers]);

  const eventQueueForDay = useCallback(
    (day: number) => buildEventQueue(customersByDay.get(day) ?? []),
    [customersByDay],
  );

  const eventQueueRef = useRef<ScheduledEvent[]>([]);

  const loadDay = useCallback(
    (day: number, time: number) => {
      activeDayRef.current = day;
      playbackTimeRef.current = time;
      lastMinuteRef.current = -1;
      eventIndexRef.current = 0;
      // Day switch / seek invalidates customer state — rebuild from scratch next frame.
      customerStatesRef.current.clear();

      const checkpoint = dayCheckpoints.get(day);
      accumulatorRef.current.reset();
      if (checkpoint) accumulatorRef.current.loadSnapshot(checkpoint);

      eventQueueRef.current = eventQueueForDay(day);

      const acc = accumulatorRef.current;
      for (let i = 0; i < eventQueueRef.current.length; i++) {
        if (eventQueueRef.current[i]!.time > time) {
          eventIndexRef.current = i;
          break;
        }
        acc.processEvent(eventQueueRef.current[i]!);
        if (i === eventQueueRef.current.length - 1) {
          eventIndexRef.current = eventQueueRef.current.length;
        }
      }

      const snap = acc.snapshot();
      const minute = Math.floor(time / 60) * 60;
      useSimulationMetricsStore.getState().setMetrics({
        currentDay: day,
        currentMinute: minute,
        finished: false,
        ...snap,
      });
      lastMinuteRef.current = minute;
    },
    [dayCheckpoints, eventQueueForDay],
  );

  const firstDay = availableDays[0] ?? 1;
  useEffect(() => {
    loadDay(firstDay, minTime);
  }, [loadDay, minTime, firstDay]);

  useFrame((_, delta) => {
    if (!customers?.length) return;

    const ctrl = usePlaybackControlStore.getState();
    const { playing, speed, consumeSeek, currentDay } = ctrl;

    if (currentDay !== activeDayRef.current) {
      loadDay(currentDay, minTime);
      return;
    }

    const lastDay = availableDays[availableDays.length - 1] ?? 1;
    const dayIdx = availableDays.indexOf(currentDay);
    const isLastDay = dayIdx === availableDays.length - 1;

    const seekTarget = consumeSeek();
    if (seekTarget !== null) {
      if (seekTarget >= maxTime && isLastDay) {
        loadDay(lastDay, maxTime);
        usePlaybackControlStore.getState().setDay(lastDay);
        usePlaybackControlStore.getState().pause();
        useSimulationMetricsStore.getState().setMetrics({ finished: true });
      } else if (seekTarget >= maxTime && !isLastDay) {
        usePlaybackControlStore.getState().setDay(lastDay);
        loadDay(lastDay, maxTime);
        const acc = accumulatorRef.current;
        const eq = eventQueueRef.current;
        while (eventIndexRef.current < eq.length) {
          acc.processEvent(eq[eventIndexRef.current]!);
          eventIndexRef.current++;
        }
        usePlaybackControlStore.getState().pause();
        useSimulationMetricsStore.getState().setMetrics({ finished: true, ...acc.snapshot() });
      } else {
        loadDay(currentDay, seekTarget);
      }
      return;
    }

    if (playing) {
      let next = playbackTimeRef.current + delta * speed;
      if (next >= maxTime) {
        if (!isLastDay) {
          const nextDay = availableDays[dayIdx + 1]!;
          usePlaybackControlStore.getState().setDay(nextDay);
          loadDay(nextDay, minTime);
          usePlaybackControlStore.getState().play();
          return;
        }
        next = maxTime;
        usePlaybackControlStore.getState().pause();
        useSimulationMetricsStore.getState().setMetrics({ finished: true });
      }
      playbackTimeRef.current = next;
    }

    const t = playbackTimeRef.current;
    const eq = eventQueueRef.current;

    const acc = accumulatorRef.current;
    let metricsChanged = false;
    while (eventIndexRef.current < eq.length && eq[eventIndexRef.current]!.time <= t) {
      acc.processEvent(eq[eventIndexRef.current]!);
      eventIndexRef.current++;
      metricsChanged = true;
    }

    const minute = Math.floor(t / 60) * 60;
    if (metricsChanged) {
      lastMinuteRef.current = minute;
      const snap = acc.snapshot();
      useSimulationMetricsStore.getState().setMetrics({
        currentDay: currentDay,
        currentMinute: minute,
        ...snap,
      });
    } else if (minute !== lastMinuteRef.current) {
      lastMinuteRef.current = minute;
      useSimulationMetricsStore.getState().setCurrentMinute(minute);
    }

    const dayCustomers = customersByDay.get(currentDay) ?? [];
    const frames: PersonaFrame[] = [];
    const states = customerStatesRef.current;
    for (const c of dayCustomers) {
      const arrivalSec = parseTimeToSeconds(c.arrival_time);
      const rel = t - arrivalSec;
      if (rel < 0) continue;

      let state = states.get(c.persona_id);
      if (!state) {
        state = { prevIdx: -1, trail: [], trailFacing: 0 };
        states.set(c.persona_id, state);
      }

      // Advance prevIdx — for each newly crossed event, incrementally update trail/facing.
      while (
        state.prevIdx + 1 < c.timeline.length &&
        c.timeline[state.prevIdx + 1]!.elapsed_sec <= rel
      ) {
        state.prevIdx++;
        const ev = c.timeline[state.prevIdx]!;
        const lastTrail = state.trail[state.trail.length - 1];
        if (!lastTrail || lastTrail.x !== ev.x || lastTrail.y !== ev.y) {
          state.trail.push({ x: ev.x, y: ev.y });
        }
        if (state.prevIdx > 0) {
          const pev = c.timeline[state.prevIdx - 1]!;
          const ddx = ev.x - pev.x;
          const ddy = ev.y - pev.y;
          if (ddx !== 0 || ddy !== 0) state.trailFacing = Math.atan2(ddx, ddy);
        }
      }

      const prevIdx = state.prevIdx;
      if (prevIdx < 0) continue;
      const prev = c.timeline[prevIdx]!;
      if (prev.action === "exit") continue;

      const next = prevIdx + 1 < c.timeline.length ? c.timeline[prevIdx + 1]! : null;
      const { x, y, moving: isMoving } = positionBetweenEvents(prev, next, rel);
      const heading = isMoving
        ? Math.atan2(next!.x - prev.x, next!.y - prev.y)
        : state.trailFacing;
      const facing = facingForEvent(heading, isMoving, prev);

      // state.trail is the event-based accumulator. Append the interpolated current
      // position as the tail to form the output trail. slice cost is O(unique tiles
      // visited), not the full timeline length.
      const outTrail = state.trail.slice();
      const lastOut = outTrail[outTrail.length - 1];
      if (!lastOut || lastOut.x !== x || lastOut.y !== y) {
        outTrail.push({ x, y });
      }

      const label = personaNames.get(c.persona_id) ?? c.persona_id;
      const gender = personaGenders.get(c.persona_id) ?? "";
      const currentEvent = prev;

      frames.push({
        id: c.persona_id,
        gender,
        x, y, facing, isMoving,
        color: colorForCustomer(c.persona_id),
        label,
        trail: outTrail,
        currentEvent,
      });
    }

    personaFramesRef.current = frames;
  });

  return { personaFramesRef, playbackTimeRef };
}
