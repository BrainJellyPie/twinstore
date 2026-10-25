# Require actual text in staff-script ratings

Pitch ratings required a reply and reason of at least one character, but spaces
and Unicode whitespace satisfied that rule. Such incomplete responses could be
cached and counted as complete pairs in the script comparison.

Both fields now trim surrounding whitespace before checking their length. The
prompt explicitly asks for nonblank text. The existing one-attempt-per-arm
budget and complete-pair reporting remain unchanged. A failed arm excludes that
respondent from both means; short refusals and non-English text remain valid.

Real LiteLLM/Instructor HTTP regressions cover both structured modes, either arm,
either required narrative, ordinary and Unicode whitespace, and fresh or older
cached answers. They verify exclusion from comparisons and segments, retained
valid-arm cache entries, later successful recovery, and subsequent cache reuse.

Before repair: 33 failed, 1 passed in 3.50 seconds. The first repaired run passed
all domain/report/API regressions but exposed an overly strict test equality
comparison between fresh SDK models and cached models carrying different private
metadata. That assertion now compares serialized application data. Final new
coverage passes 34 tests in 2.79 seconds; all 79 distinct focused tests passed
across the final runs. Full-source Pyright reports zero errors and warnings.
No full suite, paid calls, model weights or native inference were used.
