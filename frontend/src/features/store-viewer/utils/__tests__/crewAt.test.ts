import { expect, it } from "vitest";
import type { CrewTask } from "@/shared/api/client";
import { crewAt, crewIndex, crewOnDuty } from "../crewAt";

const task = (member: number, kind: CrewTask["kind"], start: number, end: number, day = 1): CrewTask =>
  ({ day, member, kind, rack_id: kind === "till" ? "C0" : "A", face: kind === "till" ? "" : "E", sku: "chips", name: kind === "till" ? "" : "Chips", start, end });

const index = crewIndex([task(1, "refill", 36070, 36130), task(1, "refill", 36010, 36070), task(0, "till", 36025, 36026),
  task(0, "till", 36500, 36530, 2)]);
const plan = { crew: 2, schedule: { "11": 3, "12": 0 } };

it("says what each crew member on duty is doing, by the clock second", () => {
  expect(crewAt(index, plan, 1, 36000)).toEqual([{ member: 0, kind: "idle" }, { member: 1, kind: "idle" }]);
  expect(crewAt(index, plan, 1, 36025)).toEqual([{ member: 0, kind: "till", rackId: "C0" },
    { member: 1, kind: "refill", rackId: "A", face: "E", name: "Chips" }]);
  expect(crewAt(index, plan, 1, 36026)[0]).toEqual({ member: 0, kind: "idle" });   // the end is not part of it
  expect(crewAt(index, plan, 1, 36070)[1]).toEqual({ member: 1, kind: "refill", rackId: "A", face: "E", name: "Chips" });
  expect(crewAt(index, plan, 1, 36130)[1]).toEqual({ member: 1, kind: "idle" });
  expect(crewAt(index, plan, 2, 36025)[0]).toEqual({ member: 0, kind: "idle" });   // another day
});

it("follows the crew hour by hour", () => {
  expect(crewOnDuty(plan, 10 * 3600)).toBe(2);
  expect(crewOnDuty(plan, 11 * 3600 + 59)).toBe(3);
  expect(crewAt(index, plan, 1, 11 * 3600)).toHaveLength(3);
  expect(crewAt(index, plan, 1, 12 * 3600)).toEqual([]);
});
