import { describe, expect, it } from "vitest";
import type { CustomerResult, Face, TimelineEvent } from "@/shared/types/domain";
import { shopperPoseAt } from "../shopperPose";

const ev = (elapsed_sec: number, x: number, action: string, extra: Partial<TimelineEvent> = {}): TimelineEvent => ({
  elapsed_sec, x, y: 2, action, duration: 0, target_rack: "shelf", face: "S", description: "",
  product_sku: "", product_name: "", price: 0, ...extra,
});
const customer = (stop: Partial<TimelineEvent> = {}, next = ev(15, 2, "move")): CustomerResult => ({
  persona_id: "dwell", day: 1, arrival_time: "08:00:00", leave_time: "", total_spent: 0,
  timeline: [ev(0, 0, "enter"), ev(2, 1, "move"), ev(2, 1, "browse", { duration: 10, ...stop }), next, ev(20, 3, "exit")],
});
const pose = (c: CustomerResult, seconds: number) => shopperPoseAt(c, 28800 + seconds)!;

describe("stationary shopper actions", () => {
  it.each(["browse", "buy", "pay"])("holds %s for its authored duration, then walks to the next event", (action) => {
    const c = customer({ action });
    for (const seconds of [2, 2.001, 7, 11.999]) {
      expect(pose(c, seconds)).toMatchObject({ x: 1.5, z: 2.5, moving: false });
    }
    expect(pose(c, 12)).toMatchObject({ x: 1.5, moving: true });
    expect(pose(c, 13.5)).toMatchObject({ x: 2, moving: true });
    expect(pose(c, 15).x).toBe(2.5);
  });

  it.each((["N", "S", "E", "W"] as Face[]).flatMap(face => ["browse", "buy"].map(action => ({ face, action }))))(
    "looks toward face $face during $action even without a description", ({ face, action }) => {
      const p = pose(customer({ face, action }), 7);
      expect(p.moving).toBe(false);
      expect(p.lookYaw).toBe(({ N: 0, S: Math.PI, E: -Math.PI / 2, W: Math.PI / 2 })[face]);
      expect(p.event?.action).toBe(action);
    },
  );

  it.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])(
    "keeps a finite legacy interpolation for unusable duration %s", duration => {
      const p = pose(customer({ duration }), 8.5);
      expect(p).toMatchObject({ x: 2, moving: true });
    },
  );

  it.each([13, 14, 1000000])("holds overlapping duration %s until the next timestamp without overshoot", duration => {
    const c = customer({ duration });
    expect(pose(c, 14.999)).toMatchObject({ x: 1.5, moving: false });
    expect(pose(c, 15).x).toBe(2.5);
  });

  it("uses fractional dwell and movement intervals", () => {
    const c = customer({ duration: 10.25 }, ev(14.75, 2, "move"));
    expect(pose(c, 12.249).moving).toBe(false);
    expect(pose(c, 13.5).x).toBe(2);
  });

  it("does not apply wander pauses twice: their timestamps mark the end of the glance", () => {
    const c = customer({ action: "wander", duration: 3 });
    expect(pose(c, 8.5)).toMatchObject({ x: 2, moving: true });
  });

  it("keeps coincident positions stationary and final shoppers visible until exit", () => {
    const c = customer({}, ev(15, 1, "buy"));
    expect(pose(c, 13)).toMatchObject({ x: 1.5, moving: false });
    expect(shopperPoseAt(c, 28799)).toBeNull();
    expect(shopperPoseAt(c, 28820)).toBeNull();
    const noExit = { ...c, timeline: c.timeline.slice(0, -1) };
    expect(pose(noExit, 100)).toMatchObject({ x: 1.5, moving: false });
  });

  it("picks the last event when several share an arrival timestamp", () => {
    const c = customer();
    c.timeline.splice(3, 0, ev(2, 1, "buy", { duration: 5 }));
    expect(pose(c, 6.999)).toMatchObject({ x: 1.5, moving: false });
    expect(pose(c, 11).x).toBe(2);
  });
});
