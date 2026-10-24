# Include direct buyers in group-interview evidence

Group-question generation counted a shelf visit only when the timeline had a
BROWSE event. A valid planned purchase can skip that event. Those buyers were
included in the whole-run total but omitted from their shelf's visit and buyer
counts; a mixed shelf could appear to have browsers and no buyers. Moving a
direct purchase to another shelf also left this evidence unchanged.

Count the union of browsed and purchased shelves for each shopper, matching
the run analyst's existing stop definition. Purchase quantity and repeated
visits do not multiply visitor counts. Empty-handed visitor counts and impulse
unit totals retain their existing definitions.

Eight failures were reproduced, with six controls passing in 2.46 seconds.
Tests execute actual paths and purchase timelines, then send the resulting
summary through LiteLLM/Instructor to group-question generation in both JSON
modes. They cover direct buys, mixed browsers/buyers, repeated browsing and
purchase lines, quantities, different shelves, walk-throughs and rejected
invalid purchases. Identical evidence reuses cache; moving a direct purchase
now changes the prompt and requests fresh questions.

Afterward, 74 focused interview, personal-context, multilingual-question and
API tests passed in 6.34 seconds. Pyright reported zero errors and warnings.
The 31 pytest warnings are existing async logging cleanup warnings. No real
model inference or model download was used.
