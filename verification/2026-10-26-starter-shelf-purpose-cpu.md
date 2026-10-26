# Keep suitable shelf purposes during automatic product selection

On main `6cf154b5`, a fresh Qwen3.5-2B CPU run of the French-description
bookstore returned valid JSON, covered all four racks, selected four valid
catalog SKUs and placed them correctly. It nevertheless changed Stationery
to Sports and all three Books shelves to Kitchen Tools. The old probe
reported success because it checked identifiers, limits and placement but
not this fixture's requested shelf purposes.

The probe now checks category meaning for the known bookstore and cafe
fixtures. Replaying the exact baseline cache fails the strengthened checks
with zero HTTP calls and two cache hits. The original result is retained
unaltered, including its old success flag. New cases explicitly repurpose
all bookstore shelves for gift wrapping and exclude stationery in favor of
books, so copying existing categories unconditionally cannot pass.

## Change and actual-model checks

Primary and small-task category requests put the generic catalog before
the actual rack/store requirements. Their prompts start from the suitable
suggested category and explicitly retain it unless excluded/unavailable or
overridden by the owner's requirements. They no longer encourage replacing
suitable shelf purposes merely for variety. The full allowed catalog,
explicit overrides, ID/count checks and product-selection logic remain
available. No merchant-specific category allowlist or post-hoc substitution
is introduced.

An ordering-only trial fixed the Books shelves but still selected Sports
for Stationery (21.35 seconds, two HTTP calls); that incomplete candidate
was not published. The final prompt plus ordering passes the cases below.
All fresh runs use Qwen3.5-2B Q4_K_M, llama.cpp b11878, five CPU threads,
no GPU, 8,192-token context, reasoning disabled, temperature zero and zero
application cache hits. This is the text-based assortment flow on a
vision-capable model. Times are observations, not controlled benchmarks.

| Case | Mode | Seconds | Successful model requests | Result |
| --- | --- | ---: | ---: | --- |
| Original bookstore baseline | Native schema | 24.18 | 2 | Wrong Sports/Kitchen Tools, despite old probe passing |
| Bookstore repaired | Native schema | 20.46 | 2 | Stationery and Books retained |
| Bookstore repaired | JSON | 30.58 | 2 | Stationery and Books retained |
| Explicit gift-wrapping override | Native schema | 8.61 | 2 | All shelves repurposed correctly |
| Explicit gift-wrapping override | JSON | 13.27 | 2 | All shelves repurposed correctly |
| Stationery excluded, books requested | Native schema | 19.98 | 2 | Books only, two selected SKUs |
| Japanese cafe, JPY, one product/category | Native schema | 46.63 | 2 | All nine shelf purposes retained, nine SKUs |
| Isolated small task: retain bookstore purposes | Native schema | 13.87 | 1 | Stationery and Books retained |
| Isolated small task: explicit override | Native schema | 3.99 | 1 | Both rows become gift wrapping |

The last two runs invoke the real small-category helper directly with two
rack rows and the full catalog. They do not claim that a primary failure or
the product/placement stages occurred in those runs. The six full-flow
repaired cases also check source immutability, selected/placed identities,
catalog prices, exclusions and per-category limits. These observations do
not guarantee semantic correctness for every possible natural-language
request; production's hard checks still cover IDs, counts and catalog bounds.

## Evidence and verification

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `starter-semantic-baseline/book-json_schema-1793042420500753496`.
- `starter-semantic-audit/book-json_schema-1793042589724244664` (cache replay).
- `starter-task-last-candidate/book-json_schema-1793042602427001408` (incomplete trial).
- `starter-purpose-candidate/`: native bookstore and override,
  timestamps 1793042717765806979 and 1793042741324644204.
- `starter-purpose-controls/`: four full-flow controls,
  1793042787464461421 through 1793042859761718978.
- `starter-small-purpose/`: two direct small-task records,
  1793042958099207930 and 1793042971971186511; runner
  `/workspace/scratch/probe-starter-small-purpose.py`.

Focused verification passes 1,213 backend cases across 21 files in
42.50 seconds, including primary/small schemas, adaptive recovery, invalid
identifiers, exclusions, product bounds, canonical cache reads and API
placement. Six existing LiteLLM asynchronous logging cleanup warnings
remain. Strict Pyright reports zero errors/warnings; server boot, probe
compilation and diff checks pass. No full suite is rerun.

Frontend code is unchanged and inherits the preceding 138 focused UI cases
and TypeScript/lint/build. Released changelog text and v0.8.2 tag/assets are
unchanged. Logs: `/workspace/scratch/starter-{semantic-baseline,semantic-audit,task-last-candidate,purpose-candidate,purpose-controls,small-purpose,purpose-tests,purpose-pyright,purpose-boot}.log`.
