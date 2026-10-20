import type { Scenario } from "@/shared/api/client";

// Starting point of a custom scenario: an ordinary weekday.
export const BASELINE_SCENARIO: Scenario = {
  id: "custom", name: "Custom situation", description: "", weather: "clear", temperature_c: null, season: null,
  day_type: "weekday", only_days: [], traffic_multiplier: 1, hourly_traffic: {}, crowding: "normal", events: [],
  promotions: [], stockouts: [], budget_multiplier: 1, music: "none", lighting: "normal", notes: "",
};
