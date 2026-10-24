# Neighborhood comparisons retain accepted product artwork

Neighborhood VLM studies copied their layout and customers at acceptance but
loaded mutable project artwork when the worker ran. Replacing SKU images or
deleting package assets while queued changed model inputs. After decoded-image
cache eviction, changing artwork between comparison arms could also mix product
design changes into the estimated neighborhood effect.

The start path now uses the existing image snapshot writer under its project
transaction. Both arms receive the same loader backed by the saved image copies,
including explicit absence of artwork. Image, manifest and initial-status save
failures remove the exclusively reserved job directory without queuing analysis.
Existing image read locking, bounded decoded-image caching and occupied-directory
protection remain in use.

## Evidence

- Before the fix, queued and running studies read replaced/added artwork or lost
  deleted package art. Between-arm package deletion and SKU replacement changed
  the second read after ordinary LRU eviction. Adding previously absent art
  between arms was a passing pixel control but had no persistent snapshot.
- Nine cases cover package deletion, SKU replacement and newly added art, each
  while queued, running and between arms. A one-entry cache exercises eviction
  using a second real product image without a large fixture.
- Three failures injected during image, manifest and status persistence leave
  no job directory, submit no worker and do not block project deletion.
- 58 focused checks passed in 29.32 seconds, including setup/customer snapshot
  races, identifier collisions, monetary-unit checks, failed model evidence and
  worker status persistence. Strict Pyright: zero errors and warnings.
- The comparison probe reads both arms through the real engine's image loader
  and then intentionally ends with an offline error. No live model calls or
  claims about predictive model accuracy are involved.

```sh
uv run pytest -q tests/server/test_synergy_image_snapshot.py tests/server/test_synergy_start_snapshot.py tests/server/test_study_interview_identifiers.py tests/server/test_analysis_currency.py tests/server/test_town_synergy_failed_evidence.py tests/server/test_worker_status_persistence.py --tb=short
uv run pyright src/
```
