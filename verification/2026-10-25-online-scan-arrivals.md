# Online branch integration and quick-scan customer conditions

Date: 2026-10-25. Integrates `f6cf9ae9bfaeea001f73aaa9f1cd2c458936e7a4`
and `214002d699c2961df7e736d600e4d97f95ce526a` on top of
`afdce8ac2ead2d75c415e96f1a67f352e8d89f9c`.

The integrated changes include quick design scans, scans of suggested changes,
links from cited analyst evidence to report sections, suggested experiments,
grouped variants, store/run search and revised default visitor conditions. The
new browsing proportions and patience distribution remain illustrative simulation
settings; this integration does not establish their accuracy for a real store.

## Actual CPU reproduction

Qwen3.5-0.8B Q4_K_M on five CPU threads, with no GPU offload, was asked through the
production design chat to make delivery free and remove the welcome popup. Its
response correctly changed only `shipping_fee` and `welcome_popup` in one call.
The production scan then ran 150 real rule shoppers against the saved fixture,
an identical copy and the actual model's draft. Only fixture loading was isolated;
model output, shopper generation, sessions and paired statistics were real.

The scan passed the default missions and mobile share to shopper generation, but
omitted the default arrival mix. All 150 shoppers consequently entered directly.
The ordinary run's default cohort with the same seed had 69 search visitors,
49 direct visitors, 18 social visitors and 14 email visitors. This matters because
these sources land on different pages; a scan could assess a draft against a
different customer journey from the ordinary run it precedes.

The scan now supplies the configured arrivals. The complete generated cohort,
not only its source counts, agrees with ordinary default generation. An unchanged
candidate retains zero paired differences. No saved project is modified.

The actual-model harness gained `design-free-popup-scan`:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case design-free-popup-scan
```

It saves raw HTTP bodies without keys/headers, the scan result and the generated
customer cohort. The earlier analyst probe's rate check now reads the actual
report's rates instead of fixed percentages, since the visitor behavior changed.

## Verification

The baseline API regression failed with only `direct` arrivals. After the fix,
the actual CPU probe passed in one model call and the full cohort matched the
configured ordinary default cohort. The focused checks passed: 82 backend tests,
88 frontend tests, strict backend typing (zero errors/warnings), backend boot,
frontend TypeScript, changed-file lint and the production build (21.49 seconds).
The existing analyst evidence requirement and complete 500-price transfer remain
present after merging. The scan still uses its documented default panel; it does
not copy every custom setting from a separately configured run.
