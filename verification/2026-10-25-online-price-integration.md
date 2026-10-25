# Price experiments and sample planning integration

Integrated online feature branch d31f2da295f19ac1ff995ab5413871fd04276ecb:
price quick experiments, paired-difference planning hints and visible theme dots.
Existing confirmed-copy retry behavior, model-work estimates, interview repairs
and the concurrent technical report are preserved.

Currency-step rounding previously charged for free products and increased some
prices during a discount (50 KRW became 100 KRW). Preserve zero and the original
finer unit when a price is not a multiple of the customary rounding step. Omit
experiments with no actual price change. Nine new failing currency tests now
cover USD/KRW/JPY free, minimum and rounding boundaries, direction, integer units,
unchanged inputs and no-op experiments. A launcher test confirms repriced products
and options are copied together, and a failed run start reuses the confirmed copy.

At 500 shoppers, the planning hint previously recommended 501 despite the run
limit. Apply the minimum increase before testing that limit. Replace claims that
an uncertain difference probably does not matter, or that more observations will
confirm it, with rough planning estimates and explicit variability assumptions in
all six languages. Seven report tests include the 499/500 boundary, large estimates,
zero effects, missing intervals and already-clear differences; two failed before
repair and five passed.

Final affected frontend and locale checks: 183 tests passed in 28.15 seconds;
TypeScript passed; changed-file ESLint reported zero errors and warnings;
production build passed in 28.12 seconds (existing chunk/plugin timing warnings).
Backend runtime was unchanged, so backend checks were not repeated. No paid
inference or model downloads were used.
