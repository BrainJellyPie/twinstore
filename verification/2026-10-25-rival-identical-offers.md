# Do not weight rival prices by repeated detections

The comparison counted every captured row as a price observation, even when
several rows described the same product at the same price. With Tea at twice
our price and Coffee at half our price, one observation each gave index 1.0.
Repeating only the Tea detection nine times changed it to about 1.741 and
reduced the suggested venue pull to 0.67, without any changed products or prices.

Price observations now use the resolved product and rival price as their
identity. Identical offers count once; genuinely different rival prices remain
separate offers. Product counts and unmatched lists also use resolved/normalized
identities, so case differences and confirmed aliases do not inflate counts.

Eighteen new checks failed before the change and seven controls passed. The
focused comparison/API suites now pass 194 checks in 5.61 seconds; full-source
Pyright reports zero errors and warnings. Cases include one/two/nine detections,
different shelf levels/facing counts, reversed order, case and alias variants,
unmatched duplicates and different prices for one product. Four API cases
apply a neutral comparison repeatedly after changing only duplicate counts
and verify the saved venue attractiveness and capture source remain correct.
Existing synthetic shelf scenes and alias integration checks also pass.

No native model inference, weights or paid calls were used. This checks
aggregation of supplied capture/model matches, not detection accuracy.
Existing third-party LiteLLM logging cleanup warnings remain.
