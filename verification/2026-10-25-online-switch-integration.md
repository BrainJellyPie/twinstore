# Integrate paired customer comparisons without inventing historical zeros

Merged `claude/online-shopping-features-ji7y0f` at
`82a21690210ca66f92d628a8fbaaa898e0eb2e83`, including paired segment differences,
orders won/lost and individual shopper replays. Existing coupon, ad identity,
survey recovery and experiment retry repairs remain present.

Older persisted reports load successfully with empty segment/switch lists and
zero compatibility counts. The new UI initially presented those defaults as
measured orders won/lost. The customer-switch section now stays absent when no
segment analysis was recorded. New measured zero results still appear normally.
Before repair, the historical-report regression failed and two controls passed.

The merged source passed 84 focused backend tests in 31.59 seconds, including
session, advertising, reminder/coupon, paired comparisons and online APIs.
Full-source Pyright reported zero errors and warnings; backend boot passed.
Frontend online and catalog checks: 91 passed in 12.95 seconds. TypeScript,
changed-file ESLint with zero warnings, and production build (17.93 seconds)
passed. Existing SDK cutoff tests were not repeated because their code did not
change. No paid inference or new release workflow was run.
