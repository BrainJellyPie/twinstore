# Keep generation probes inside the accepted write budget

A local-model quick sample over 24 operating hours promised **20 written customers / 4 requests** but
actually requested **24 customers / 5 requests**. The probe wrote five customers in one hour, which the
smaller sample allocated only one; subtracting it only from that hour left four excess customers.
Separately, a one-customer probe followed by nine customers was advertised as one request rather than two.

Limit the probe to the smallest offered sample, retain its customers, and scale the remaining hourly
allocations to the remaining daily budget. Count the already-sent probe plus the actual remaining batches
when preparing each choice. Reset settled progress to the returned probe count before writing the rest.
Full-day populations and their hourly distributions still use twins to meet the visitor estimate.

Focused evidence:

- One, two, fourteen and twenty-four hours; local/cloud batch sizes; 1/20/100-customer samples; all/sample
  choices; two weekdays; and both complete and one-customer probe responses.
- Check accepted count, actual model request count, original-vs-twin counts, exact hourly populations,
  unique IDs and final progress. Include a quiet-hour probe with a separately required final request.
- Before the fix: **29 failed, 20 passed in 0.52s**.
- New cases plus generation choice, missing-day and traffic-boundary modules: **101 passed in 3.29s**.
- Strict Pyright on the changed module: **0 errors**.

No live model calls, full suite, frontend or release binary changes. Request estimates still depend on
provider latency, pricing and retry behavior; the fix aligns the application's planned batches.
