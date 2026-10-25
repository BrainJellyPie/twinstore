# Preserve shelf capture at cropped photo edges

A generated 500×400 shelf photo, rotated by six degrees and cropped 35 pixels
at the bottom, reproduced two product-labeling failures out of 33 groups.
The packages were visible, but their price-tag strips mapped outside the
original photo after deskewing. `to_image_box` clipped only the lower bound
of left/top and upper bound of right/bottom, allowing inverted crop boxes.
Pillow raised before those products reached the model. Both rotation signs
reproduced the problem using real band detection, classic facing detection,
grouping and capture orchestration.

All mapped box coordinates now stay within the photo, including boxes wholly
outside it. Recognition retains visible packages and substitutes a white
strip when no price-tag pixels remain. A package with no visible pixels is
explicitly rejected before inference. Existing label prompts already require
empty text and a null price for unreadable tags; no price is invented by this
change. Ordinary nonempty crops use the same processing as before.

The application had a related failure when saving a reviewed capture: an
empty representative crop raised `ValueError: cannot write empty image`,
preventing the new layout from being saved. Older inverted boxes also failed,
while wholly external positive-size boxes could become black thumbnails.
Thumbnail generation now clips to the stored photo and skips empty crops.
Reviewed product data remains available for placement without a thumbnail.

Eight actual LiteLLM/Instructor HTTP cases cover JSON and JSON-schema modes,
both rotation signs, cropped and uncropped controls, cache reuse, and
unchanged source pixels. All 33 visible groups are labeled after the fix;
the scripted provider returns no price, and results retain estimated-price
flags. Eighteen geometry cases cover rotation, downscaling, all four edges,
partial overlap and interior boxes. Three absent-tag cases check white pixels
and retained package pixels. Four external-package controls require the new
explicit rejection instead of relying on an incidental Pillow crop error.
The initial run had 23 failures and 10 passes in 33.02 seconds; four failures
were those new rejection-message controls, not additional production defects.

Ten API cases exercise zero-size, inverted legacy, fully external, fractional,
partially visible and ordinary boxes. They check successful layout creation,
both reviewed SKUs placed, unchanged source layout, thumbnail presence and
dimensions, and capture application history. Before the application fix,
nine failed and one passed in 4.72 seconds. The focused engine run passed 751
checks in 47.60 seconds; application checks plus the existing upload/edit/apply
flow passed 11 in 5.44 seconds, for 762 distinct checks. Full source Pyright
reported zero errors and warnings after the final source edit; backend import
smoke printed `OK`. No native inference, model weights or paid calls were used.

An independent read-only check also confirmed that current llama.cpp's
`--reasoning off` sets `enable_thinking=false`; its separate
`--reasoning-format` option controls output formatting. The managed launch
option was therefore left unchanged. Remote branches were refreshed at
ea0872bb25d9e2ac6aecdd3a4f5d733f8ff51b6f with no new unmerged work.
