import { expect, it } from "vitest";
import type { RunEstimate } from "@/shared/api/client";
import { costText, durationText, formatUsd, runEstimateText, shoppersOverDaysText, visitorsPerDayText } from "../estimate";

it.each([
  [0, "about 1 min"], [0.2, "about 1 min"], [25.4, "about 25 min"], [59.4, "about 59 min"],
  [59.6, "about 1.0 hours"], [90, "about 1.5 hours"], [125, "about 2.1 hours"], [600, "about 10.0 hours"],
])("words %s minutes as %s", (minutes, text) => {
  expect(durationText("en", minutes)).toBe(text);
});

it("words hours with the locale's decimal mark", () => {
  expect(durationText("ko", 90)).toBe("약 1.5시간");
  expect(durationText("ko", 12)).toBe("약 12분");
  expect(durationText("fr", 90)).toBe("environ 1,5 heures");
});

it.each([
  [1.8, false, "about $1.80"], [1234.5, false, "about $1,234.50"], [0.004, false, "< $0.01"], [0.009, false, "< $0.01"], [0.01, false, "about $0.01"],
  [0, false, "about $0.00"], [null, false, "cost unknown"], [null, true, "free on this computer"], [3.2, true, "free on this computer"],
])("words a cost of %s (local %s) as %s", (cost, local, text) => {
  expect(costText("en", cost, local)).toBe(text);
});

it("keeps dollars in every language", () => {
  expect(formatUsd(1.8)).toBe("$1.80");
  expect(costText("ko", 1.8, false)).toBe("약 $1.80");
  expect(costText("ko", 0.001, false)).toBe("$0.01 미만");
  expect(costText("ja", null, false)).toBe("費用不明");
});

it("reads customers as a total over the days", () => {
  expect(shoppersOverDaysText("en", 3640, 7, 520)).toBe("3,640 shoppers over 7 days (about 520 a day)");
  expect(shoppersOverDaysText("en", 140, 7, 20.4)).toBe("140 shoppers over 7 days (about 20 a day)");
  expect(shoppersOverDaysText("en", 140, 1, 140)).toBe("140 shoppers on one day");
  expect(shoppersOverDaysText("ko", 3640, 7, 520)).toBe("7일간 고객 3,640명 (하루 약 520명)");
});

const estimate: RunEstimate = {
  customers: 3640, days: 7, per_day: 520, engine: "pattern_intent_impulse", model: "anthropic/claude-haiku-5-5",
  local: false, model_calls: 10920, minutes: 25, cost_usd: 1.8, warn: true,
};

it("puts shoppers, time and cost on one line", () => {
  expect(runEstimateText("en", estimate)).toBe("3,640 shoppers over 7 days (about 520 a day) · about 25 min · about $1.80");
  expect(runEstimateText("en", { ...estimate, local: true, cost_usd: null })).toBe("3,640 shoppers over 7 days (about 520 a day) · about 25 min · free on this computer");
  expect(runEstimateText("en", { ...estimate, engine: "rule_based", model: "", model_calls: 0, minutes: 0.4, cost_usd: null, warn: false }))
    .toBe("3,640 shoppers over 7 days (about 520 a day) · about 1 min, no model calls");
});

it("shows simulated and estimated visitors a day when they differ", () => {
  expect(visitorsPerDayText("en", 520, 100)).toBe("simulated 100 a day of about 520 estimated visitors a day");
  expect(visitorsPerDayText("en", 520)).toBe("≈520 visitors a day");
  expect(visitorsPerDayText("en", 142.9, 142.9)).toBe("≈143 visitors a day");
  expect(visitorsPerDayText("en", 1200.4, 1200)).toBe("≈1,200 visitors a day");
  expect(visitorsPerDayText("ko", 488)).toBe("하루 약 488명 방문");
  expect(visitorsPerDayText("ko", 1200.4, 300)).toBe("하루 예상 방문객 약 1,200명 중 300명 시뮬레이션");
});
