import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import type { CustomerResult } from "@/shared/types/domain";
import { useSimulationStore } from "@/stores/simulationStore";
import { useSimulationLoop, type PersonaFrame } from "../hooks/useSimulationLoop";
import { PersonaView } from "./PersonaView";
import type { Point } from "../utils/queueLine";

interface Props {
  customers: CustomerResult[] | null;
  personaNames: Map<string, string>;
  personaGenders: Map<string, string>;
  minTime: number;
  maxTime: number;
  availableDays: number[];
  counters?: Point[];
}

export function PlaybackScene({ customers, personaNames, personaGenders, minTime, maxTime, availableDays, counters }: Props) {
  const highlightId = useSimulationStore((s) => s.highlightId);
  const { personaFramesRef } = useSimulationLoop({ customers, personaNames, personaGenders, minTime, maxTime, availableDays, counters });

  const frameMapRef = useRef<Map<string, PersonaFrame>>(new Map());
  const prevIdsRef = useRef<string[]>([]);
  const [visibleIds, setVisibleIds] = useState<string[]>([]);

  useFrame(() => {
    const frames = personaFramesRef.current;
    const map = frameMapRef.current;
    map.clear();
    for (const frame of frames) {
      map.set(frame.id, frame);
    }

    const currentIds: string[] = new Array(frames.length);
    for (let i = 0; i < frames.length; i++) currentIds[i] = frames[i]!.id;

    const prevIds = prevIdsRef.current;
    let changed = currentIds.length !== prevIds.length;
    if (!changed) {
      for (let i = 0; i < currentIds.length; i++) {
        if (currentIds[i] !== prevIds[i]) {
          changed = true;
          break;
        }
      }
    }
    if (changed) {
      prevIdsRef.current = currentIds;
      setVisibleIds(currentIds);
    }
  });

  return (
    <>
      {visibleIds.map((id) => (
        <PersonaView
          key={id}
          id={id}
          frameMapRef={frameMapRef}
          highlightId={highlightId}
        />
      ))}
    </>
  );
}
