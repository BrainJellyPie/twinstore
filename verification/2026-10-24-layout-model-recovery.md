# Correct unusable layout and experiment model drafts before caching

Automatic layout editing and A/B experiment drafting cached structurally valid
model responses before resolving their products, shelves and prices. When all
changes were rejected, conversion raised an error after caching. Retrying the
same request could therefore return the same unusable draft indefinitely.

Both request-local response models now run the existing conversion checks inside
Instructor's two-attempt budget. The model receives one correction before failure.
When no change survives, the error includes up to three existing conversion
warnings, so correction can name the actual missing target or invalid amount.
Prompts state the usable-change requirement, negative discount convention and
representable prices. Their updated schemas/prompts avoid old cache identities.

Existing partial drafts still keep valid changes and warnings; no new persistence
or application occurs. Conversion checks continue to apply edits only to copies.

The offline HTTP matrix covers two entry points, immediate correction versus
repeated failure, and 12 unusable outputs: unknown/ambiguous products, unknown
shelves, positive or missing discounts, missing category percentages, missing
or negative prices, infinity, huge finite prices, and sub-minor USD/JPY prices.
It verifies exact attempt counts, specific feedback in the correction request,
successful later retries, cache reuse and unchanged source stores. Two controls
preserve usable partial edits without retries.

Before: 48 failures reproduced and two partial-draft controls passed. After:
114 focused recovery, existing conversion and HTTP endpoint checks passed in
7.37 seconds. Strict Pyright reported zero errors; `git diff --check` passed.
No live inference or paid provider requests were used.
