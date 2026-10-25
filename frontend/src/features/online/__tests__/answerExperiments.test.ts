import { expect, it } from "vitest";
import { experimentsForAnswer } from "../answerExperiments";

const all = new Set(["no_popup", "guest_checkout", "smart_search", "faster", "no_service_fee", "free_delivery", "lower_threshold",
  "cart_reminder", "reminder_discount", "prices_down", "best_seller_deals"]);

it("picks the experiments that test what an answer points at, in the order it brings them up", () => {
  expect(experimentsForAnswer("Most shoppers who left had to sign in first, and the welcome popup made some leave.", [], all))
    .toEqual(["guest_checkout", "no_popup"]);
  expect(experimentsForAnswer("Searches that found nothing ended a third of the visits.", [], all)).toEqual(["smart_search"]);
  expect(experimentsForAnswer("The cited lines say it.", ["Shop friction: fee_left in 4 visits (13%)."], all)).toEqual(["no_service_fee"]);
});

it("keeps to three experiments that apply to the store", () => {
  const answer = "Delivery costs, a long sign-in, slow pages and the popup all hurt; prices look high.";
  expect(experimentsForAnswer(answer, [], all)).toEqual(["free_delivery", "lower_threshold", "guest_checkout"]);
  expect(experimentsForAnswer("The popup hurt.", [], new Set(["guest_checkout"]))).toEqual([]);
  expect(experimentsForAnswer("Conversion is about the same in both stores.", [], all)).toEqual([]);
});

it("does not read a sign-in into other words", () => {
  expect(experimentsForAnswer("The luxury design increased orders.", [], all)).toEqual([]);
  expect(experimentsForAnswer("x", ["Shop friction: signin_reached in 10 visits (33%)."], all)).toEqual(["guest_checkout"]);
});
