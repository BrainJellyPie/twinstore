# Run comparison display currency

The API resolves each run's saved currency from its summary, configuration or
store snapshot and returns that currency with the comparison. The frontend's
comparison type omitted it, and the dialog instead read only the cached run-list
summary. A valid KRW report with missing summaries therefore displayed 4,200 won
as $42.00; a zero-baseline 500-won gain displayed +$5.00.

Use the report's explicit currency for table values, zero-baseline headlines and
confidence intervals. Keep the run-summary fallback for older reports with no
currency or an empty value. The API type documents this optional compatibility
field. No backend calculation or monetary conversion is changed.

Nine of the 15 added display cases failed before the fix. Afterward, 84 focused
comparison, optimization and money tests passed in 7.46 seconds. They include
KRW/JPY/USD with absent, matching and conflicting summaries, absolute gains and
intervals, plus absent/empty/whitespace older report currencies. TypeScript and
ESLint passed. Vite built in 20.34 seconds with existing large-chunk/Babel timing
warnings. No full suite or paid model calls.
