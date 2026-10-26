# Store-details customer drafts on the actual CPU model

2026-10-26, main `69812fe8`. The `profile-draft-night`,
`profile-draft-bookstore` and `profile-draft-sparse` cases in
`verification/local-model-probe.py` call the production `draft_profile` function
with Qwen3.5-0.8B Q4_K_M on CPU only, five threads, seed 0 and temperature 0.5,
matching the application draft temperature. The production output ceiling is
700 tokens, with the existing bounded expansion for truncation. No replies are
mocked. Fresh application caches and a warm server are used; times are not cold
benchmarks. Raw requests, replies and results remain in the scratch artifact
directories, not in the repository.

## Baseline

| Artifact under `/workspace/scratch/cpu-vlm-probe/` | Calls | Seconds | Manual finding |
| --- | ---: | ---: | --- |
| `profile-draft-night-json_schema-1792977665461452149` | 1 | 5.52 | Weekday 22:00–24:00 pharmacy becomes weekend 14:00–15:00 visits, with repeated sentences and invented individual demographics |
| `profile-draft-bookstore-json_schema-1792977673963250363` | 1 | 7.89 | Retains Tuesday/Thursday 18:00–21:00 and $5–$20 per visit, but invents a library job, children and housing, then repeats a closing-hours sentence six times |
| `profile-draft-night-json-1792977684755880606` | 2 | 12.47 | Copies schema definitions; the required profile text is missing |

The pharmacy description names night workers buying over-the-counter medicine,
excludes food/drinks, and explicitly closes weekends. Its generated claim about
weekend afternoons contradicts that source. The pharmacy repeats one whole
sentence three times and another four times. The original two schema-mode logs
said `success: true` based only on parsing and language presence. The saved
`profile-draft-repetition-review.json` records their failed content review.

The reusable probe now detects identical repeated sentences. It reports
`success: false` for those automatic failures and `success: null` when only its
structural/language/repetition checks pass: manual content review is still
required, and the command exits nonzero in either case. This prevents a
well-formed but unreviewed paragraph from being presented as a successful
customer draft. The structure check and automated-check status are separate.
The language-presence heuristic cannot establish correct language throughout.

## Withheld experiments

No production profile prompt, response schema, parser or sampling configuration
changes in this iteration. Several actual-model candidates reduce repetition
but still corrupt facts:

- A compact schema and a short three-sentence, group-focused prompt produce a
  Korean pharmacy draft with Sunday–Friday instead of Monday–Friday
  (`profile-draft-night-compact-json_schema-1792977788403211898`, 2.48 seconds).
  The bookstore output conflates per-visit spending with item prices
  (`profile-draft-bookstore-compact-json_schema-1792977793911035925`, 2.59 seconds).
- In plain JSON, that compact candidate emits actual strings under `properties`,
  but they still introduce payday, incorrect closure days and unsupported salary
  statements (`profile-draft-night-compact-json-1792977799382954710`, two calls,
  9.26 seconds). Accepting the container would not fix its content.
- Compact schema plus wrapper recovery, with the original prompt unchanged,
  still copies type definitions (`profile-draft-night-wrapper-only-json-1792977915925389090`,
  two calls, 7.44 seconds). There is no demonstrated benefit from shipping that
  parser/schema change alone here.
- A more extractive prompt gives an accurate night-pharmacy paragraph in plain
  JSON (`profile-draft-night-extractive-json-1792978056313045147`, 3.08 seconds),
  but its schema-mode counterpart mixes English labels with contradictory Korean
  days (`profile-draft-night-extractive-json_schema-1792978062695966540`, 2.66
  seconds). A name-only store becomes an invented dining business, and the
  bookstore again turns purchase budgets into product prices.
- A customer-only prompt, instructed to omit the separate address/schedule fields,
  still invents Sunday visits, frequency and durations in the pharmacy. For a
  name-only store it fabricates $5–$15 spending and attributes it to the owner.
  The bookstore says no spending data was supplied immediately after quoting the
  supplied $5–$20. These are the `profile-draft-*-customer-only-*` artifacts.

The sparse input is accepted by the current application because it contains a
store name. It tests missing evidence, not a supplied retail assortment. The
mini model's invented dining/handmade-goods claims are not accepted as inferred
facts. The original saved evidence is retained; no generated text is edited to
make a probe pass. The earlier shelf judgment fix remains on main, but does not
imply profile-generation semantics have been fixed.

## Integration

Reviewed upstream `83743479`/`b6bc68ef`: move the online shopper mission into the
goal line to make room for names, wrap long store quick-link and report labels,
and expose clipped names, goals and page titles on hover. These are display
changes; very long text can still be clamped or truncated.

Verification: 26 frontend cases in four affected suites pass (7.46 seconds),
TypeScript and changed-file lint are clean, and the production build passes
(21.35 seconds). The usual chunk-size and Babel-plugin timing warnings remain.
The extended probe compiles and whitespace checks pass. No backend application
changes remain, so the backend checks from the preceding fix are not repeated.
