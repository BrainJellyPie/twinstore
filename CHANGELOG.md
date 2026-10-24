# Changelog

## Unreleased

- Validate saved results across POS XLSX array-formula ranges, including missing
  child cells and tails beyond existing rows. Prevent silent SKU loss and default
  quantities/prices while bounding declared array areas and cache-tracking memory.

- Stop VLM layout judging when more than half an arm's entrance/shelf model
  calls fail, even if fallback customer journeys complete. Reject a bad pilot
  before calibration and further judging; disclose smaller failure counts in
  report notes instead of presenting fallback behavior as clean vision evidence.

- Keep undefined surrogate/VLM rank agreement out of optimization report values
  and explanations when either model assigns identical scores to every layout.
  Report the limitation explicitly while preserving candidate selection.

- Reject CSV text containing NUL characters before parsers can silently truncate
  IDs, product codes or amounts. Block corrupt customer uploads before project
  creation and preserve earlier POS/movement reports on rejected uploads.

- Display run-comparison money in the currency resolved by the comparison API.
  Missing or stale run-list summaries no longer render won/yen as cents; older
  reports without a currency still use their saved summary fallback.

- Fit uploaded customer traffic only from explicit calendar dates and clocks;
  incomplete dates and date-only rows no longer invent weekdays or midnight
  visits. Recognize compact/textual midnight, preserve split date/time imports,
  and prevent weekday names from inventing POS receipt dates.

- Normalize reviewed receipt timestamps before exporting POS evidence so ISO
  week dates and alternate separators retain their local date and hour. Detect
  date-only inputs by parsing instead of length, preserving compact timed forms.

- Reject POS XLSX cells containing spreadsheet errors or formulas without saved
  results before they can drop receipts or default quantity/price to 1/0. Check
  the imported worksheet and selected columns, preserve cached zero/empty text,
  and leave existing evidence intact when an upload needs recalculation.

- Reject POS totals that overflow even though each input field is finite, before
  replacing saved fidelity evidence. Treat unrepresentable ratios as unavailable
  so API responses and saved JSON agree instead of persisting Infinity.

- Reject duplicate recognized POS headers in CSV/XLSX before pandas can rename
  them or case/space normalization can select a different product or amount.
  Validate repeated receipt-scope names too; retain distinct alias precedence,
  ignored notes columns and previously saved reports on rejected uploads.

- Mark SKU/rack rank correlation unavailable for constant sales or fewer than
  two products/groups. Perfectly matching uniform sales and single-category
  stores no longer receive a misleading zero/poor rank score; defined zero
  correlations and other fidelity measures retain their meaning.

- Include the retained closing shift in hourly checkout staffing reports. Late
  and after-midnight payments no longer show zero staff/tills while the last
  shift is serving them; weekday maxima and physical till limits are preserved.

- Stop product workbook imports when a product/header cell contains an Excel
  error or a formula without a saved result. Report the original cell address
  instead of turning errors into empty SKUs or zero prices. Reject product rows
  without rack IDs and preserve valid spacer columns and cached formula values.

- Reject duplicate product workbook columns before they can clear SKUs, relocate
  products or overwrite prices. Treat case/space variants and legacy price aliases
  as the same field, with recovery guidance in all six interface languages.

- Import product workbooks from their actual populated range instead of trusting
  oversized or understated worksheet dimensions. Bound rectangular conversion
  before saving, preserve image row references, and explain oversized actual
  ranges in all six interface languages without truncating products.

- Reject negative and non-finite checkout arrival times before capacity searches.
  The expanding search stays bounded even for unusable input; after-midnight
  arrivals retain the previous hour's queue backlog.

- Base checkout wait guidance on recorded hourly waits instead of comparing
  theoretical capacity with the default staffing count. Show the worst observed
  delay, use each hour's staffing for capacity highlights, and explain the queue
  assumptions in all six interface languages.

- Calculate the actual minimum checkout capacity needed for the target mean
  wait. Recommendations no longer stop at 30 tills while claiming to meet a
  target that remains unmet. Cached queue simulations and binary search keep
  large arrival bursts inexpensive to evaluate.

- Stop neighborhood vision studies when more than half the model calls in either
  condition fail, matching marketing experiments. Count both entrance plans and
  shelf glances; completed fallback visits no longer mask an unusable vision
  panel. Smaller failure rates remain visible in the report notes.

- Fail neighborhood basket/revenue studies when a required visitor group has no
  successful evidence. Missing affected pairs no longer imply zero basket effect,
  and missing unaffected visitors no longer borrow the affected group's spending.
  Stop before the second panel when the first already lacks a required group.

- Exclude Shelf Lab counterfactuals with no valid paired responses from lever
  effect summaries. The CLI marks unavailable comparisons, preserves raw outcomes,
  and exits unsuccessfully when no effect can be estimated instead of reporting
  model failures as a measured zero effect.

- Keep captured product identities when existing names identify multiple SKUs,
  including equally close fuzzy matches. Preserve an explicitly known SKU and
  only replace estimated prices when its matching offers agree on one price.
  Ambiguous matches remain reviewable instead of changing with catalog order.

- Split captured product runs across new racks using individual facing positions.
  Wide runs now use the available shelf capacity instead of shrinking onto one
  rack. Preserve reviewed facing totals when distributing boxes, count each source
  product once, and report a product as dropped only when none of it is retained.

- Give each captured product facing its own editable item. In-memory captured
  layouts no longer compound percentage price changes across shared objects or
  change sibling facings when one is edited; bulk edit counts match placements.

- Keep displaced products accessible when a marketing/layout edit moves a product
  into a full slot. Choose a reachable source for the swap or warn and skip that
  slot, while still considering later empty blocks. Unapplied moves no longer
  create empty destination slots.

- Limit optimizer moves to the baseline's exact unreachable offer counts.
  An already-blocked SKU no longer permits hiding its remaining accessible
  facings or different price/photo offers, preventing accidental delisting.

- Audit repeated products without shifting later positions or duplicating missing
  and facing-count findings. Check every read price tag against the SKU's valid
  reference prices on that level, including free offers, and mark only the
  mismatched tag regions.

- Match Shelf Lab photo badges to the captured SKU, name, price and shelf level.
  Repeated SKUs at different prices or heights retain their own offers instead
  of inheriting one arbitrary price/level; omitted offers are counted even when
  another offer of the same SKU fits the rendered twin.

- Match embedded Excel photos to the same decoded SKU used for product imports,
  including cached formulas, rich text, hyperlinks and normalized headers. Preserve
  sparse worksheet row positions and support identifiers such as `constructor`
  and `__proto__` without silently losing their images.

- Exclude unresolvable Shelf Lab model choices from response counts, photo/render
  agreement and paired merchandising comparisons. Invented products, ambiguous
  names and number-only raw-photo replies can no longer masquerade as no-picks;
  a sim2real job with no valid comparison pairs fails instead of claiming agreement.

- Retain reviewed product photo references through Excel export/import using
  hidden workbook metadata. Successfully uploaded embedded images replace the
  corresponding SKU references; missing or failed new uploads retain saved links.

- Reserve Excel uploads while files and images are prepared, preventing a slower
  old file from overwriting a later import. Leaving or switching layouts discards
  staged work before slot replacement; image batches settle before another upload.

- Make downloaded product workbooks reimportable for stores with dining furniture
  and locked faces. Export only product-capable fixtures and exposed faces, retain
  every rotated rack block, and skip empty blocked template rows on upload.

- Preserve discount/reference prices through product Excel export and import.
  The workbook includes `regular_price (minor units)` and bulk slot uploads retain
  it, so reimporting products no longer removes their usual-price reference.

- Mark rack-level POS fidelity unavailable when sold SKUs span different rack
  groups: receipts cannot identify which shelf sold them. Rack ordering no longer
  turns the same evidence into opposite scores; SKU and basket metrics remain usable.

- Compare POS hourly transaction profiles with simulated checkout completion,
  including queue delays and midnight rollover. Visits without usable checkout
  timing are identified and excluded instead of being assigned their arrival hour.

- Keep successful receipt readings when another uploaded photo is malformed or
  oversized. Read uploads one bounded photo at a time and release decoded pixels
  after each model call; unreadable receipts still require review or exclusion.

- Publish simulation completion/failure after updating the layout state, so the
  UI's final refresh sees a locked result or a retryable draft. If completion
  status cannot be saved, failure cleanup removes that run's provisional lock.

- Extend saved-run playback through the last recorded event, including payment
  and departure after closing or midnight. Recorded weekdays and early arrivals
  are included even when a legacy saved schedule omits them.

- Average tied simulated sales rankings in POS NDCG scores, including ties that
  cross the top-K cutoff. Arbitrary SKU ordering can no longer make the same
  tied prediction look like a perfect match or a complete miss.

- Ground stockout substitutions in offers at the shopper's actual shelf position.
  Another block on the same rack cannot supply a remote purchase, and local
  product names, prices and levels now drive replacement selection and budgets.

- Match ensemble cost/runtime history against saved model references and exact
  weights, so reused display aliases cannot apply another model group's usage to
  a new run. Missing or unreadable ensemble inputs fall back to normal estimates.

- Mark scenario-generated extra visitors as copies of their original customer,
  so optimization panels select available distinct profiles before repeated visits.
  Copies of existing twins retain the same original customer reference.

- Keep optimization-result application and its final job-status write together
  with respect to project deletion, preventing a late status write from recreating
  the deleted project's directory.

- Read captured price tags in the same currency units the app prints. Explicit
  dollar/currency and cent markers outrank catalog guesses; malformed grouping,
  multiple prices, negatives and discount percentages remain visibly estimated
  instead of becoming inflated prices or aborting the whole shelf capture.

- Bound the shelf-photo cache by 64 MiB of estimated retained pixels, box metadata
  and cache overhead as well as 256 entries. Decodes that overlap an upload cannot
  reinsert an invalidated old photo; eviction keeps live renderers' images usable.

- Freeze rendered shelf photographs and their product-box mappings for photo-chart
  vision runs. Uploads coordinate with deletion and run startup; layout image URLs,
  product art and matching shelf photos are captured against one SKU image state.

- Freeze product artwork when vision layout optimization is accepted, so queued
  jobs and later candidate evaluations keep the same package/SKU images. Failed
  image copies leave no pending optimization job.

- Reserve existing run directories even when `status.json` is missing. New normal
  and preview runs cannot overwrite legacy inputs, saved results or interrupted
  snapshots by reusing their run ID.

- Freeze product artwork when a vision simulation or preview is accepted. Source
  package deletion, SKU image replacement and newly added photos cannot change its
  later shoppers' inputs; missing saved manifests fail instead of using current art.

- Coordinate study commentary snapshots and commits with study/project deletion.
  Late A/B narratives and survey, shelf, conjoint or staff-script readings now return
  not-found instead of recreating a deleted study or project after a model responds.

- Reject incomplete customer panels before scoring or caching optimization search
  candidates. Failed shoppers can no longer create apparent improvements by changing
  the population; paired vision judging still compares common successful shoppers.

- Select rule and vision purchases only from shelf offers connected to the shopper's
  entrance. Unreachable promoted, cheaper or free offers cannot consume a basket slot,
  reserve a SKU or spend the budget before routing silently drops them.

- Reject operations replay/planning when a shared-store run has lost its operations
  report. Already-depleted purchases can no longer masquerade as original demand;
  malformed saved configuration objects also fail before calculation.

- Coordinate capture corrections and counterfactual photo edits with deletion and
  study startup. Concurrent corrections keep metadata and overlays together; photo
  edits reject a source corrected or deleted during processing instead of saving stale
  results or recreating deleted folders.

- Compute price-sensitivity intersections at actual response thresholds instead of a
  coarse plotting grid. Large price outliers no longer shift all recommendations into
  unobserved price gaps; exact ties and intersections at the final price are retained.

- Keep paid customer-generation models priced when their client limits concurrent
  requests. Endpoint locality now controls cost warnings and local batch sizes, while
  provider timing respects lower concurrency limits.

- Freeze the resolved product images for visual A/B and shelf studies before work is
  submitted. Source deletion, SKU-photo replacement and later photo additions cannot
  change a running comparison; saved shelf evidence and all participants use the same art.

- Coordinate package-image uploads, metadata edits, reads and lock creation with project
  deletion. Late commits cannot recreate deleted image folders; model reads use a captured
  image and metadata snapshot, with unreadable images rejected before provider work.

- Preserve a vision planner's hard spending limit through shared-stock substitutions and
  saved operations replays. Replacements must fit the money left after the other planned
  purchase lines, including quantity limits; stockouts can no longer inflate a capped basket.

- Exclude incomplete shopper runs from cost/runtime measurements for the next run.
  A completed job containing failed or skipped shoppers no longer dilutes provider work
  across its whole requested population and makes a normal rerun appear artificially cheap.

- Prepare town visitors only for the scenario's selected weekdays, keeping the complete
  persona pool available for age matching. Consecutive days with the same demand profile
  and opening hours reuse one demand calculation without changing seeded visitors.

- Reuse neighborhood building lookups and nearest competing-store distances while describing
  a visitor batch. Large town runs, their estimates and vision synergy panels no longer scan
  the same buildings and venues separately for every cloned shopper.

- Reject shelf-test answers that name product badges absent from the displayed shelf.
  Invalid choices no longer count as refusals or missing attention, and incomplete pairs
  stay out of comparisons. Render queued respondent images only when a worker slot is free.

- Account for every vision voter and weighted mixture members in run cost estimates.
  Mixed local/cloud populations retain the paid share's cost and the local server's workload;
  a provider concurrency limit no longer makes a paid cloud model appear free.

- Share demand calculations across neighborhood venue-removal effects. The synergy view
  computes exact Huff-choice and linked-trip changes from one origin/venue calculation
  instead of rebuilding the entire demand report once per venue, preserving report rounding.

- Reduce neighborhood-demand memory by retaining only the focal store's origin shares.
  Dense, supported 3 km neighborhoods no longer allocate unused group-by-venue-by-hour
  arrays of roughly a gigabyte; venue flows and reported demand remain unchanged.

- Restrict shared-store checkout assignments to counters reachable from the customer's queue
  position. Counters across a disconnected wall no longer shorten waits or hide abandoned
  baskets; connected counters and a counter serving both areas retain shared capacity.

- Recheck product-edit and starter-fill sources under the source layout lock at final save.
  Concurrent floor changes now reject an outdated preview; operating and building settings
  are copied from the committed source instead of an earlier, possibly incomplete snapshot.

- Keep customer interviews, follow-up suggestions and group transcripts consistent with project
  deletion. Transcript locks live outside the removable project tree; input snapshots and final
  writes coordinate with deletion without holding the project lock during model calls.

- Coordinate run-analyst snapshots, transcript locks and saves with project deletion.
  Replies arriving after deletion cannot recreate the project; accepted transcript saves
  finish before deletion, while a busy project preserves the existing conversation.

- Use the named category to disambiguate exact VLM product names repeated across shelves.
  A plan for an identically named milk product no longer randomly buys its snacks counterpart;
  global exact-name fallback remains available when the category does not stock that name.

- Prefer named transaction/visit timestamps and recognized date-plus-time pairs when fitting
  customer traffic. Unrelated account creation/update timestamps no longer override usable
  sales times because they appear earlier or contain fewer missing values.

- Fit uploaded customer traffic from each receipt's earliest valid local timestamp, independent
  of product-line order. Date/store/register scoping, significant leading zeros and missing
  register identifiers remain intact; files without receipt IDs still count individual rows.

- Keep uploaded customer evidence available after its text summary is saved. Retrying a
  generation interrupted before traffic-profile persistence now restores visit-time data from
  the retained CSV/XLSX, while reusing the summary without another summarization model call.

- Preserve selected shelf blocks and levels in purchase timelines so VLM surrogate calibration
  measures the height actually chosen for repeated SKUs. Older or pooled-substitution purchases
  contribute a height only when their placement evidence identifies one unambiguously.

- Complete conjoint studies with accepted negative random seeds. Bootstrap estimation now
  uses the seed magnitude, consistently with other marketing comparisons, instead of failing
  after all respondent calls have finished. Nonnegative seeds retain their existing results.

- Validate track CSV structure before parsing movement evidence. Surplus fields and malformed
  quoting can no longer silently change coordinates/timestamps, and sparse imports are bounded
  to two million cells including missing fields. UTF-8 BOM, standard newline variants and long
  quoted auxiliary notes remain supported; rejected uploads preserve the previous movement report.

- Recheck completed runs and coordinate POS/movement report saves with project deletion.
  An analysis that finishes after deletion cannot recreate output folders; an accepted save
  finishes before deletion proceeds, and lock contention preserves the previous report.

- Commit rival-attractiveness adjustments and their reapplication baselines under the same
  project/neighborhood locks. Concurrent applications no longer compound or lose another venue's
  baseline, deletion cannot recreate an orphaned project folder, and baseline write errors restore
  the previous neighborhood value before retrying.

- Count only retained VLM planned purchases in the planning summary. Items rejected by the
  category-breadth limit no longer inflate average purchases or category rankings, and products
  added during trip filling contribute their actual shelf category to the totals.

- Apply VLM planned-spend limits when automatically filling a trip to its requested size.
  Additional products are selected from affordable candidates and their quantities fit the
  remaining budget; expensive usual products cannot bypass the cap, while free items and
  explicitly unlimited plans remain supported.

- Keep VLM shelf choices on the selected numbered offer when names repeat or are ambiguous.
  Exact printed names outrank fuzzy word matches, clipped long names retain their badge fallback,
  and ensemble votes preserve the supported placement of a repeated SKU instead of switching
  to its first price/level/block. Ambiguous names without a usable badge no longer guess a SKU.

- Normalize raw model-action dwell to the existing 0–120-second budget before scenario arithmetic.
  Negative or enormous durations no longer overflow calculations or inflate visits. Scenario
  increases/decreases apply afterward and retain their intended effect on wandering and operating time.

- Drop point-route stops that the shopper cannot reach. Disconnected browsing and move actions
  no longer add time at the previous position or attribute remote shelf visits to shared-store
  crowding; later reachable purchases, checkout and departure continue from the actual location.

- Bound POS CSV tables before dataframe allocation, including missing fields in short rows.
  Small but very wide/sparse files cannot expand beyond two million cells, and invalid record
  widths or quoting fail before allocation; normal UTF-8/CP949 exports retain their identifiers.

- Scope learned model-option restrictions to each endpoint. A server rejecting temperature,
  token-limit names or thinking/reasoning settings no longer changes requests sent to another server
  exposing the same model alias; clients using the same endpoint still share learned restrictions.

- Keep concurrent model fallback working when different servers expose the same model name.
  Late authentication failures and delayed fallback choices retain the newer working configuration
  instead of failing the request or switching it back to an older endpoint.

- Keep model fallback responses out of the previous provider's cache. Queued structured and text
  requests adopt the new provider before sending, and parameter rejections are attributed to the
  model that actually received the request instead of another model selected while it was running.

- Reject ambiguous decimal commas and malformed thousands grouping in POS quantities and prices.
  Values such as `0,5` no longer become `5`; valid grouped prices, decimal points, weighed goods
  and returns keep their existing interpretation in CSV and XLSX imports.

- Validate customer CSV column counts and padded table size before creating a project or allocating
  a dataframe. Extra fields no longer shift named columns, and sparse rows cannot expand past the
  two-million-cell limit; malformed uploads report actionable errors before model generation starts.

- Route checkout and departure to service tiles and exits the current shopper can actually reach.
  Partitioned multi-entrance stores keep the chosen counter when possible, then try reachable
  alternatives; visits with no checkout or exit route fail instead of recording remote payment.

- Exclude purchases that cannot reach the selected shelf block, including disconnected aisles,
  blocked stances and locked faces. Later reachable purchases still proceed, and inaccessible
  products no longer create sales or stockout demand; unknown products remain counted in diagnostics.

- Keep purchases on the selected block of a multi-cell shelf, including its own price and name.
  Rule-based visits decline a blocked selected stance instead of using another block's aisle;
  purchase diagnostics check the reached block's offers and locks.

- Keep saved customer IDs containing slashes usable in journey, interview, follow-up and reset routes.
  The exact ID reaches the existing customer lookup and bounded transcript storage without changing
  saved identities or conflating customers that share a trailing ID component.

- Reject XLSX files whose expanded archive or sparse worksheet ranges exceed ingestion budgets
  before allocating dataframes. The new-store wizard reports the problem before saving a project or
  calling a model; supplemental reloads and POS imports apply the same bounds without truncating data.

- Keep shelf capture working when one model-read price is nonfinite, overflows currency scaling, or
  rounds below a minor unit. Unusable readings use the existing explicitly marked estimate; valid
  thousand-unit abbreviations remain usable even when the literal amount rounds to zero.

- Avoid catalog classification when rival-price comparisons do not filter product categories.
  Catalog searches reuse normalized bundled names and skip similarity calculations that cannot win,
  preserving exact matches, pack-size handling, category order and reported prices.

- Coordinate neighborhood saves, generation, imports and venue edits with project deletion and
  analysis startup. A late save can no longer recreate a deleted project's data, and a study waits
  for a neighborhood save already being committed.

- Reserve venue-synergy inputs and pending-job registration against project deletion and concurrent
  customer/layout saves. Accepted jobs keep their project, deleted projects stay deleted, and a study
  waits for an input save already in progress instead of silently using the preceding data.

- Recognize explicit POS calendar dates and clocks across two-digit years, named months and compact
  timestamp formats. Reused receipt numbers on different dates no longer merge into inflated baskets.
  Partial dates do not borrow today's date; date-only values do not invent midnight visits.

- Draw building origins for neighborhood visitors and venue counterfactuals from the arrival hour's
  age-specific demand. Night visitors no longer originate from daytime-only building populations, and
  changing one hour's traffic no longer changes otherwise paired visitors' origins in other hours.

- Keep saved customers with Unicode, spaces, punctuation or long cloned IDs accessible in journeys and
  interviews. IDs remain unchanged; transcripts outside the legacy filename alphabet use bounded hashed
  paths in a separate directory, while existing transcript paths remain readable.

- Apply weekend/holiday traffic once in venue basket-synergy studies. They now share the area model's
  scenario traffic calculation, so visitor and daily revenue estimates use the selected day profile
  consistently while retaining weather, event, budget and shopping effects.

- Choose linked neighborhood visitors' source venues using their hour and age group's demand. Morning
  shoppers no longer claim to come from evening-only cafes, and venues with different customer mixes
  no longer receive the same daily source weights at every hour. Older demand reports respect venue hours.

- Recheck project existence and protect photo-upload acceptance through image saving and pending-job
  registration. A project deleted during decoding/model preparation stays deleted. Stable upload retries
  retain their single-job behavior without placing their lock inside removable project data.

- Coordinate Shelf Lab audit/photo-comparison startup with customer/layout saves and project/capture
  deletion. Pending jobs register before deletion can proceed, and audits retain the starting visitor
  estimate instead of changing their daily money scale when metadata changes later.

- Bound each route cache by accounted memory as well as entry count. Large layouts and repeated search
  candidates no longer retain hundreds of thousands of full-map keys regardless of their size. Old paths
  are evicted as needed, and oversized paths are computed without caching.

- Reuse parsed POS timestamps within each import, with a bounded cache. Receipt product lines no longer
  repeatedly parse identical date/time strings for both receipt grouping and hourly fidelity.

- Keep the server responsive while comparing runs, scoring uploaded POS data or exporting customer CSVs.
  Their synchronous file parsing and calculations now run in the worker pool, allowing unrelated status
  requests to complete while the analysis is still in progress.

- Preserve existing customers when regeneration finds no open weekday. Missing, empty or entirely closed
  saved schedules now fail before model setup instead of completing with an empty replacement population.

- Evaluate POS hourly fidelity only when a clock is present. Date-only CSV/Excel cells no longer invent
  midnight visits, while explicit midnight remains supported. Each receipt uses its earliest known hour,
  so missing clocks on the first line or reordered product lines no longer erase or change the score.

- Keep measured customer-generation probes inside the chosen quick-sample budget. Broad hourly traffic
  no longer requests more customers and model batches than promised. Plans account for a partial probe
  as its own request and include the actual remaining batches before the user chooses.

- Scale daily experiment and shelf-audit money using each included weekday's visitor estimate and sample
  count. Excluded busy days no longer inflate quieter-day reports. Missing or invalid estimates fall back
  to that day's observed customers without discarding usable estimates for other days.

- Validate saved customer records and unique, nonblank IDs before simulations, estimates, optimization
  and customer studies. Duplicate IDs no longer bypass sample caps or collapse distinct customer results;
  invalid saved records report a repairable input error before work is registered, preserving the source file.

- Keep trade-area customer types and visit purposes within the same limits as generated customers.
  Overlong model labels now trigger correction during analysis instead of making subsequent customer
  batches fail while attempting to repeat incompatible labels verbatim.

- Distinguish POS receipts by explicit calendar date and available store/register identifiers during
  fidelity comparisons. Reused receipt numbers no longer merge independent baskets and distort
  transaction counts, average-basket ratios or basket-value distances. Original receipt labels remain intact.

- Ignore malformed model-cache containers and replace them after a successful provider response.
  Null, numeric, string or array cache entries no longer block generation and every subsequent retry
  before a model request can be made.

- Estimate new model work from valid uncached runs, falling back to engine defaults when necessary.
  Cached replays no longer suppress cost warnings or understate runtime. Malformed history files and
  mixed timezone clock records no longer break the estimate endpoint.

- Keep project browsing usable when customer/layout files contain the wrong JSON container or metadata
  has a non-string creation date. Invalid customer containers appear as missing customers, malformed
  layout files are skipped in lists and named on direct access, and original files remain untouched.

- Validate customer arrival hours as 0–23 before saving. Out-of-range hours previously saved successfully
  and then silently removed those customers from runs with operating schedules.

- Reject repeated weekdays in store schedules before creation, layout saves or customer generation.
  Conflicting/split entries previously duplicated customers and IDs or made generation disagree with
  simulation opening hours. Unique partial schedules and legacy empty schedules remain supported.

- Retry empty model customer batches through structured-response validation. If an estimated visiting day
  still has no generated customers, fail generation with the affected weekdays instead of publishing a
  partial population and misleading daily estimates. Existing saved customers remain intact on failure.

- Read supplemental customer CSVs exported as Korean CP949 or BOM-marked UTF-16/UTF-32, and recognize
  comma, semicolon and tab separators. These files now reach customer summaries and traffic calibration
  with quoted cells and receipt identifiers intact instead of silently dropping the uploaded evidence.

- Reject repeated hours, invalid clock values and negative/non-integer visitor counts in model traffic
  estimates before they reach customer generation. The existing structured-response retry can request a
  valid estimate, preventing saved daily counts and financial scaling from disagreeing with the population.

- Combine recognized separate POS date/time columns by row, including AM/PM and Excel time cells. Time-only
  values no longer borrow today's date and distort weekday traffic, and unrelated birth dates or durations
  are not combined as visits. Complete timestamps retain precedence when equally complete.

- Keep POS receipt/register identifiers as text during traffic extraction, preserving leading zeros,
  large IDs and literal `NA`/`NULL` identifiers. Mixed UTC offsets or aware/naive timestamp exports now
  retain their recorded local weekdays and hours instead of disabling traffic calibration.

- Preserve distinct POS visits when receipt numbers restart on another date, register or store. Traffic
  extraction recognizes receipt ID columns instead of confusing order timestamps, totals or transaction
  types with IDs, and accepts explicit midnight timestamps without treating date-only exports as visits.

- Recover incomplete automatic starter-product selections before failing store creation. Each category/product
  stage can request one complete correction with the missing, duplicate or invalid IDs and capacity limits.
  Normal selections still use two calls; invalid corrected selections never save a partial project or overwrite
  existing products. Corrective prompts also avoid reusing the same invalid cached response.

- Coordinate concept surveys, shelf comparisons, conjoint studies and staff-script tests with project
  deletion and input saves. Studies use the accepted customer/product data and register pending work
  before deletion can proceed, preventing orphaned jobs and stale study panels.

- Keep A/B experiments on one saved layout, customer list and operating plan, and preserve the starting
  visitor estimate used to scale daily results. Concurrent edits no longer change a running study's money
  scale, and project deletion cannot race pending study registration.

- Start optimization from one committed layout, customer list and operating plan. Input capture and pending
  registration now coordinate with saves and project deletion, preventing stale search inputs and jobs
  registered after their project was removed. Busy starts return a retryable error.

- Capture saved stock, refill and checkout settings under the same layout lock as simulation inputs. Runs
  waiting for an operations save now use the accepted settings, including removal, while later edits leave
  the already captured run unchanged. Explicit overrides and shared-store opt-out keep their precedence.

- Keep completed or canceled customer-generation jobs from returning to "running" when a confirmation write
  finishes late. Accept each generation choice once, coordinate it with the worker's progress handoff, and
  preserve accepted choices at the wait deadline while rejecting answers after the wait has closed.

- Reserve customer generation under the project's layout locks before queuing work. Concurrent requests can
  no longer launch duplicate generators, replace customers used by an accepted final run, accept customer
  edits after generation starts, or register jobs in a deleted project or layout.

- Preserve project edits when metadata saves overlap customer saves or generation results. Serialize updates
  to names, addresses, summaries, traffic profiles and visitor estimates, and prevent a late save from
  recreating a deleted project. Waiting metadata requests leave the API responsive.

- Keep model-generated impulse responses to shopping stops, excluding extra checkouts and exits. Correct
  conflicting purchase/payment navigation so shoppers reach the shelf and till instead of buying remotely,
  leaving early, or abandoning a queue created by their own duplicate payment. Complete missing or malformed
  exits so recorded visits include checkout time and the walk out.

- Serialize customer-list saves with run startup. An accepted save supplies the next run's population; a final
  run that starts first rejects later customer edits, preventing locked layouts from using a different population.

- Coordinate project deletion with starting simulations and layout saves. Deletion rechecks active jobs after
  acquiring the project's layout locks, preventing accepted runs from recreating records in a deleted project.

- Send shoppers to checkout when impulse purchases add a basket to an initially browsing-only visit. Surviving
  purchases now reach the tills even when the model omitted payment, so queue waits and abandoned sales are counted.

## 0.4.11 — Reliable runs, saved layouts and store operations

Released 2026-10-23.

- Add the TwinStore paper citation ([arXiv:2610.30909](https://arxiv.org/abs/2610.30909)), DOI and BibTeX to the
  README, and explicitly acknowledge Intellicia's ParaStore as the original open-source foundation.

- Reserve each run ID across a project's layouts before marking a simulation pending. Concurrent starts with
  the same ID can no longer launch two jobs into one results directory or leave the rejected layout running.

- Keep the API responsive while simulation starts, product uploads, layout cloning/deletion or project deletion
  wait for a busy layout or tree lock. Those waits no longer stop unrelated status and health requests.

- Preserve saved queue-patience and refill thresholds in the run and operations forms. Loading a plan no longer
  rounds 31.25 seconds to 30 or 12.5% to 13%; the UI accepts the server's 10-second minimum and fractional thresholds,
  with matching validation guidance in all six languages.

- Resolve missing model destinations for known-product purchases and checkout. Shoppers no longer record
  remote purchases and payments at the entrance when optional coordinates are omitted; unknown SKUs are still rejected.

- Respect the shopper's chosen checkout instead of redirecting every payment to the first counter. Counter-body
  targets resolve to that counter's service tile, and payment events are attributed to the serving counter even
  when a neighboring shelf shares the access tile.

- Keep wandering shoppers on their planned path when shelf glances consume time. Reserve walking time before
  pauses, fit diagonal steps within the wandering budget, and timestamp glances at their start so playback no
  longer skips tiles or jumps into the next route leg.

- Preserve each source layout's operating settings when reusing template generation, including reordered or
  duplicated building floors. Layout alternatives no longer silently disable saved stock, crew and queue behavior.

- Coordinate new layout saves with parent-tree and project deletion. Deleting a layout while a child is
  being saved no longer leaves orphaned branches; prepared saves recheck their parent and project before writing.

- Keep the source building and floor when applying individual or combined shelf photos. Captured layouts no
  longer lose their floor association in multi-floor projects.

- Keep deleted combined-shelf layouts deleted when an old save is retried, including after a lost response.
  Capture-batch retries coordinate with layout deletion while preserving recovery of successful saves.

- Serialize Excel product imports with layout and operations saves. Concurrent saves no longer erase imported
  products or overwrite newer names, memos or operating settings; busy imports return a retryable error.

- Save confirmed floor changes and product removal atomically. A rejected floor or interrupted connection no
  longer leaves the original floor with its products already deleted; legacy floor reset uses the same save.

- Preserve an engine-selected shelf offer through routing and purchase execution. Different prices for the same
  SKU on separate levels no longer change after budget planning. Stockout loss and substitute selection use
  the selected price, and purchase diagnostics recognize each valid name/price offer on a face.

- Resolve purchases against the shelf face the shopper actually reached when the same SKU appears on several
  faces. Routing, prices and shared stock no longer collapse those purchases onto the rack's first SKU placement.

- Keep saved stock, staffing and checkout settings when creating layouts from product edits, shelf reuse,
  starter products, library photos, text edits or shelf captures. Saved optimization results retain the
  operating conditions used to evaluate them, even if the source layout's settings changed meanwhile.

- Serialize layout-tree deletion with editor and operations saves. Delayed saves no longer recreate deleted
  layouts, and deletion rechecks running simulations after waiting without partially deleting a busy tree.

- Serialize simulation input capture and setup state changes with editor saves. Concurrent saves no longer
  reset a starting run to draft, leave a finished run marked running, or lose newly saved operations settings.

- Bound timed crew refills to the units their scheduled work can handle. Customers buying during a refill no
  longer make extra stock appear without its per-unit work, and reserved checkout tasks keep their place.

- Run regular shelf refills until store closing even when the last shopper leaves early. This keeps overnight
  stock, morning delivery, later sales and refill costs independent of nonbuying observers; no refill starts at
  or after closing. Stores without opening hours continue using their observed visit window.

- Pay for checkout and shelf-refill work that continues after a scheduled shift ends. Count only the workers
  still doing that work, and avoid charging twice when a later staffed hour begins.

- Include checkout service finishing after closing in staffed till hours, labor costs and utilization even
  without a shelf crew. Honor an explicitly configured zero-second checkout in the customer timeline.

- Keep the original operating days when forecasting customer retention. A day losing its last customer still
  pays its scheduled staff and stock-holding costs, refills shelves overnight and receives configured deliveries;
  otherwise forecasts could erase fixed costs and change later stock availability merely because a visit vanished.

- Apply newly requested minimum/maximum shift lengths to existing rosters before comparing their costs. Preserve
  weekday staffing, reject operating windows too short for the requested shift, and keep returned plans savable.

- Keep abandoned baskets in stock when their shelves have already been refilled: excess units return to the
  finite backroom, and staff resume refilling any shelves of that product. Previously those units disappeared,
  reducing later sales and overstating stockouts, including on the following day.

- Use natural virtual-customer generation language in all six UI languages, with correct visitor
  count grammar, explicit daily-sample copying and localized model-start recovery. Disabled local
  models point to API-key settings. Keep choices, estimates and original diagnostics unchanged.

- Complete nine more default-map departments with 64 sweets, jewelry, pet, digital,
  travel, art, tabletop-game, plant and spice photos, reaching 1,312 local images.

- Serve shoppers already at the till before starting a same-time crew refill.
  Keep crew hours and refill results visible when the scheduled hours are zero,
  and preserve a valid default crew when a plan leaves every hour unstaffed.

- Add 64 more pet-walking, car-detailing, composting, watering, embroidery,
  knitting, paper-craft and food-packaging photos, reaching 1,248 local images.
  All eight departments now have a photo for every product in their default maps.


### A roster the crew can work: shifts by weekday
- The crew can now be set as shifts — from one hour to another, on chosen weekdays (none = every day), with a
  number of staff — instead of numbers hour by hour. **Try other stock and staffing → Shifts** edits them; with
  shifts, they decide who is on duty in each hour of each weekday, and the last shift of the day stays until the
  last shopper has paid.
- **Plan a roster of shifts** (with the shortest and longest shift, 4–8 hours by default) makes **Find the best plan**
  answer with a roster: shifts covering what each hour needs, then trimmed shift by shift and weekday by weekday
  while that leaves more money after costs — a rota people can work instead of hourly numbers nobody can.
- Store operations names the roster; playback shows its staff on duty by weekday. API: `crew_shifts` in
  `operations` (`start`, `end`, `days`, `staff`) and `roster: {min_hours, max_hours}` on `/operations/plan`.

### The crew at work, in 3D and on a timeline
- In a crew run's playback the staff are in the store: each one on duty stands at their till while serving, at the
  shelf they are refilling (with "Refilling …" over their head), or beside the tills waiting for work — a ring on
  the floor tells staff from shoppers. Combined with the sold-out marks, you can watch a lone cashier leave the
  line to refill the drinks and the line grow behind them.
- **Store operations** shows the crew's day: a row per staff member with their time at the tills and refilling,
  for the day the playback shows, with a mark at its clock.
- API: `crew_tasks` in the operations report (day, member, till or refill, the till or shelf face, start and end in
  clock seconds; the first 3,000 are kept).

### Catalog and fixes
- Add 96 yoga, running, fishing, leathercraft, seed-starting, plant-propagation, candle-care and camping-repair
  products with 96 photos and six-language labels; ten matching default maps stock them. The catalog now includes
  1,688 products in 147 categories and 1,152 local images.
- **Run simulation** waits for the layout's saved store settings before it can start (and offers to try again when
  they cannot be loaded): a run started while they loaded used the default store instead. A backroom holding
  nothing (0 units) is now reported too.
- Add 96 pet-walking, car-detailing, composting, watering, embroidery, knitting, paper-craft and food-gift-packaging
  products with 32 photos and six-language labels; twelve matching default maps stock them. The catalog now has
  1,784 products in 155 categories and 1,184 local images.
- An older run's worked-out summary is recomputed when any of its saved files changes (cached per data folder); a
  damaged file keeps the saved summary.

## 0.4.10 — One crew for the tills and the shelves; a backroom behind them; older runs show their results

### One crew for the tills and the shelves
- Tills and refills used to be staffed separately: refill rounds were instant and cost nothing at the tills. A store
  can now have a crew — **Crew on duty (tills and shelves)** — who serve at the tills when shoppers wait and refill
  shelves when free, so a refill takes someone away from the tills. A shelf is refilled once it is down to a share
  of its full stock (**Refill a shelf once down to**, 50 % by default; 0 = only when empty), by whoever is free
  first, taking 30 s plus 4 s per unit (assumed times to set from your own time studies). The first crew member
  stays at the tills while anyone else is on duty; a lone crew member does both, and shoppers wait while they refill.
- The crew can change hour by hour (`crew_schedule`). **Store operations** shows the staff hours and how they split
  between the tills and the shelves, the shelves refilled, how long a shelf waited for its refill on average and
  the shelves still waiting at closing; the hourly table shows the crew on duty.
- In **Try other stock and staffing**, a staffed hour costs one crew member for an hour, and **Find the best plan**
  tries refill points with shelf stock and the crew hour by hour (up to two more than the tills, or `max_crew`).
- API: `crew`, `crew_schedule`, `refill_at`, `refill_face_sec` and `refill_unit_sec` in `operations`; blank (null)
  keeps tills staffed on their own with refill rounds, as before. With a crew, `restock_every_min`,
  `open_counters` and `till_schedule` are not used.

### One crew for the tills and the shelves
- Tills and refills used to be staffed separately: refill rounds were instant and cost nothing at the tills. A store
  can now have a crew — **Crew on duty (tills and shelves)** — who serve at the tills when shoppers wait and refill
  shelves when free, so a refill takes someone away from the tills. A shelf is refilled once it is down to a share
  of its full stock (**Refill a shelf once down to**, 50 % by default; 0 = only when empty), by whoever is free
  first, taking 30 s plus 4 s per unit (assumed times to set from your own time studies). The first crew member
  stays at the tills while anyone else is on duty; a lone crew member does both, and shoppers wait while they refill.
- The crew can change hour by hour (`crew_schedule`). **Store operations** shows the staff hours and how they split
  between the tills and the shelves, the shelves refilled, how long a shelf waited for its refill on average and
  the shelves still waiting at closing; the hourly table shows the crew on duty.
- In **Try other stock and staffing**, a staffed hour costs one crew member for an hour, and **Find the best plan**
  tries refill points with shelf stock and the crew hour by hour (up to two more than the tills, or `max_crew`).
- API: `crew`, `crew_schedule`, `refill_at`, `refill_face_sec` and `refill_unit_sec` in `operations`; blank (null)
  keeps tills staffed on their own with refill rounds, as before. With a crew, `restock_every_min`,
  `open_counters` and `till_schedule` are not used.

### The backroom: refills come from somewhere
- Refills used to fill every shelf from nowhere. A store can now keep a backroom: units of each product behind the
  shelves (one number for all, or per product) that refills draw from, until it runs dry. Shelves keep last
  night's stock and are filled from the backroom before opening; a delivery each morning tops the backroom up to
  its level (an order-up-to policy), or, turned off, what was there has to last the simulated days — so a week-long
  run shows a popular product's backroom running out on Saturday and the shelf staying empty.
- **Store operations** shows the refills that came up short, the backroom at opening and the deliveries, and for
  each product whose backroom ran dry, when. Units in the backroom are held at the stock-holding cost, and
  **Find the best plan** also tries other backroom levels. API: `backroom_per_product`, `backroom_overrides` and
  `daily_delivery` in `operations`; blank (null) keeps the endless backroom of earlier versions.

### Catalog and fixes
- Add 96 skincare, makeup, nail, shaving, tea, cake-decorating, pantry-organization and shoe-care products, with 32
  photos and six-language category labels. Twelve matching default maps stock the added departments. The catalog
  now includes 1,592 products in 139 categories and 992 local images.
- Operations planning can stock a product that starts sold out (0 units) when that pays; till hours must be written
  "00"–"23" in ASCII digits; a damaged saved shopper list is reported (422) instead of a server error.
- Wait for the saved starter layout to appear in navigation before opening it, and recover failed list refreshes
  through the same idempotent save request. Wide operations comparisons scroll within their panel.
- Add 64 more skincare, makeup, nail, shaving, tea, cake-decorating, pantry and shoe-care photos, reaching 1,056
  local images; all eight new departments have a picture for every product in their matching default maps.
- Playback orders the line at the tills by clock time (shoppers who arrived at different times queued in the wrong
  order) and puts waiting shoppers at their own till; crowding counts shelf visits longer than ten minutes until
  they end, and a visit that ends as another shopper picks no longer counts. The weeks table scrolls in its panel.

### Fixes
- A run saved by an older version, the bundled sample store's runs included, said "re-run it to see conversion,
  basket and impulse KPIs". Its conversion, revenue per visitor, basket, units, visit length and segment figures are
  now worked out from its saved shoppers when it is opened (nothing is rewritten); only the impulse share, which
  those runs did not record, stays empty.

## 0.4.9 — Layouts keep how their store is run; shoppers in each other's way; shoppers remember

### A layout knows how its store is run — runs, A/B tests and the optimizer use it
- A layout can now keep its operations: units per shelf level (and per product), refills, tills (and by hour),
  patience and crowding. **Try other stock and staffing → Save for this layout** stores a plan you replayed or
  found; a copy of the layout keeps it.
- Everything on the layout then runs in that store unless told otherwise: **Run simulation** starts from it (and
  keeps hourly tills and per-product stock it has no field for), **A/B tests** run every arm in it — so a promotion
  that empties its shelf or lengthens the line pays for it, and each arm shows the units it sold out and the
  shoppers who left the line — and the **layout optimizer** judges its candidates in it (vision judge included).
- API: `GET/PUT /setups/{sid}/operations`; `shared_store: false` on runs, A/B tests and optimizations turns it off
  for one request, and `operations` overrides it. A finalized layout can still change how it is run.

### Shoppers in each other's way, and the shared store in 3D
- Crowding: when four or more shoppers stand at one shelf at once, an unplanned pick there is given up with a 35 %
  chance (crowded shoppers buy less on impulse — Harrell, Hutt & Anderson 1980; Machleit, Eroglu & Mantel 2000;
  assumed values to set from observation). Planned buys are made however crowded. **Run simulation** has the
  setting (blank turns crowding off); **Store operations** shows the impulse sales lost in crowds, and journeys say
  "too crowded at the shelf".
- Playback shows the shared store: shelves standing empty get a red floor mark and a "Sold out: …" label while they
  are empty, and shoppers waiting for a till stand in a line behind it, earliest first, instead of on one spot.
  The operations report carries when each face stood empty (`empty_spells`).

### Shoppers remember: the weeks after a run
- A bad visit used to cost only that visit. **Try other stock and staffing → Shoppers remember** repeats the run's
  week: after each week, a shopper may stop coming, the likelier the more products they found gone (and did
  without), the longer they waited at the tills, and if they gave up in the line; everyone else comes again and
  makes the same visits. A store that runs out loses customers, the next weeks are less crowded and stock and tills
  stretch further — the loop one day cannot show.
- Each week is shown next to an ideal store (endless stock, no line) that loses only the weekly churn, with the
  same leave-or-stay draw per shopper in both and in every plan: the gap is what operations cost through customers'
  memory, and shoppers who left are counted by reason (stock or tills). **Find the best plan** then judges plans by
  their money over all the weeks, so a plan that costs more today can win by keeping customers.
- The chances (3 % per missing unit, 25 % after giving up in the line, 1 % per minute waited, 1 % weekly churn) are
  assumptions to set from your own loyalty or survey data, not fitted values. API: `memory` on
  `POST /runs/{rid}/operations/replay` and `/plan`; no model call.

### Catalog, photos, translations and fixes
- Per-product stock (`stock_overrides`) may be 0: the product starts each day sold out, refills included, and counts
  as out from opening. Values outside 0–10,000 are refused.
- Add 64 everyday essentials, pantry, book, electronics, music, household and garden photos, reaching 960 local
  images; with the dairy, prepared-meal, dessert, breakfast, coffee, baking, frozen-food, seafood and barista-tool
  (896) and everyday-care, baby, hair, pet, plant-based food, snack, refreshment and car-care (832) photos, 35 more
  catalog departments have a picture for every product in their stocked default maps.
- Localize the descriptions of all 82 built-in store formats in Korean, Chinese, Japanese, Spanish and French,
  including cross-language search; custom or updated server descriptions are kept. New non-English preset floor
  names no longer repeat the level the interface already shows.
- Keep one model-settings action after customer generation fails, with the local-model download/start control.

### Fixes
- Compare did not say when one run's shoppers shared the store (stock and tills, new in 0.4.8) and the other's had it
  alone, as every run before 0.4.8 did, or when the two runs used different store operations: the difference
  looked like the layout's. It now says so.
- Compare's notes were always in English. They now follow the app's language.

## 0.4.8 — Shoppers share one store, store operations; safe updates; nothing downloaded or spent unasked

### Try other stock and staffing on a finished run
- **Store operations → Try other stock and staffing** replays a run's shoppers — the same people making the same
  choices — in a store run another way: units per shelf level, refills, tills open, patience, and tills hour by
  hour. No model is asked, so even a vision run replays in seconds, and the shoppers keep their patience and their
  substitute-or-not draws, so plans compare on the same people. Any finished run replays, including one whose
  shoppers each had the store alone ("what would real stock and a line at the tills have cost this day?").
- With costs for a staffed till hour, a round of refilling and a unit kept on the shelves for a day, **Find the best
  plan** tries hundreds of plans (refill interval with shelf stock, more stock for the products that still run out,
  tills hour by hour) and shows the one leaving the most after costs next to the current one, ready to use in the
  form. Ties go to the plan using less.
- Tills can be staffed per hour (`till_schedule`, 0 closes them for the hour); the tills share one line, first come,
  first served. API: `POST /runs/{rid}/operations/replay` and `/operations/plan`; shared-store runs keep their
  shoppers' visits as decided (`timeline_planned.json`) for this.
- A replay copies only the events it changes; replaying a run is now about seven times faster.

### Shoppers share one store
- Until now every simulated shopper had the store to themselves: endless stock on every shelf and no one else at the
  tills. Runs now play all of the day's visits in clock order against one store. What a shopper takes is gone for the
  next one until staff refill the shelves (every 2 hours by default, or only overnight); a shopper who finds a product
  gone takes another one from the same shelf face (45 % do, as in the 40 stock-out studies of Gruen, Corsten &
  Bharadwaj) or does without, and the sale is lost. Shoppers with something to pay wait for a free till; one whose
  wait runs past their patience (5 minutes for a typical shopper) leaves the line and the basket goes back on the
  shelf.
- The model calls are unchanged (visits are still decided in parallel, then played together), so a shared-store run
  costs the same, and two layouts on the same seed still face the same shoppers with the same patience.
- **Run simulation** has the option on by default, with units per shelf level, refill interval, tills open and
  patience. **Store operations** in the results shows sales lost to empty shelves, products taken instead, the wait at
  the tills (average, 9 in 10, longest), shoppers who left the line, how busy the tills were, a table by hour with the
  fewest tills that would have kept each hour's average wait under 2 minutes, and the products that ran out (when, for
  how long, units lost). Journeys say "sold out", "took … instead", "waited 2.5 min for a till" or "left the line";
  the customer export has each shopper's wait, whether they left the line, and units lost or replaced. API:
  `operations` on `POST /runs`, `GET /runs/{rid}/operations`. Runs without it work as before.

### Safe updates
- The stores of an earlier version are always brought over, from any folder (OneDrive included), and one unreadable
  file no longer stops the app from starting. Details under Fixes.
- A file left empty or cut short by a version before 0.4.3 (it was stopped, or the computer lost power, while saving)
  showed "Internal Server Error" instead of the store gallery, a store, its layouts or its run history. The rest now
  opens: a store whose customers file is damaged opens without customers, a damaged run shows as failed, damaged
  captures, studies and optimizations are left out of their lists, and opening a damaged item names its file. A
  store whose settings file is damaged was left out of the gallery as if lost; it is listed, saying so.
- The local model's llama.cpp program, downloaded by a version before 0.4.3, did not count as downloaded: a newer
  version deleted it and fetched it again. A complete earlier download is now kept, and it comes along when the
  stores are brought over from an earlier app folder, so a local model you already have starts without a download.
- Settings showed a local server (llama.cpp, Ollama, …) as Ready at an address an earlier version or session left
  behind, with nothing running there. It now says Not running.
- Compare paired different people when the customers had been written again between the two runs, which versions
  before 0.4.7 allowed once the earlier run's layout was deleted (the new customers reuse the ids M1001, F1003, …).
  Such customers are now left out, and the comparison says how many.

### Nothing downloaded or spent unasked
- The local model downloads only when you press Start; screens that need a model say so and offer a key or the
  download. Details under Fixes.

### Starter catalog, photos and translations
- Add 64 Korean, Mediterranean, Mexican, Vietnamese, pharmacy and care-product photos,
  reaching 768 locally bundled images. All 18 menu assortments and six pharmacy/care
  departments now have pictures for every existing product in their default maps.

- Keep translated template headings in downloaded SVG titles without changing stored names.

- Add 64 pizza, salad, juice, Indian, Thai, Turkish, Mexican and ice-cream menu
  photos, reaching 704 local images. Seven more menu assortments now have pictures
  for every existing product in their matching default maps.

- Add 64 tea, burger, noodle, sushi, restaurant, bubble-tea and Turkish-menu
  photos, reaching 640 locally bundled images. Tea, burger, noodle, sushi,
  restaurant and bubble-tea menus now have a photo for every product in their
  matching default maps.

- Rewrite open-area and floor-review guidance in six languages, including complete move labels,
  localized floor badges and count summaries. Preserve user names and coordinates during language
  changes; show translated recovery guidance when a floor preview fails.

- Add 64 water, sports/energy drink, coffee, soda, tea, beer, wine, frozen-food and
  ice-cream photos, reaching 576 locally bundled images. Existing convenience, grocery,
  cafe and dessert templates display the new photos automatically.

- Complete photos for all 96 baby feeding, bath, toy vehicle, plush, educational toy,
  puzzle, model building and miniature painting products. Add 64 local images, reaching
  512 photos; they appear on the matching default maps and in image-aware VLM grids.

- Rewrite interior-design, color, floor-plan and recovery guidance in natural Korean, Chinese,
  Japanese, Spanish and French. Share design names across setup, floor review and comparison;
  localize color-reset accessibility labels and preview error recovery without changing stored values.

- Apply the expanded product catalog to all 82 default map templates, with departments
  matched to each store format and bundled product images retained in previews and saved floors.
  The default maps collectively stock every catalog product, including all 131 categories;
  category exclusions, assortment limits and small-floor layouts remain supported.

- Add 96 baby feeding, baby bath, toy vehicle, plush, educational toy, puzzle, model
  building and miniature painting products, plus 32 photos and six-language category labels.
  The catalog now has 1,496 products in 131 categories with 448 bundled images.

- Add 64 hardware, music, gardening, pantry, produce, bakery, dairy, prepared-food and
  personal-care photos, reaching 416 local product images for the 1,400-item catalog.
  Extend six-language category labels to all 123 categories, including the newest home and hobby assortments.

- Complete starter-fill localization in six languages: automatic/manual guidance, catalog
  category labels, eligibility reasons, reviewed prices and retry states. Category language
  follows the selected interface language. Detect duplicate translation keys.

- Localize template operating hours, product-category limits, assortment seeds and settings-file
  import/export in all six interface languages. Keep exact seed values, category IDs and current
  edits when switching languages. Rewrite the new guidance in natural, task-oriented language.

- Add 96 home linen, dinnerware, food storage, pet grooming, hair accessory, woodcraft,
  ceramic craft and gift wrapping products, plus 32 photos. The catalog now has 1,400
  products in 123 categories and 352 bundled photos for automatic or manual placement.

- Translate detailed floor previews, comparison metrics, gate legends and SVG exports into all six
  interface languages. Preserve expanded previews and zoom when changing language, retain original
  layout/product data, and translate the eight newly added starter category labels.

- Add 64 grocery, baby, pet, stationery, art, technology, travel, game and household photos,
  reaching 320 bundled product images. Preserve automatic starter selection and image previews
  when merging the six-language interface; automatic choices and recovery guidance are localized too.

- Add 96 cycling, swimming, climbing, desk, aquarium, bird, lighting and bathroom products, plus
  32 apparel, garden and hobby photos. The bundled catalog reaches 1,304 products, 115 categories
  and 256 product photos, available to automatic category-based placement and vision grids.

- Add 96 products across eight pantry, deli, seafood, barista and party categories, reaching 1,112 products
  in 99 categories. Add 32 cafe and specialty photos, bringing the local image collection to 128.

- Vision shoppers now see available product photos together with names, numbered badges and prices in
  the shelf grid. Bundled, uploaded and reviewed library photos resolve locally. Dense shelves wrap within
  labeled levels; missing or corrupt pictures retain text cards. Shelf tests and interview previews use
  the same renderer, including project photos. Extend the bundled photo catalog from 64 to 96 images.

- Expand the starter catalog by 192 products across 16 specialty categories, reaching 1,016 products in
  91 categories. Add 32 local photos for apparel, books, pets, hobbies and specialty merchandise (64 total).
  Automatic selection sees image availability while retaining store requirements and exact SKU validation.

- New-store creation defaults to selecting bundled catalog products with the text model. Large generated
  floors group equivalent racks, exclusions and product limits are validated, and model failure creates no
  partial project. Six-language controls retain the format-default alternative. Sixteen more grocery and
  household packshots bring the bundled image collection to 32.

- Starter assortment: 144 additional generic products (824 across 75 categories) and 16 locally bundled
  generated packshots. Auto-place starter products defaults to category-aware text-model selection, validates
  exact catalog IDs, previews before saving, and retains manual selection and retry-safe child layouts.

- Step 2 can reuse library product photos in a reviewed, separate layout: bulk SKU links,
  before/after preview, immutable photo copies, source revision checks and retry-safe saving.

### Fixes
- On a computer without the Noto fonts (Linux with DejaVu only), the narrowest shelf views cut the price off a
  tag ("#100…"), so a vision shopper could not see it. Tags now shrink a little further before cutting.
- Keep the model-provider list available when a saved local address has malformed IPv6 syntax.
- Reject malformed Origin headers with 403 instead of a server error.
- Without internet access (or when LiteLLM's online price table could not be downloaded), the warning before a run
  or customer writing had no cost for the default models. Their prices are now built in; a downloaded price still
  wins.
- A tab left open across an update showed an error on the next screen it opened (its scripts belonged to the
  previous version). It now reloads once into the new version.
- The first launch downloaded a local vision model (up to several GB) without asking, even with no plan to use it.
  Nothing is downloaded now until you press Start for the local model, and the button says how large the download
  is. After that it comes back by itself when the app opens, until you press Stop. A model an earlier version already
  downloaded still starts with no key, without downloading anything.
- A vision run, optimization or venue check whose model never answered (a key turned down, no credit, a server that
  is down) still finished, with every shopper quietly on the rule-based plan and labelled as vision shoppers. Until
  the model has answered once, a failed call now fails that shopper, so such a run stops with the model's error.
- With no API key, creating a store failed: it chose starter products with a text model by default. The format's own
  products are now the default until a model is set up, and the new-store form and the customer-writing screen say
  that writing customers needs a model, with buttons to add a key or download the local model (showing its size).
- After an update, a browser that kept the previous version's page could show a blank screen or the old app. The page
  is now fetched fresh on every visit.
- A sample store you deleted came back the next time the app started. It now stays deleted; a new sample store that
  comes with an update still appears once.
- Just opening a shopper's interview had the model write opening questions — a paid call for every shopper you looked
  at. The trip-based questions start an interview now; the model writes follow-ups once you have asked something.
- One click on the bin deleted a finished marketing study, a shelf photo with its reading and Shelf Lab results, a
  counterfactual photo or a group interview — all made with model calls. The first click now asks "Delete?"; a second
  click deletes, and clicking elsewhere cancels.
- "Regenerate" and "Import" on the neighborhood page replaced the current neighborhood, with the venues you opened or
  closed and its storefront ratings, without asking. With a neighborhood on the map they now ask first.
- The sim2real panel in Shelf Lab and the vision-shopper check of a neighborhood venue said nothing about their size
  before starting; they now show how many vision-model calls or shopper visits they take.
- A drafted A/B test (or a recipe) that switched to vision shoppers kept the 300-shopper rule panel — thousands of
  model calls — where choosing vision shoppers by hand starts at 80. Both now start at 80 per arm.
- A run whose model never answered (a key turned down, no credit left, a server that is down) still tried every
  shopper twice before failing, which could take many minutes. Once the first 10 shoppers have all failed, the rest
  are not tried and the run stops with the reason.
- With no API key, the start-up window still said a local model would be downloaded on first use. It now says that
  rule-based shoppers work without a key, and that nothing is downloaded until you start the local model in Settings.
- "OpenStreetMap download failed: … HTTP Error 502: Bad Gateway": the public map server is often overloaded for a
  few minutes. The download now moves to other Overpass servers and tries once more before giving up, and then says
  the map servers are busy and to try again shortly.
- With an API key connected, vision shoppers still ran on the local model, and failed whenever it was not running.
  They now use the connected provider's vision model unless a run picks another (the local model is the fallback
  with no key) — in runs, vision A/B tests, the optimizer's vision judge and the neighborhood synergy runs, and the
  run dialog shows that model.
- Vision shoppers looked ready with no model at all (the local model turned off and no key): the run dialog let the
  run start and it failed with "Start it in Settings", which Settings cannot do. The engine now shows as not ready,
  and the message says the local model is turned off and what to do instead (also for shelf capture).
- Compare no longer shows an impulse-spend drop to 0 against a run made before impulse buys were recorded; it says
  why that row is missing. The note about minor units is gone (amounts are shown as money).
- Other websites open in your browser can no longer use TwinStore while it runs. Before, any page could quit it,
  read or change your stores, or point a model provider's address elsewhere and so send your API key there.
  TwinStore now answers only its own pages.
- After an update, your stores could go missing: if TwinStore was once started without bringing them over (for
  example from inside the downloaded zip), a later start no longer knew where the earlier version kept them and began
  with the sample stores. It now remembers that folder until the stores are brought over.
- Stores in a folder OneDrive keeps in sync arrived empty after an update; their files are now copied.
- One file that could not be read (or a full disk) kept TwinStore from starting at all, and Try again could not get
  past it. Files that cannot be read are now left out and named in the log; if the copy still fails, **Start without
  them** starts TwinStore and leaves the stores where they are. A store kept on another disk through a link is now
  brought over too.
- Clicking the TwinStore icon right after Quit opened the TwinStore that was closing, and then nothing ran. The click
  now waits for it to close and starts TwinStore.
- Clicking a new version twice while an older one was running opened a second tab saying the older one was still
  running. The second click now shows the new one.
- When another TwinStore held your stores without answering, a click did nothing for 20 seconds and then gave up
  silently. The start screen now says so, with Try again.
- On Windows, a new version could not update its copy of uv while an older TwinStore was still running, and fell
  back to the old one. On a slow connection the uv download no longer gives up after five minutes; it stops only when
  nothing arrives for a minute.
- On Windows, starting a second TwinStore emptied the log of the one already running; each now keeps its own log.
- Try again no longer shows when the app files are missing (there is nothing to try again), and the start screen no
  longer cuts Korean text in the middle of a character.
- On Linux, the application-menu entry now works from a folder whose name holds `$`, `"`, `%` or a backslash.
- A data folder chosen with `PARASTORE_DATA_HOME` now gets its own Python environment, so a TwinStore using it
  can run beside the usual one without the two changing each other's packages.

## 0.4.7 — Marketing studio results you can trust

### Marketing studio results you can trust
- A vision-shopper A/B test whose model calls failed finished "completed" with rule-shopper results labelled as
  vision results. It now stops (after the control, before paying for the variants) when most calls fail, and notes
  per-arm failures otherwise.
- A/B tests and Shelf Lab audits drew shoppers who arrive while the layout is closed (dropped by the simulator,
  then blamed as "failed") and scaled per-day money by everyone: with 12–15 opening hours a panel of 100 became 43
  and "+$X a day" was 2.6× too high. Panels and per-day money now come from the shoppers who come, matching the run
  estimate.
- Moving a product onto a shelf side shoppers cannot reach silently took it out of the test; the move is now refused
  with the reason, in A/B tests and in "edit in words".
- A category price change looked free to rule shoppers ("Drink +50 %" won); in tests shoppers now compare with the
  old price. Saved with "edit in words", the new price is the everyday price.
- ".99 endings" always rounded up, so "−10 % and ending in .99" raised most prices; endings now round down (a rise
  still rises), the applied text gives the actual average change, and a new category change starts at −10 % without
  them.
- The price-response curve no longer mixes in arms that also added a sign, moved products or changed a category.
- Concept-test and conjoint CSVs say their currency and minor units; a tie reads "level", not a lead.

### Fixes
- Deleting a layout that had a final run unlocked the customers: they could be edited or written again while the
  run still used them, and comparisons then paired different people under the same ids. A final run on disk keeps
  them locked, and the store still shows as simulated.
- A restart between a final run finishing and its layout being locked left the layout an editable draft; it is
  locked on start-up.
- Concept, shelf, conjoint and staff-script panels drawn from a quick-sample store counted a written customer's
  copies as separate respondents (100 picked held 63 people); written customers come first.

## 0.4.6 — the whole app in your language; neighborhood and Shelf Lab fixes

### The whole app in your language
- The store screen (playback, results, shoppers, store tab, run comparison and optimization), the floor editor,
  Settings, the Marketing studio, Shelf capture and Shelf Lab, and the Area page are now in English, Korean, Chinese,
  Japanese, Spanish and French, as the rest of the app was. Template names, weekdays and times follow the language
  too. Text the server writes (analyst answers, notes, errors, reports) stays English.

- Complete starter-fill localization in six languages: automatic/manual guidance, all 107 catalog
  category labels, eligibility reasons, exact reviewed prices and retry states. Category language
  follows the selected interface language even in KRW stores; existing product identities remain intact.
  Detect duplicate translation keys and keep price-review instructions aligned with the editor label.

- Integrate the store-screen, Settings, marketing, capture and neighborhood translations from
  the current development branch while retaining product workflow validation and automatic selection.

- Add 32 prepared-food, pharmacy and personal-care photos, bringing the collection to 224.
  Starter placement previews show current uploaded or bundled photos for reused products without
  rewriting their saved values. Empty product names retain their SKU label in vision grids.

- Translate shelf-product reuse into six languages, including eligibility reasons, section review,
  price formatting, save/retry and accessibility text. Keep selections and request identities across
  language changes, support translated fixture searches, and retain legacy API reason compatibility.

- Translate product bulk editing end to end in six languages, including validation, mixed values,
  undo, preview and saving. Preserve edits and retry identities when switching languages, format
  reviewed prices by locale, and keep long buttons inside mobile dialogs. Product workflow clients
  retain HTTP status so conflict and invalid-input guidance can be localized correctly.

- Translate the complete reviewed library-photo workflow into all six interface languages, including
  explanations, selection and preview counts, accessibility names, validation and save/retry states.
  Switching language preserves choices and pending requests. Fix the shared dialog footer's untranslated
  Close button and provide localized error guidance with original diagnostics available on demand.

- Previously saved starter products pick up new bundled photos by exact SKU when no custom photo is set.
  Existing uploads and explicit photos retain priority; layouts are not rewritten on read. Add 32 kitchen,
  pet, technology and everyday-product photos, bringing the local collection to 192.

- Add 96 kitchen, home, pet and technology products and 32 grocery/merchandise photos: 1,208 products,
  107 categories and 160 local photos. Vision grids fit bundled product artwork more closely by omitting
  empty white margins, while retaining names, prices and numbered identities.

### Neighborhood visitors
- A scenario run with neighborhood visitors could not be compared with its baseline: changing one hour's count
  renamed every later visitor, so "lunch rush" paired 164 of 533 shoppers. Visitors are now named by their demand
  row, and every visitor of an unchanged hour keeps their name.
- Neighborhood traffic used the convenience store's scenario effects for every format (a supermarket's "Holiday
  season" ×0.80 instead of ×1.16) and never used the neighborhood's holiday profile; weekend and holiday scenarios now
  use the weekend or holiday profile, without counting the day twice.
- Visitors come in the hours the layout opens each day: a 24-hour store had none before 7 am, and an 8–20 store's
  panel counted a quarter of its visitors at closed hours (market share 54.5 % instead of 42.9 %).
- A visitor has the age of the shopper they were made from (a 40-year-old "walked from school" before).
- Running with neighborhood visitors on a project without a neighborhood says so instead of running without them;
  an unknown situation on the Area page is refused; basket synergy reports walking distances like the synergy table.

### Fixes
- Resolve neighborhood label keys in controls, legends and map tooltips instead of showing the keys.
  Keep seeded visitor trip assignments independent of demand-report list ordering so unchanged
  demand rows remain paired when another hour's volume changes.
- Applying a rival shelf's prices to its pull in the neighborhood compounded on every apply (0.82 → 1.03 → 1.28 →
  1.61 for the same photo); it now replaces the earlier adjustment.
- The rival comparison found none of our products in the rival's categories on layouts not made from a template (the
  sample, model-made, hand-built), so overlap read 100 %; our products now get their category from their names.
- A shelf audit of a rack side with nothing planned on it scored 100 % compliant; it is refused, naming the sides
  that have products.
- A wide shelf photo added as new racks on a north or east wall read right to left from the aisle.
- A POS export whose product codes match nothing on the shelves scored 0 on every measure and replaced the run's
  earlier report; it is refused with what to fix.
- The run analyst called the walking path "metres"; it is grid tiles (1.25 m each).
- A store larger than 256 tiles a side is refused (a huge size hung the save).
- A capture cannot be deleted while a Shelf Lab job on it is running (the job wrote its results back under it), and
  an interview with a shopper who is not in the run is "not found" instead of an empty transcript.
- The dwell map counts each shopper's own walking pace, diagonal steps, the time at the entrance and wandering; it
  left about a tenth of the visit time off the map, most of it around the entrance.

## 0.4.5 — every visitor a day, with a warning before long or costly work

### Every visitor a day, with a warning before long or costly work
- A new store's customers were capped at 100 a day (20 with the local model), so a convenience store the model
  expected to see 600 people a day was simulated with 100 (or 20) a day — 140 for a week on the local model. The model
  now writes every visitor each day's traffic estimate expects (up to 1,000 a day; 300 when it gives no usable
  estimate), with the local model as with any provider.
- Before writing them all, one request is written and timed. When the rest would take about 10 minutes or more, or
  cost about $1 or more (LiteLLM's price list), the preparing screen asks first: write them all (about how long and
  how much), a quick sample (100 a day, 20 on the local model) whose twins fill the rest of each day, or cancel.
  Writing shows its progress ("1,240 of 3,640"). Each request writes customers across hours, so a quiet hour's one or
  two customers no longer cost a request of their own (a 20-a-day sample took 14 requests a day, now 4), and a day
  scaled to a number has exactly that many (a 20-a-day sample over quiet hours came to 14).
- The run dialog shows the shoppers a run will simulate (a day × days), the model requests, and about how long and how
  much; above the same limits it asks before starting. A project's last finished run with the same engine and model is
  what the estimate is measured on.
- Per-day money in A/B tests and Shelf Lab audits ("about ₩X a day") scales by the store's estimated visitors a day,
  and the reports say how many a day were simulated when that differs.

### Faster and more faithful runs
- The route map was rebuilt with a path search for every pair of access points on every run and every optimizer
  candidate: minutes per run on a hypermarket or warehouse club (an optimization looked hung for hours). It is one
  sweep per access point now (under a second) and optimizer candidates skip it.
- "Optimize for a situation" now optimizes for it: its promotions, stock-outs, days, traffic and budgets apply to every
  layout the optimizer's shoppers walk (they bought out-of-stock water and noodles before). The saved layout keeps the
  regular prices.
- A run with a customer cap samples from the shoppers who come on the situation's days and opening hours; "Payday
  Friday" with 20 customers simulated 1 (and could fail with "no shoppers come… change the opening hours").
- Situation previews show the effect sizes a run of that layout uses: a supermarket's "Holiday season" said traffic
  ×0.80 while its runs used ×1.16.

### Fixes
- Stop on a vision-judged layout optimization ends the layout run in progress at once; it waited for dozens of vision
  shoppers to finish (minutes on a local model, billed calls on a cloud one).
- A key saved in Settings at the moment the local model became ready could be lost (two writes of the settings file
  at once); they now take turns.
- Customer generation on a small model failed with "List should have at most 10 items" when the model listed many
  customer types but gave a day no visitors (the plain day put every type in each hour); each hour now takes ten of
  them in turn.
- Optimized layouts and "Edited products" drafts stay on their building floor.
- Every CSV download opens in Excel with Korean (and other non-English) text intact; customers.csv says the unit of
  its money columns (e.g. "USD cents").
- A field-pilot observation sheet saved back by Excel (staff 007 → 7, a shift date in the computer's format) imports
  again.
- A concept-test draft for a layout priced in another currency no longer copies its prices over as the survey's.
- Testing a model provider's key says "OpenAI turned this key down (Incorrect API key)…" instead of a raw library
  error; with no key anywhere, messages say so instead of naming the default model's provider.

### In the app
- Opening the floor editor no longer removes a layout's products: they are removed only when a changed floor is saved
  (and put back if the save is refused). Cancel and Esc leave the layout as it was; Esc with unsaved changes asks,
  like Cancel.
- "Delete store and start over" opens the new-store form, as it says, instead of a page of the deleted store.
- Totals say the period they cover ("Totals over 7 days: 3,640 shoppers, ≈520 a day"), and A/B and Shelf Lab reports
  say how many visitors a day were simulated of how many estimated.
- On a phone the store page opens at the top (it scrolled down to the run analyst).
- Testing a provider's key updates its badge at once ("Key turned down"), and the message wraps instead of being cut.
- The sample store's older run shows "—" for conversion and impulse share instead of 100% and 0%, and empty rack and
  product lists say they fill in as shoppers pay.
- The playback panel starts folded on screens up to 960 px tall and no longer lets the compass show through; speech
  bubbles go when the store closes.
- Compare shows spend as money ("$8.45 → $8.62") instead of cents.
- Korean text wraps between words, and the wizard heading's last syllable is no longer cut off.
- The breadcrumb and the run picker no longer cut names and times short on wide screens.
- With the local model turned off by TWINSTORE_LOCAL_VLM, Settings says so and how to turn it on.

### Releases
- Each release now starts on clean Windows and macOS machines before it is published (the launcher's first start:
  uv, Python, every package, the server answering), and the macOS bundle's signature is verified there.

## 0.4.4 — updates keep your stores; photo and vision features check their model

### Updating keeps your stores
- Stores, runs and the local model's downloads now live in a folder of your own (Windows %LOCALAPPDATA%\TwinStore,
  Linux ~/.local/share/twinstore, macOS as before) instead of inside the unpacked app folder, so a new version
  unpacked anywhere finds them. On its first start it copies the stores over once from the app folder an earlier
  version ran from (large model files are linked, not copied), showing it on the start screen. An earlier version
  still running is asked to quit first, so two versions never share the stores at once.

### Photo and vision features check their model
- Shelf capture used the app's vision model without checking it: with a cloud key and no local model, or while the
  local model was still downloading, every product came out as "Product 1.1, 1.2, …" at typical prices and the capture
  said "completed". It now uses the cloud provider's vision model when the local one is not running, refuses to start
  when no model can answer, and fails with the reason when not one product could be read.
- A vision A/B test on a model that cannot answer is refused before it starts (vision shoppers whose every call
  failed fell back to rule-based decisions, and the report said "no winner").
- A concept test nobody could answer fails instead of reporting zeros on a 1–5 scale.
- Failed background jobs (captures, tests, Shelf Lab, the optimizer, neighborhood runs) say what went wrong in words,
  e.g. "the model could not be reached. If it is the local model, start it in Settings…", instead of
  "APIConnectionError: litellm…".
- Interviews, the run analyst, commentaries and study readings record the model that actually answered.

### Editing and settings
- The floor editor no longer throws away unsaved changes on Esc, a click outside it, Cancel or ×: it asks first. A
  failed save or reset says why instead of silently re-enabling the button, and reset cannot run twice.
- The new-store form asks before leaving it (another page, Back, closing the tab) with what you typed still unsaved.
- Saving a correction in shelf capture no longer turns every estimated "typical" price into a read tag price.
- Errors that were swallowed now show: shelf photo and Shelf Lab uploads and deletes, model-provider saves and tests,
  the local model's start and stop, the "Edit floor" confirmation (with the server's reason), and the store gallery
  (in your language, details below). One bad file in a product-photo upload no longer stops the others.
- Photo mode stops when you leave the 3D view (it came back on by itself, with "Fit store view" disabled).
- The Store tab shows opening hours right (24:00 as midnight, closed days as gaps, each day's own hours).
- The layout list and store gallery show a layout as running or finalized as soon as a run starts or ends.
- Money follows the app's language rather than the browser's; the template preview, floor comparison, run readiness
  reasons and floor set-up steps are translated.
- A question about results typed in the command palette while a draft layout is open goes to a layout that has a
  run, instead of disappearing; with no run anywhere the palette says so.
- The local model can be stopped from the banner while it downloads or starts.

### Smaller fixes
- The macOS download is signed (ad-hoc) as a whole bundle: only its arm64 executable was, and Apple silicon Macs may
  call such a download "damaged" instead of offering Open Anyway.
- "Try again" after the local model failed to start (a dropped download) starts it again instead of repeating the
  old failure.
- A program other than a llama.cpp server that reads images, answering on port 8081, is no longer taken for the local
  model; TwinStore starts its own on another port.
- A layout being simulated refuses changes to its store until the run ends (a change saved meanwhile was locked
  unsimulated, or lost to the run's own write).
- A second tab uploading shelf photos waits its turn instead of pausing its whole queue with "Another photo is being
  accepted".
- Survey, conjoint, factorial and staff-script CSVs open in Excel with Korean and other non-ASCII text intact.

## 0.4.3 — failures that say so, the local model behind company networks

### Runs and customers that fail now say so
- A run in which every shopper failed (a key turned down, a model that is not there), or in which no shopper comes on
  the scenario's days and opening hours, finished "completed" and locked the layout and the store's customers for
  good. It now fails with a sentence saying why, and the layout stays editable.
- Customer generation fails with a plain reason when more than half of its requests to the model fail, instead of
  finishing with a fraction of the customers; all days now share one limit of requests at once (seven days of ten
  each were enough to hit rate limits). Provider errors read as advice ("the provider is limiting requests right
  now…") instead of a dump of retries.
- A failed run stays visible on its own layout after leaving the page or reloading (it was kept only in the tab that
  watched it, and showed on every layout); the whole message is shown, not just its first line.
- One failed progress poll during a run no longer replaces the page with an error screen: the last progress stays,
  with "Reconnecting…", and polling continues.
- A store whose customer generation keeps failing can be deleted from its preparing screen.
- The customer data uploaded with a new store (CSV/XLSX) is kept with the store: it lived only in memory, so when the
  first customer generation failed (no key yet, a restart), "Try again" generated customers without it and said nothing.
- "Try again" while another tab is already generating customers follows that job instead of failing.
- Errors with a code and a message from the server show the message instead of "409 Conflict".

### The local model
- The default vision model (`openai/local-vlm` at port 8081) now goes wherever TwinStore's own model server runs —
  another port when 8081 was taken — and waits for its free slots instead of timing out in its queue; shelf capture
  uses the same address.
- A run on a model server on this computer that does not answer is refused before it starts ("start the local model
  in Settings…"): vision shoppers whose every call failed fell back to rule-based decisions and the run looked fine.
  A stopped local model is no longer offered in model pickers.
- An NVIDIA card whose driver is older than every llama.cpp CUDA build got the CPU build with a GPU-sized model; it
  now gets the CPU plan. A build whose download stopped half-way (or lost a DLL to an antivirus) is fetched again
  instead of being reused forever, and TwinStore's own build is preferred to an older `llama-server` on the PATH.
- The local model's download or start can be stopped from Settings while it runs; the run dialog notices a new key
  or a started local model without waiting five minutes.
- An interrupted model download (a dropped connection, a sleeping laptop, a restart) continues where it stopped
  instead of starting again from zero.

### Windows, macOS and company networks
- Behind a company proxy or HTTPS inspection: the first start trusts the system's certificates (uv was given its
  own), the proxy set in Windows' Internet Settings is used for the downloads, and requests to the local model no
  longer go to the proxy (on Windows and macOS every call to 127.0.0.1 did, so the local model never answered).
- A system-wide `PYTHONHOME` or `PYTHONPATH` (left by GIS software or old installers) no longer breaks the start.
- An old `uv` on the PATH (from `pip install uv`) is not used; the launcher's own is.
- A second launch while the first is still starting opens the running app instead of starting another one on the
  same data.
- On macOS and Linux the local model server stops when the app's server stops unexpectedly (it kept gigabytes of
  memory, and "Try again" reused it).
- One damaged file (a power cut mid-save) no longer hides every store: that store is skipped and logged, and saves
  reach the disk before they replace the old file.
- Product photos are found after the data folder moves to another computer or OS.
- The log no longer records every request to the model, images included (it grew by hundreds of MB in a run).

## 0.4.2 — the local model when no key works, and a Quit button

### Downloads
- The release notes and the README say up front that Windows' "Windows protected your PC" warning is expected for a
  new app without a code-signing certificate (More info → Run anyway).

### Quitting
- Closing the browser tab never stopped TwinStore: the server and the local model kept running in the background,
  holding memory and keeping the app from being updated or deleted. Under the launcher the top bar now has a **Quit**
  button (it asks first, since running simulations and the local model stop too), and the app and the boot screen
  warn that closing the tab does not stop TwinStore. The stopped screen follows the app's language.

### Models
- The default text model is **Claude Haiku 5.5** (`anthropic/claude-haiku-5-5`) instead of Gemini 3.1 Pro: an Anthropic
  key is all the app's text features and language-model shoppers need.
- With no cloud API key at all, the text features (set-up helpers, interviews, persona generation, the run analyst)
  and language-model runs use the local model TwinStore runs on the computer for vision shoppers, once it is ready
  (`llamacpp:local`). A cloud provider with a key still comes first, and a run refused for a missing key now names
  the local model when it is ready.
- A key the provider turns down (not valid or revoked) now counts as no key. Customer generation failed three times
  over with Gemini's "API key not valid" instead of using another model: assistive features (customer generation,
  set-up helpers, interviews, the run analyst) now set such a key aside and continue on a provider whose key works,
  else on the local model; customer generation waits for the local model's first download and says so on the
  preparing screen, and asks it for at most 20 customers a day so it finishes in reasonable time. Opened from the app
  icon, TwinStore checks each key at start with a free model listing, so the local model starts downloading right
  away when no key works. Settings → Model providers marks a turned-down key, a run on it is refused with a message
  that says so, and a new key (or a passing connection test) is tried again.
- Customer generation could finish "successfully" with no customers: a small model answered an open day with no
  visitors (or with visitors of no type), and failed batches were only logged. Such a day now gets a plain
  convenience-store day, hours without types get the trade area's customer types, a generation that brings back no
  customer at all fails with a message saying so, and the traffic and trade-area answers are bounded in length so a
  small local model cannot repeat itself for minutes. Requests to the local model server wait their turn in the app
  (as many at once as the server has slots, also for a llama.cpp server found already running) instead of timing
  out in its queue.
- A key entered in Settings now reaches the provider for the default model names too (LiteLLM itself reads only the
  environment), and `GOOGLE_API_KEY` counts as a Gemini key, as it does for LiteLLM.

### Fixes
- The local vision model could not start ("no llama.cpp build for windows/x64 in release v0.7.0"): llama.cpp's latest
  release is now a versioned one without binaries, which come with its numbered builds marked as pre-releases. The
  download now takes the newest of the recent releases that has a build for the computer.
- On Windows the first start could stop at "Simulator" for good: the server process watched for the launcher closing
  its stdin with a blocking read, and Windows makes every other operation on that pipe (a library or child process
  asking what stdin is) wait behind a pending read. It now polls the pipe without reading it, hardware probes no
  longer inherit it, and the boot log says when the simulator is loading and how long it took. If a start still
  stalls, every thread's stack is written to the log every two minutes until the server answers.
- Other Windows-only failures of the same kind:
  - Files are read and written as UTF-8 whatever the Windows code page (the launcher runs Python in UTF-8 mode, and
    the remaining file reads name their encoding): on Korean (cp949) or Western (cp1252) Windows a non-ASCII file
    could not be read.
  - Saving a JSON file while another request was reading it (a run's status polled every second, for example), or
    while a virus scanner looked at it, failed with "PermissionError" on Windows; replacing and reading such files
    is retried for up to two seconds there.
  - The port check no longer sets SO_REUSEADDR on Windows, where it let a busy port look free.
  - The launcher keeps reading the server's output past a very long line instead of stopping, which would have left
    the server blocked on a full pipe.
  - When the app folder's path is long (an unzipped folder on a OneDrive desktop, say), the Python environment goes
    to a short folder under %LOCALAPPDATA%\TwinStore\venv, so package files stay within Windows' 260-character
    limit.
  - The UI's scripts and styles are served with their web types whatever the Windows registry says; on machines
    that map .js to "text/plain" the browser refused the scripts and the page stayed blank.
  - The local model server (llama-server) ends with the TwinStore server even when that is killed outright (a closed
    console window, Task Manager) instead of keeping its memory and port.
  - Product photo uploads and finished model downloads use the same retrying replace, and deleting a project, a
    capture, a pack or a study waits out files still open for a moment instead of stopping half-way.
  - Hardware detection gives PowerShell 20 s (a cold start can take longer than 5 s), does not stop on output in
    the console's code page, and runs once at a time; the local model's port check also needs a port it can listen
    on (Windows reserves ranges for Hyper-V, WSL and Docker).
  - The Korean font for shelf images is found when Windows is not on drive C:.

### Vision shoppers can see the shelf in 3D
- The run dialog's vision settings add **What a vision shopper sees at a shelf**: **Chart** (as before: a flat
  drawing of the shelf with names, prices and numbers) or **Chart + 3D photo**. With the photo, the browser first
  photographs every stocked shelf face in the 3D store (Realistic mode's fixtures, labels, product photos and price
  tags, from a shopper's eye height; chest freezers and tables from above), crops it to the fixture and uploads it
  with the position of every product. Each glance then shows that photo, tagged with the chart's own numbers, above
  the chart: the photo for what catches the eye, the chart for names and prices. Answers map to the same products
  either way, and the same shoppers glance at the same shelves, so the two views can be compared on paired runs.
- Photos are kept per project under a key of what the face shows (products, prices, promotions, fixture, face,
  currency): later runs reuse them, an edited shelf is photographed again, and a shelf changed since, or by the
  day's promotions and stock-outs, is shown as the chart. Run results say how many glances showed the photo.
  API: `GET /api/projects/{pid}/setups/{sid}/shelf-views`, `PUT .../shelf-views/{key}`; run option `shelf_view`.
- The glance prompt for the photo view describes the two parts; chart runs keep the prompt they had.

## 0.4.1 — a dependable first start on Windows, and more set-up in words

### First start
- A slow first start no longer ends in an error. On a computer that scans every new file (Windows with Microsoft
  Defender, for example) the first import of the server can take several minutes; the launcher gave up after three
  and never showed the app even when the server answered later. It now keeps waiting while the server runs, says
  after 90 seconds that a first start can take a while, shows an error after 15 minutes but still opens the app if
  the server answers, and **Try again** restarts a server that never answered (it did nothing while one was running).
- The launcher installs only what the app needs (`uv run --no-dev`: no pytest or pyright for users) and compiles the
  packages while installing them (`UV_COMPILE_BYTECODE=1`), shown on the boot screen, so the server's first import
  no longer compiles thousands of files one by one. The launcher's own health check ignores system proxies.
- When the app is ready, the boot screen shows a large **Open TwinStore** button as it opens the app by itself, so
  the app is one click away if the browser does not follow.

### Reuse a finished shelf assortment
- Step 2 copies exact products, prices, promotions, image links, levels and order from one stocked shelf/fridge
  to up to 100 compatible empty racks, with a preview and a separately saved layout. No model or CSV is needed.
- Occupied destinations and blocked/locked faces are protected; stale snapshots reject saves, and retries
  recover the same child layout. Refreshed currencies cannot relabel an older preview.

### From what shoppers said to a test
- A group interview's result and the run analyst's last answer offer **Turn this into tests**: the text model writes up
  to three test questions from the themes and answers (or the analyst's answer and figures), each with the tool that
  answers it (A/B test, shelf test or concept test) and what it checks, naming the layout's own products and shelves.
  Picking one opens the Marketing studio with that test drafted from the question. What shoppers said stays a
  hypothesis until the test runs. API: `POST /api/projects/{pid}/runs/{run_id}/tests-to-run`.

### Optimization goals in words
- **Optimize** takes the goal in words ("sell more ice cream on impulse, don't move the fridges or touch the drinks
  shelves, at most 6 changes"): the text model sets the objective, what may change, the move limit, whether fridges
  stay on the walls, the shelves that stay locked (this layout's, by name; shown with **Unlock all**) and the
  smallest gain worth keeping. Limits out of range and unknown shelves are reported, not guessed. Nothing starts until
  the user does. The command palette sends "optimize the layout for more impulse sales" to a finished run's
  optimizer with the goal filled in. API: `POST /api/projects/{pid}/setups/{sid}/optimize/goal`.

### A new store from one description
- The create-store form starts with **Describe the store in your own words**: "a campus convenience store at the
  university gate, open weekdays 7 to 23, mostly students" fills the name, a short description (only what was said),
  the address only when a place is given, the type, opening days and hours, and picks the starting store format and
  its currency from the generator's own list. Overnight hours and unknown formats are left for the user with a note;
  an answer that arrives after the user edited the form is dropped. Works in all six interface languages.
  API: `POST /api/assist/store-setup`.

### Resume saved photo queues
- Capture can explicitly save original photos and recognition settings in this browser, restore paused after
  a reload or restart, and reuse stable upload identities even when an accepted upload response was lost.
- Revision checks protect another tab's saved copy; storage failures preserve the live queue and old copy.
  Save/restore makes no model call. Browser storage limits and eviction still apply; see USAGE.md.
- Routed concept/shelf drafts are consumed once so returning to their tabs does not repeat drafting.

### Run analyst
- **Suggest questions from this run** replaces the generic starters with three questions read off the run's fact sheet
  (the shelves, products, hours or groups that stand out). API: `POST .../analyst/suggestions`.
- A shelf picked on the floor of a finished run offers **Ask about this shelf**, which asks the analyst why it sells the
  way it does and what could make more of the shoppers who stop there buy.

### Fixes
- Vision shoppers' shelf glances are now spread over the shelves their route passes equally well: ties were ranked
  by rack id, which sent every shopper's glances to the same first racks of the store whatever the route. Each
  shopper now draws among them with their own seed (`engines.vlm_glance.glance_order: "shuffle"`, the default), so
  runs still repeat exactly and paired layout comparisons keep common random numbers; `"rack"` restores the old
  order. Runs made before this change will glance at different shelves when repeated.
- Newer Claude models (Sonnet 5.5) refuse `thinking: {"type": "disabled"}` and name the value to send instead; the
  client now learns that value per model and retries, instead of dropping the setting and letting the model think
  through the shopper's small answer budget.

## 0.4.0 — TwinStore: the store's digital twin, from photos, in one click

The project is now **TwinStore**, built on intellicia's open-source Parastore (MIT). User-facing
text, the brand mark and the launcher use the new name; internal identifiers (`PARASTORE_*`
variables, storage keys, the Python package, the `parastore` CLI) keep working.

### Find shoppers in words
- The Shoppers tab of a run takes a description ("women in their 20s who stopped at the ice cream freezers but bought
  nothing after 3 pm"). The text model writes a filter (age and gender groups, words from the persona, bought
  something or nothing on the trip or at given shelves, impulse buys, shelves stopped at, products bought or not,
  arrival time, spend, visit length, order); the run's own records decide who fits, so every listed shopper really
  matches. The filter is shown in words; when nobody fits, the panel says how many would without each condition.
  **Interview these shoppers** opens a group interview with the found shoppers as the group. The command palette
  sends "show me students who left empty-handed" here.
  API: `POST /api/projects/{pid}/runs/{run_id}/shoppers/find`.

### Design briefs that set the layout options
- The **Additional design brief** of a generated layout used to be saved as a note only. **Apply to the options**
  now has the text model set what the brief asks for: style, density, size in grid cells, door wall and position,
  tills and their placement, theme and #rrggbb colors, dining tables and seating zone, left-out categories (the
  format's own, by name) and range size. Each option is checked against the options already chosen; one that does not
  fit is reported, and what no option can express (music, lighting, signage text) is listed instead of guessed. The
  brief is still saved with the layout. API: `POST /api/store-templates/{template_id}/brief`.

### Change a layout in words
- **Change it in words** under Store, Layout: "put the green tea at eye level and 10 % off all ice cream" becomes
  the same edits the A/B builder makes (price, discount, sign, move, category price) on this layout's own products and
  shelves, shown in words after they are applied to a copy. "The best seller" uses the layout's last run. **Save as a
  new layout** keeps the result as a new layout that opens next; the original stays as it is. Package changes stay
  test-only. The command palette sends direct edits ("raise every drink price by 5 %") here, and questions about
  them ("would the cola sell more at eye level?") to an A/B test. API: `POST /api/projects/{pid}/setups/{sid}/edit/draft`,
  `POST .../edit`.

### Concept tests and shelf tests drafted from a question
- **Draft the test** in Concept tests: from "which of our two labels looks more premium to people in their
  twenties?" the text model picks the product images to show from the library (by name, with the shelf product and
  price each one shows), the questions, the brief respondents read, a shelf price when price matters, and age or
  gender quotas only when the question names a group. Images the library does not have are reported, never
  invented; "preference" is asked only with two or more images. API: `POST /api/projects/{pid}/surveys/design`.
- **Draft the test** in Shelf tests: from "would the green tea stand out more with a SALE sign?" the model picks the
  product under test (a product of the layout, by name) and the shelf it stands on, and only the changes the question
  asks about: a library pack, a new price, a sign (any short sign, shown beside the usual ones). A product that is not
  in the layout is refused, a pack that is not in the library reported. API: `POST /api/projects/{pid}/shelf-tests/design`.

### Fill existing empty shelves
- Step 2 can select empty shelves/fridges, apply built-in categories, preview starter products and save
  a stocked child layout. Existing products and geometry remain unchanged; inaccessible faces are skipped.
- The template catalog's SKU identities are reused, preserving existing SKU values and image links.
  Reference prices are explicitly labelled, and changed source/catalog snapshots reject stale saves.

### Edit placed products together
- Step 2 now opens a searchable SKU editor for names, prices and promotion text. Select rows for bulk changes,
  undo local edits, inspect mixed prior values and save a separate child layout with all placements preserved.
- Snapshot checks reject stale inputs; stable save IDs recover uncertain responses without duplicate drafts.
  No model call or new spreadsheet is required. See the product editor section in USAGE.md.

### Ask TwinStore from the command palette
- Inside a store, a sentence typed in the command palette (Ctrl K) that names no command can be handed to TwinStore:
  the text model decides whether it is an A/B test ("would a 1+1 sign on cola sell more than a 20 % cut?"), a shelf
  test, a conjoint study, a concept test, a staff script, the neighborhood, or a question about the last run, opens
  that page and drafts from the same words (the A/B variants, the shelf test, the study, the concept test, script B
  for the product the sentence names, the area settings, or the analyst's answer). Nothing runs on its own; a
  request that fits none of these says what can be set up. A request that is not picked up within two minutes is
  dropped. API: `POST /api/assist/route`.

### Ask about this run
- A new **Ask about this run** box in a run's results answers questions such as "which shelf converts worst, and
  why might that be?" from the run's own fact sheet (totals, arrival hours, shelves with stops, buys and buy rate,
  products, age and gender groups). Every answer lists the figures it rests on (only lines that are in the sheet are
  kept), says plainly when the run cannot answer, and offers follow-up questions; the thread is kept with the run.
  API: `GET/POST/DELETE /api/projects/{pid}/runs/{run_id}/analyst`, `GET .../analyst/facts`.

- **Explain the difference** in Compare runs: the model reads the paired comparison (in money, points, seconds and
  metres) and both runs' fact sheets, and says what changed, which shelves, products, hours or groups it came from,
  and what is within noise, with the figures it used. API: `POST /api/projects/{pid}/compare/explain?a=…&b=…`.
- A model reply cut off by its length limit now says so ("the model's reply was cut off before it finished").

### Model-written shopper thoughts
- Vision shoppers now say what they came for: the model's own mission and reason become the first step of each
  journey and the speech bubble at the door ("a cold soda and something salty (thirsty)"); a shopper who turns
  away says why ("turns away: queue").
- Interviews suggest follow-up questions written by the model for this trip and this conversation (the product
  they put back, the shelf they skipped, something in the last answer), refreshed after every answer and reused
  until the conversation moves on. Without a working model the trip-based questions stay.
  API: `POST .../shoppers/{id}/interview/suggestions`.
- **Suggest questions from this run** in group interviews: the model reads the run's numbers (shelves where shoppers
  stopped without buying, impulse picks, empty-handed visits) and proposes three questions, each with the group to
  ask and why. API: `POST .../runs/{run_id}/group-interviews/suggestions`.
- Failed model calls in interviews say what to do ("the provider rejected the API key…", "the model's reply was
  not in the expected form. Try again, or pick another model.") instead of a raw provider error, and a shopper's
  answer gets one more retry when the model puts it outside the expected JSON.
- **Read the answers** on concept, shelf, conjoint and staff-script results: a model groups the reasons respondents
  gave into themes (for paired studies, each arm's share of its own reasons) and writes a short commentary on the
  numbers that ties the two together. It is kept with the study, can be rewritten with another model or removed, and
  appears (labelled as model-written) in the print-ready report. API: `POST/GET/DELETE
  .../{surveys|shelf-tests|conjoints|staff-pitches}/{id}/reading`.
- **Describe the day** in the run dialog's situation editor: "rainy Friday evening, the game next door at 7, 1+1 on
  Pepsi, out of ice cream" becomes weather, weekday, an evening sports match, the promotion and the stock-out, with
  the details opened for checking. Promotions and stock-outs are matched against the layout's products: targets that
  match nothing are left out and listed, and a target that reaches several products says how many.
  API: `POST /api/scenarios/describe`.
- **Draft the test** in the A/B builder: write the question ("would eye level or a 2+1 sign sell more ice cream?")
  and the text model drafts variants from the builder's own changes (price, discount, sign, move, new package,
  category price) on the layout's products, shelves and product images, with the products to track, the engine and a
  rationale. When the layout has a final run, each product is listed with its units sold there, so "the best seller"
  is found rather than assumed. Changes that point at nothing are left out and listed, as are changes that would do
  nothing. API: `POST /api/projects/{pid}/experiments/design`.
- Drafting prompts list the products a question names first and share the rest across shelves, so a long catalogue
  is no longer cut off at whichever shelves come last.
- **Write an alternative** for staff script B: the text model drafts another script for the same product and offer,
  using only the verified facts given and an optional direction ("lead with value"), and says what it changes.
  API: `POST /api/projects/{pid}/staff-pitches/draft-script`.
- **Draft the study** in the conjoint builder: write the question the study should answer and the text model drafts
  the product, attributes, levels and price levels in the study's currency, bracketing comparable products of the
  active layout (cited when the model used them), with a short rationale; everything stays editable before fielding.
  API: `POST /api/projects/{pid}/conjoints/design`. The example studies now give KRW and JPY price levels of a
  plausible size and leave prices empty in other zero-decimal currencies instead of multiplying dollars by 1,000.
- Interviews, report commentary and the set-up helpers no longer fail when the app's text model has no API key:
  they use a fast model of a provider that has one (the model actually used is recorded). Simulation runs and studies
  keep their configured model.
- Store tiles on the home page draw each store's own layout (fridges glowing, the counter marked) instead of the same
  generic block for every store; `GET /api/projects` lists the active layout's `footprint`.
- Product images are **named from what the pack says**: on upload (on by default) and with "Read the pack" on each
  card, a vision model reads the name, brand and size printed on the pack instead of using the file name, and links
  the image to the layout's product when it is an exact match and the image was not linked yet. With the local
  vision model off, a cloud vision model that has a key is used. API: `POST .../lab/packages/{id}/read`.
- The create-store form can **write the customer profile from the store details** (name, type, description,
  address, opening hours) in the form's language: who shops there, when and why. API: `POST /api/assist/customer-profile`.
- Persona generation is grounded in the project's neighborhood model when there is one: the prompt carries who
  comes on a weekday and at the weekend (students, office workers, residents, commuters, linked trips), the busiest
  hours and how far people walk. It also uses a model that has an API key when the app's text model has none.
- **Describe the area** in the neighborhood generator: "a busy campus street, two rival stores nearby, a café next
  door" sets the archetype, size, density, rivals and neighbors; generating stays a separate step.
  API: `POST /api/projects/{pid}/town/describe`.
- Runs no longer start on a cloud model whose provider has no API key (every shopper would fail): the run dialog
  starts from a fast model of a provider that has one and says so, or explains how to add a key; the server refuses
  such a run with the same advice. `GET /api/engines` reports `model_ready` and `suggested_model`.
- A rival's shelf compared with ours now matches products whose names differ ("Coca-Cola Original 500ml" against
  "Coke 500 ml") through the text model, same brand, variant and size only; the card lists those matches, and when the
  model cannot be reached the comparison says which products were matched by name alone.
- A storefront photo whose vision call fails leaves the venue's pull unchanged and says why, instead of saving an
  image-statistics guess into the demand model.
- Theme coding no longer fails when a model returns more than six themes: the smallest fold into "Other". This also
  fixes group interviews that lost their themes this way.

### Conjoint studies
- New **Conjoint** tab in the Market page: a choice-based conjoint on the project's personas. Define a product's
  attributes and levels plus price levels; each respondent gets their own level-balanced random choice tasks
  (2–4 versions, optionally "none") and answers them in one model call.
- A pooled multinomial logit (level dummies, one price slope, a constant for none, a weak ridge prior) gives
  centred **part-worths**, **attribute importance** and **willingness to pay**; intervals resample respondents.
  Importance by age group and gender, fit (hit rate vs chance, McFadden R²), verbatims and caveats.
- **Market simulator**: build a line-up of up to four products from the tested levels, move prices within the
  tested range and see logit shares of preference (and "none") and the first product's share-versus-price curve.
- Print-ready HTML report and a long-format CSV (one row per option shown) for re-estimation elsewhere.
  API: `POST/GET /api/projects/{pid}/conjoints`, `GET .../conjoints/{id}`, `.../report.html`, `.../export.csv`.

### Multi-photo capture intake
- Capture accepts several selected/dropped shelf photos into an explicit-start queue, with byte-based duplicate checks, per-file/total limits, sequential recognition, per-photo review and safe retries. It connects directly to combined shelf layout creation.
- Pause stops later uploads; accepted server jobs are preserved. Request IDs prevent duplicate recognition on uncertain retries, while removed uploads cannot be resurrected by replay. Interrupted server jobs become failed for an explicit new attempt.
- Boundary fixes preserve queued currency across project refreshes, handle executor rejection and keep hidden upload controls out of the editing view.

### Combine reviewed shelf photos
- Capture now selects up to 20 completed photos, previews their combined floor plan, registers product crops and saves one new child layout. Opening it is explicit; the base layout and source photos are preserved.
- Full product-name matching keeps similarly named variants separate. Dropped products block saving; reduced facing counts require explicit acceptance. Estimated/missing prices remain visible review warnings.
- Source-bound previews, stable save request IDs and atomic draft records protect stale selections and uncertain retries. Boundary fixes cover legacy currency fallback, long IDs, invalid numeric data and refreshed layout lists hiding the saved result.

### Observed shelf and checkout price checks
- New **Market → Price checks** joins two independently supplied observation CSVs, preserving missing sides and excluding mismatched SKU, package, currency, date or purchase terms.
- Exact integer price differences, separate positive/negative currency sums and a sources-and-scope-bound audit export. No automatic price updates, legal verdicts, inferred customer losses or population statistics.
- Boundary regressions reject numeric epoch strings in date inputs and keep upload errors attached to the file that needs correction.

### Research protocols and amendment history
- New **Market → Protocols** records complete original plans and append-only amendments with reasons and self-declared data stages. Field differences and planned-sample changes are derived from retained snapshots.
- Canonical linked hashes, atomic saves, cross-process locking, idempotent creation and expected-head checks protect the application workflow from stale overwrites and uncertain retries. JSON and CSV exports bind to the displayed head.
- Boundary regressions withhold sample deltas across changed analysis units/evidence sources, and prevent delayed save replies from replacing a newer displayed revision.
- Local hashes and server timestamps are explicitly not external preregistration, authenticity proof or confirmation that outcomes were unseen; no model calls or study-validity score.

### Observed competitor unit prices
- New **Market → Unit prices** worksheet normalizes recorded pack prices to kg, l or item, comparing eligible focal and competitor minima within an asserted comparable group and currency.
- Stale/future observations, conditional offers and unavailable stock remain visible with exclusion reasons. Exact arithmetic preserves ties and small gaps; missing sides and zero percent denominators remain unavailable.
- Source-hash-checked audit CSV includes inputs, scope, exact rates and comparisons. No models, price changes or sales-effect claims.

### Paired price × sign analysis
- Completed A/B reports can review a supported 2×2 price/discount × promotion-sign design without extra
  simulation/model calls. New runs retain minimal shopper outcomes before intersection; legacy aggregate
  reports explicitly remain unavailable. Only exact same-SKU single factors and their combination qualify.
- Main effects and difference-in-differences share one four-cell cohort. Missing outcomes remain unknown;
  intervals require complete coverage and at least 30 shoppers. Three-contrast Bonferroni percentile intervals
  are exploratory synthetic-panel summaries, with no winner, p-value or real-sales claim.
- Source-hash-bound CSV includes exact changes, metadata, selected shopper cells and exclusion indicators.
  Boundary tests found that contradictory purchase/units/spend records were accepted; these now reject the
  snapshot while genuine zero-price purchases remain valid. Unsupported capture does not fail the existing A/B run.

### Inventory performance review
- New **Market → Inventory** worksheet reconciles observed SKU movements, then calculates explicitly defined
  period net unit sell-through, turnover and GMROI from operator-supplied cost records. Missing/duplicate inputs
  are rejected; stock/value conflicts withhold ratios without silently dropping rows from totals.
- Export source inputs, period, source SHA-256 and review flags. No model calls, annualization, invented costs,
  automatic orders or causal sales claims. Reviews are read-only and are not saved in the project.
- Boundary testing caught a missing reason for unavailable portfolio turnover in return-heavy periods;
  negative net COGS is now explained in both the UI and audit CSV.

### Observed staff time
- Review anonymous timing CSVs against locked fixed staff-script plans, including refusals and non-delivery.
  Missing time remains unknown; arm averages and differences require complete coverage. Staff/shift counts,
  a blank template, source SHA-256 and revision-bound audit CSV support review without modifying outcomes.
- Preserve small mean-time differences in the UI; zero-traffic and zero-contribution cost scenarios no longer
  display or export negative zero.

### Fixes
- Realistic shoppers no longer crash the 3D view when React remounts them (development StrictMode): the
  per-shopper animation mixer is no longer uncached while its actions are still reused.

### Shopper journeys and interviews
- Playback has a **Shoppers** tab: rank the run's shoppers (top spenders, left empty-handed, impulse
  buys, longest visits) or search, open one, and see their trip step by step — wall-clock time,
  shelf, product, impulse or planned, and the thought recorded at each step — with the walked path
  and numbered stops on a floor map. **Follow in 3D** jumps playback to their arrival and highlights them.
- Each first stop at a stocked shelf face shows **what the shopper saw** there (the vision shoppers'
  renderer of that face at run time); click to enlarge. API: `GET .../runs/{run}/racks/{rack}/faces/{face}.png`.
- **Interview**: ask that shopper why ("why didn't you buy anything at Snacks 1?"). A language model
  answers in the first person from the persona, the trip and the shelves they stopped at only, says
  so when they did not notice something, and cites the steps it means (hover to highlight them).
  Suggested questions come from the trip. Transcripts are kept per run.
- **Group interview**: one question to many shoppers at once — everyone who left empty-handed,
  impulse buyers, top spenders, buyers or a random sample (4–40). Each answers from their own trip;
  the answers are then coded into two to six themes, with counts computed from per-answer
  assignments (misnumbered answers go to "Other"). Click an answer to open that shopper.
  API: `POST/GET .../runs/{run}/group-interviews`, `DELETE .../group-interviews/{id}`.
  API: `GET .../runs/{run}/shoppers/{id}/journey`, `GET/POST/DELETE .../shoppers/{id}/interview`.

### Photo mode (path-traced stills)
- In the first-person shopper view, **DoF** traces through a physical camera focused on whatever sits
  at the centre of the frame (f/1.4, f/2.8, f/5.6), for a photographic depth of field.
- In the realistic 3D view, **Photo** path-traces the current view with three-gpu-pathtracer:
  global illumination, area-light shadows from the ceiling panels, a glossy floor, real glass and
  daylight through the storefront. It refines sample by sample (64 / 256 / 1024) and saves a PNG;
  orbiting or zooming restarts it. The live scene is copied into a static one the path tracer can
  read: instanced packages baked with their label UVs, shader-patched materials replaced by plain PBR,
  the contact-shadow decal dropped, the BVH built in a worker.

### Marketing studio
- **Field POS reconciliation**: preview anonymous transaction/SKU rows against saved field assignments, distinguish
  positive evidence, conflicts and missing links, and send proposed purchases through the existing reviewed import.
  Duplicate item rows and transactions shared by assignments are rejected within a file. No automatic nonpurchase
  imputation, enrollment changes or overwriting of known outcomes; no model calls or raw POS persistence.
- **Field collection checks**: default pilot monitoring view with staff/shift and A/B completeness denominators,
  recording-gap checks, unrecorded-tail counts and a filtered, paginated follow-up checklist. JSON and CSV contain
  outcome availability rather than purchase values. Imports and closure refresh the checklist; older and locked
  pilots are supported. No significance tests or automatic outcome imputation.
- **Observation import review and history**: full-sheet change previews, explicit reasons and confirmation,
  file/revision-bound application, and retained before/after records with CSV export. Known-value clearing,
  enrollment removal and purchase reversals are flagged. Unchanged sheets do not create revisions; older pilots
  disclose missing historical coverage. API imports now require a preview token and reason.
- **Field pilot sample planning**: conservative power bounds aligned with the final 95% Hoeffding interval,
  required encounters and operating days, explicit capacity shortfalls, and optional even allocation across
  existing staff/shift blocks. Assumptions and a server-calculated assessment are saved with each new plan;
  existing pilots remain fixed. No model calls or real-sales forecasts.
- **Observed field pilots**: fixed staff/shift A/B assignment sheets from saved scripts, full-sheet CSV imports,
  immutable stimulus snapshots, intention-to-treat purchase counts, missingness bounds, versioned atomic updates,
  and locked closure. Complete targets receive a conservative fixed-sample conversion interval; unfinished targets
  stay descriptive. The independent Field pilots tab retains results after deletion of a source screening job.
- **Field pilot sensitivity checks**: post-closure staff, shift and block deletion diagnostics with planned-count
  weighting, exact-zero handling, unavailable comparisons and a revision-bound CSV export. Fully completed
  fixed plans are required; no outcome imputation, interim testing or additional significance claims.
- **Staff-script cost scenarios**: apply explicit per-buyer contribution, per-assignment staff time, hourly labor
  cost and daily eligible traffic to a completed, locked pilot. Show break-even conversion difference and
  conditional contribution ranges with snapshot CSV export; no inferred costs or realized-profit claims.
- New **Market** page (`/marketing/<project>`) for marketers and research agencies, with eight tabs: A/B tests,
  shelf tests, concept tests, conjoint, staff scripts, field pilots, inventory and products.
- **Staff scripts**: independent A/B exposures on the same synthetic personas, with purchase intent,
  trust and pressure ratings, complete-pair bootstrap intervals, exploratory segments and customer replies.
  Saved product/persona snapshots and exact-script CSV support review; missing responses, restart recovery
  and conservative screening recommendations are explicit. API: `POST/GET /api/projects/{pid}/staff-pitches`,
  `GET/DELETE .../{id}`, `.../{id}/export.csv`. This is wording screening, not a real sales-effect estimate.
- **Products**: a product image library (multi-file drop, background cut-out, name, brand, linked shelf
  SKU, rename, delete), shared with Shelf Lab. The vision shoppers' shelf renderer draws a linked
  image instead of the plain package.
- **A/B tests**: variants of a saved layout — price, discount with a was-price tag, promotion sign,
  move to a fixture / shelf level, new pack, category price with .99 endings — plus one-click recipes.
  All arms run on the same persona panel and seed (common random numbers); store and focus-product
  outcomes come with paired bootstrap 95 % intervals, a winner only when the interval clears zero,
  and CSV export. API: `POST/GET /api/projects/{pid}/experiments`, `GET/DELETE .../{eid}`.
- **Price sweep**: a one-click recipe tests a product at −30 %, −15 %, +15 % and +30 % with the current
  price kept as the shoppers' reference (`keep_reference`), and the result shows its demand curve —
  units per 100 visitors with 95 % intervals at each price, product revenue, the elasticity across the
  arms and the revenue-maximising tested price (in the app and the report). Rule shoppers react to
  price relative to the usual price, so a new everyday price without a reference gets a note.
- **Duplicate and edit**: open any finished A/B or concept test as a pre-filled new one.
- **By segment**: every A/B variant also reports its paired difference to control within each age
  group and gender (20+ shoppers) for revenue per visitor and tracked-product units, with 95 %
  intervals, in the app and the report.
- **Automatic report** for every finished A/B test: a summary with a rule-based recommendation
  (roll out the winner with its daily and monthly revenue range, flag variants that lose, call out
  product-only lifts, the panel size needed to see a 5 % change), the test design, results with
  paired 95 % intervals and charts, tracked products, best sellers per arm, method and caveats.
  One self-contained, print-ready HTML page (print to PDF) and Markdown; a model can add a labelled
  commentary written from the report's numbers. API: `GET .../experiments/{eid}/report.html|.md`,
  `POST/DELETE .../experiments/{eid}/narrative`.
- **Shelf tests** (virtual shelf impact test): pick a shelf and a product, give it a new pack, price
  or sign, and preview both shelves live. The same respondents see the control and the test shelf
  through a vision model (badge numbers shuffled per respondent), pick the one product they would take
  and name what caught their eye first. Results: the product's pick share, noticed in the top three
  and noticed first, control vs test with paired 95 % intervals; what everyone took; why. API:
  `POST/GET .../shelf-tests`, `POST .../shelf-tests/preview`, `GET/DELETE .../shelf-tests/{id}`,
  `GET .../shelf-tests/{id}/{control|test}.png`; a print-ready report at `.../shelf-tests/{id}/report.html`.
- **Concept tests**: personas (with age / gender quotas) answer purchase intent, appeal, value,
  stand-out, Van Westendorp price and preference questions about up to four images through a vision
  model; Likert summaries, Wilson shares, price-sensitivity curves, segments, verbatims, CSV export,
  and a print-ready report (board, summary, answer distributions, price curves, segments, method).
  API: `POST/GET /api/projects/{pid}/surveys`, `GET/DELETE .../{sid}`, `.../board.jpg`, `.../export.csv`.

### One icon, every OS
- `launcher/`: one Go source → `TwinStore.exe` (Windows, icon embedded, no console window),
  `TwinStore.app` (macOS universal, app files inside the bundle) and `twinstore` (Linux, adds
  itself to the app menu). Double-click → a live boot screen at `127.0.0.1:8000` → the app at the
  same address. uv is fetched into the launcher's own folder when missing; a second click reopens
  the running app; ⌘K → **Quit TwinStore** stops everything.
- Release workflow builds one archive per OS and smoke-tests the packaged Linux launcher.

### Works without an API key
- With no cloud key set, a notice under the command bar says so, and the Models page shows what
  this computer is (CPU, cores, memory, GPU) and which local vision model it gets.
- `application/hardware.py` reads the hardware (NVIDIA via `nvidia-smi`, AMD/Intel via sysfs or
  WMI, Apple silicon unified memory) and picks the largest model that runs at a usable speed:
  - Qwen3.5-9B / 4B / 2B on a GPU (85 % of VRAM; 45 % of unified memory on a Mac);
  - Qwen3.5-2B, 0.8B or LFM2.5-VL-450M on a CPU, by cores and free memory.
- `application/local_vlm.py` downloads the matching llama.cpp build (CUDA for the driver's CUDA
  version, Metal, Vulkan or CPU) and the model, starts `llama-server` on 127.0.0.1, falls back to
  the CPU build if a GPU build does not start, and points the `llamacpp` provider at it.
- Launched from an app icon, this starts on its own (`TWINSTORE_LOCAL_VLM_AUTO=1`); otherwise one
  click on the notice or the Models page. `TWINSTORE_LOCAL_VLM=off`, `TWINSTORE_LLAMA_SERVER` and
  `TWINSTORE_LOCAL_VLM_MODEL` override it. API: `GET /api/system/models`,
  `POST /api/system/local-model/start|stop`.

### Situations
- Supermarkets, grocers and drugstores now use a **grocery profile** fitted to measured situation
  effects (`engine/grocery_priors.json`, `priors_for(store.type)`); convenience stores keep the old priors.
- Shoppers whose needs come from their history draw them scaled by the measured ratio of the
  situation (`ScenarioPriors.need_ratio`): more beer and snacks on a match day, more water in summer.
- **Time of day**: per-shopper part-of-day demand and needs by arrival hour
  (`ScenarioPriors.hour_demand`, `need_ratio["hour:evening"]`); no scenario needed.
- The scenario layer no longer files frozen pizza, cream cheese and candy bars under ice cream.

### Shopper behaviour
- Time at the shelf is lognormal (`RuleBasedConfig.shelf_time_median_sec`), on its own random stream so baskets do not
  change; a pick right after a look is no longer floored again by the rack minimum, and new racks
  start at a 2 s minimum.
- Each needed category names the household's usual products there, which raises repeat purchases.

### Shelf Lab — real photos as experiments
- Budgeted restocking quantities: verified stockroom counts, whole supplier packs, explicit priority,
  pack availability and a single delivery fee. The audit-linked API, worksheet UI and CSV export show
  unfilled demand, surplus, costs and constraints without placing orders or estimating sales recovery.
- Counterfactual edits on shelf photos (swap, stock-out, new package, price tag, promotion) with
  exact ground-truth masks: pixels outside the changed boxes are untouched.
- Sim2real: the same personas and seeds on the render, the tagged photo and the raw photo;
  decision agreement with confidence intervals, attention by shelf level, interest rank agreement.
- Compliance audit against the layout's reference face; stock-outs priced in revenue per day by
  paired simulation. Benchmark generator (`lab_cli bench`) and lever experiments.
- Rival shelf comparison: price index, assortment overlap, the rival's price-adjusted pull.
- Photoreal shelf studio (`frontend/studio.html`): a gondola bay rendered with Realistic mode's
  packages and a phone-photo finish, with exact facing boxes, so Shelf Lab can be shown and
  benchmarked on photo-like shelves. Edits now match light by the bright end of the surrounding ring
  (shelf edges, tags), so neighbouring products no longer tint swapped or refilled pixels.

### Photos in, twin out
- Floor-plan images (sketch, scan, PDF page) → walls, racks and doors on the grid, or read by a
  vision model.
- Storefront photos → appeal score → the venue's pull in the neighborhood model.
- Receipt photos → POS lines matched to the store's products → fidelity report.

### A new interface
- Aurora design system (Geist, Instrument Serif), command bar and ⌘K palette, redesigned home,
  workspace, wizard, neighborhood, capture and settings pages; photoreal 3D by default with a
  store environment map and lens effects; the playback bar folds away in the shopper's-eye view.

### Docs
- README rewritten around the twin, with system, vision-shopper, Shelf Lab, validation and
  launcher figures and a short film, all generated from HTML in `.github/assets/src`.
- License: TwinStore License 1.0 — free for research and non-commercial use, free for
  organizations with annual revenue up to US$1M, a separate license otherwise. The Parastore MIT
  notice is kept in full.

## 0.3.0 — vision shoppers in a living neighborhood

v0.2 made the simulator an experiment tool. v0.3 widens what can be simulated and
who decides: vision-language shoppers now make every in-store decision (whether
to go in, what they came for, what catches their eye), on any model you connect
or an ensemble of them, in a store you can generate from ten retail formats, on a
day you describe, in a neighborhood you generate or import — and the same
shoppers judge layout optimizations and the value of the shop next door.

### Vision shoppers decide end to end
- **Planning at the door** (`plan_policy="vlm"`, default for vision runs): the
  shopper sees a rendered store directory map, reads today's situation and where
  it came from, and decides whether to enter and what to buy; items resolve to
  SKUs by name, then category. Scenario demand multipliers are not applied on
  top (no double counting); arrivals and budgets still come from the scenario.
- **Impulse picks at the shelves** as before (rendered faces, interest 0–10,
  seeded purchase draw), now with the plan in the shopper's basket context.
- **Models**: OpenAI, Anthropic, Google Gemini, Alibaba Cloud Qwen (Model
  Studio), OpenRouter, vLLM, Ollama, llama.cpp and any OpenAI-compatible
  endpoint; keys entered in Settings are stored only on the machine running the
  backend. Connection tests for text and vision.
- **Ensembles** of models as one population: *mixture* (each shopper is one
  model, weighted) or *vote* (every model looks at each shelf, majority wins).

### Situations
19 presets (heatwave weekend, typhoon, fine dust, payday Friday, exam week,
local festival, competitor opening, 1+1 drinks, supply disruption, lunch rush, …)
and an editor for weather, season, day type, events, promotions, stock-outs,
crowding and hourly traffic. Vision shoppers read the situation; the rule model
applies it as calibrated multipliers.

### Neighborhoods
Procedural towns (residential, university, business district, station area,
suburban, tourist, mixed) or a real OpenStreetMap area: homes, offices, schools,
stations, rival stores and other venues. Huff-style demand gives visitors per
hour, catchment and walking distance; runs can draw their visitors from the
town, each shopper knowing where it came from. Synergy: the numeric effect of
every venue on our visitors, plus a **vision check** that simulates the affected
visitors with and without the venue to measure the basket effect.

### Layout optimization
Hill climbing, simulated annealing or a genetic search over planograms and rack
positions, scored on a fixed shopper panel with common random numbers and
re-checked on fresh shoppers. **Vision judge**: the rule model proposes, VLM
shoppers walk the top candidates on one paired panel and pick the winner, after
an optional calibration of the rule model to a VLM pilot; the report shows rule
vs vision ranks, paired deltas with intervals and P(better). Jobs can be stopped.

### Stores and graphics
- Ten store formats generated as complete layouts with priced products (urban
  and compact convenience stores, campus store, station kiosk, gas station,
  drugstore, mini-mart, café-bakery, office lobby, tourist shop), in English/$ or
  Korean/₩, parallel aisles or racetrack loop.
- **Realistic 3D mode**: gondolas with price channels, glass-door coolers, chest
  freezers, counter with POS, glass storefront, instanced products with
  generated packaging and labels, soft shadows, optional GTAO/bloom/reflections.
- **Shopper view**: an eye-height camera that follows one shopper.

### Interface
A new interface with day and night themes, a navigation rail, a home screen with
an animated store, glass controls over the 3D view, and larger type throughout.

### Calibrated against real purchases
What a comparison with real trips exposed was fixed in the simulator:
- **Visit times from data**: a weekday × hour traffic profile fitted from
  transaction times (`engine/generators/traffic_profile.py`). A POS export with a
  timestamp column uploaded as supplemental data now sets when personas arrive;
  asked directly, models put most visits on a few stereotyped hours.
- **Supermarket-sized trips**: store-kind-aware prompts, plans of up to 30 items,
  `basket_scale`, products per category, multi-unit purchases, priority-ordered
  shopping lists, and `Persona.basket_size` (a trip of known size) honored by
  both planners.
- **Long plans no longer fall back silently**: plan token budgets scale with the
  list length, with one retry on a cut-off answer.
- **Model Studio regions**: `DASHSCOPE_API_BASE` (or Settings) selects the
  region or workspace endpoint; Qwen's reasoning mode is switched off for shopper
  decisions.
- **Walking**: 1.04 s per tile, diagonal steps without corner cutting, per-shopper pace
  (lognormal, sd 0.3); time runs in fractional seconds.
- **Prices shoppers can react to**: `SlotItem.regular_price` (a sale shows as
  "$2.39 (was $2.99)" on the shelf tag), every product's price in the vision
  planner's store directory (`directory_prices`), and a constant-elasticity
  price factor in the rule planner (`price_elasticity`, default −1.8). Before,
  neither engine responded to a 20 % price change.
- **Trips that vary like real ones**: `Persona.category_rates` (share of past
  trips with each category; on each trip a seeded draw decides which of them the
  household has run out of, and the vision planner is told) and
  `Persona.basket_kinds` (categories on the same past receipt; the planner keeps
  the model's first K categories and fills the trip within them). Asked for one
  trip, models otherwise bought every staple every time and spread six items over
  six categories.
- **Product choice**: the store directory lists every product of a category in a
  random order per shopper; `Persona.usual_products` and `habit_prob` for repeat
  purchases, shown to vision planners and used by the rule planner.
- **Newer OpenAI models** (GPT-6): `max_tokens` is renamed to
  `max_completion_tokens` and unsupported sampling values are dropped, learned
  from the provider's error and retried. Reasoning is switched off for shopper
  decisions (`reasoning_effort: none`): with it on, reasoning tokens used up the
  glance budget and 90 % of GPT-6 Luna's shelf glances failed. A cut-off glance
  is retried once with twice the budget, and validation runs report glance
  errors next to plan fallbacks.

### Getting started
Double-click `Parastore-Windows.bat`, `Parastore-macOS.command` or
`Parastore-Linux.sh`: the launcher installs what it needs, builds the interface
once and opens the app in the browser (see QUICKSTART.md).

## 0.2.0 — what changed and why

v0.1 produced plausible-looking shopper animations, but its numbers could not
support a decision: runs were not reproducible, two layouts were never compared
on equal terms, exposure ("what the shopper saw") was not computed on the route
actually walked, and baskets had no quantities, budgets or planned/impulse
distinction. v0.2 turns
the simulator into an experiment tool: every output is reproducible, paired
comparisons come with confidence intervals, and results can be scored against
real point-of-sale data.

All defaults changed by v0.2 can be switched back (see *Compatibility*).

### 1. Reproducibility and paired experiments

| Before | After |
|---|---|
| Per-customer mood/company cues drawn from an unseeded `random.Random()` | Every random stream (cue, arrival minute, timeline glances, engine seed) is derived from `(seed, replicate, persona id)` via `stable_seed` |
| Persona generation seeded the *global* `random` module while days ran concurrently | Local per-day streams |
| Two layouts saw different random customers | Same seed ⇒ same customers in the same states on every layout (**common random numbers**) |
| LLM calls not seeded, not cached | Optional per-call seed (`LLMConfig.seed`) and a content-addressed response cache (`LLMConfig.cache_dir`) |
| Failed customers silently dropped | Recorded with reasons in `diagnostics.json`, surfaced in the UI |

Each run now writes `output/manifest.json` (engine, model, seed, replicate,
exposure/ordering modes, layout and persona fingerprints, package version) and
`output/diagnostics.json` (failures, dropped hallucinated / over-budget buys,
buy-placement invariant violations).

### 2. Simulation correctness

- **Exposure on the walked route.** Stage-3 impulse candidates used to be
  computed on the stage-2 path *before* visits were re-ordered, i.e. on a route
  the shopper never walked. Exposure is now computed on the final route.
- **Visibility exposure model** (`exposure_model="visibility"`, default). A slot
  is visible from a path tile in front of its face, within `view_distance` tiles,
  inside a 45° cone, with clear line of sight. Score = shelf-level attention ×
  distance falloff; several facings of one SKU combine as 1 − Π(1 − v). The
  opposite face of a rack the shopper never walks past is not seen. Parameters
  live in `PerceptionConfig` and are explicit priors meant to be calibrated.
- **Planned ordering** (`route_ordering="planned"`, default). The shopper's own
  visit order is kept; impulse visits are grouped per rack and inserted at the
  cheapest detour. The legacy greedy nearest-neighbor re-ordering remains
  available as `"nearest"`.
- **Quantities and origins.** BUY lines carry `quantity`; `total_spent` is
  Σ price × quantity. BROWSE/BUY events carry `origin` = `planned` | `impulse`,
  so unplanned-purchase share is measurable.
- **No forced purchases.** Prompts state explicitly that leaving without buying
  is a valid outcome for patterns that allow it; impulse buys beyond
  `budget_max × budget_tolerance` are dropped (planned buys never are).
- **Currency.** `SimulationConfig.currency` (ISO 4217). Prompts describe prices in
  the right unit (e.g. KRW integers are won, not cents) and the UI formats money
  accordingly.

### 3. Engines

- `pattern_intent_impulse` (LLM): stage-2 prompt split into a static per-store
  system prefix (rules + compact catalog) and a short per-customer suffix. On the
  sample store the stage-2 call went from ~8,560 to ~7,090 tokens, of which
  ~6,760 are a prefix shared by every customer — so with provider/server prefix
  caching only ~330 tokens per call are new.
- `rule_based` (new, no LLM): calibratable heuristic shoppers
  (`RuleBasedConfig`) — pattern draw, category-matched planned purchases, and
  visibility-driven impulse buys and browse-only stops. 2,440 customers in ~7 s
  on 2 CPU cores. Use it for instant layout previews, as a research baseline,
  and for deterministic tests.

- `vlm_glance` (new, vision-language shoppers): the rule-based planner decides
  the planned visits; impulse decisions come from a VLM that is shown a rendered
  image of each well-seen rack face along the route (`engine/perception`: names,
  price tags, promotion ribbons, numbered badges, randomized numbering). The
  model answers as the persona (mood, basket, money left) with a
  schema-constrained JSON reply naming the most tempting product and an
  interest score 0–10; answers are mapped back by printed name first and badge
  number second. A seeded per-face draw turns the score into a buy
  (`buy_scale` × interest/10 × shelf-level weight), a look, or nothing, so small
  models' tendency to always say "buy" cannot set the purchase rate. Runs on a
  CPU with a small local model served by llama.cpp
  (`structured_output="json_schema"` turns the schema into a grammar, so even
  sub-1B models answer validly). Every glance is saved to
  `output/vlm_glance_meta.json` and summarized in the dashboard.
  Measured on 2 vCPUs (same 30 customers, seed 1, 41 identical glances):
  Qwen3.5-0.8B ≈ 9.5 s/glance, Qwen3.5-2B ≈ 22.5 s/glance, no failed or
  hallucinated answers; the two models picked the same product in 32% of
  glances, and the 2B model put 71% of its picks in the top shelf row (54% in
  the left column) — a reading-order bias to calibrate or study, not a shopper
  fact. Reading probe (name / price of a numbered product, 16 shelves):
  0.8B 63% / 69% at 640 px, 2B 94% / 100% at 512 px. Planner and impulse step of `RuleBasedEngine`
  are now separate methods (results unchanged) so engines can swap only the
  impulse step.

### 4. Analytics

`summary.json` keeps every v0.1 field and adds: buyers, conversion rate, units
sold, units per buyer, basket value, revenue per visitor, impulse revenue/unit
share, average visit time and path length, per-product and per-rack stats
(visitors, browsers, buyers, units, revenue), per-segment stats (age, gender,
purpose, identity) and hourly arrivals. `dwell_heatmap.json` holds seconds spent
per tile (the legacy `persona_heatmap` counts events).

- **Paired comparison** (`engine/analysis/compare.py`): per-customer metrics
  matched by persona; percentile bootstrap CI of B − A, P(B > A), and the number
  of customers needed to detect a 5% change.
- **Fidelity vs POS** (`engine/analysis/fidelity.py`): SKU and rack Spearman,
  JS similarity, NDCG@k, basket-size/value Wasserstein distances, mean and
  variance ratios (variance compression), hourly profile similarity. POS columns
  are matched by common aliases (`receipt_id`/`basket_id`, `sku`/`product_id`,
  `qty`, `unit_price`/`sales_value`, `timestamp`/`hour`, …).

### 5. API additions

| Endpoint | Purpose |
|---|---|
| `POST /api/projects/{pid}/runs` | now accepts `engine_type`, `seed`, `replicate`, `exposure_model`, `route_ordering`, `max_customers`, `preview` |
| `GET /api/engines` | engines with the server defaults |
| `GET /api/projects/{pid}/runs/{rid}/status` | adds `completed_customers`, `failed_customers`, `started_at` (live progress) |
| `GET /api/projects/{pid}/runs/{rid}/diagnostics` | diagnostics + manifest + token usage |
| `GET /api/projects/{pid}/compare?a=&b=` | paired A/B report |
| `POST /api/projects/{pid}/runs/{rid}/fidelity` | upload a POS CSV/XLSX, get the fidelity report |
| `GET /api/projects/{pid}/runs/{rid}/export.csv` | one row per simulated customer |
| `GET /api/projects/{pid}/runs/{rid}/heatmap` | adds `dwell_heatmap` |

**Preview runs** (`preview: true`) do not lock the setup and are allowed on
draft and finalized setups, so a layout can be iterated on and finalized layouts
can be re-run with other engines/seeds.

### 6. Headless CLI

```bash
cd backend
uv run parastore simulate --run sample_data/proj_67916afd/runs/run_ab0039 --engine rule_based --replicates 3 --out /tmp/runs/A
uv run parastore ab --store-a a.json --store-b b.json --personas personas.json --engine rule_based --out /tmp/ab
uv run parastore compare /tmp/ab/A/rep_0 /tmp/ab/B/rep_0
uv run parastore fidelity /tmp/runs/A/rep_0 pos_export.csv
uv run parastore summary /tmp/runs/A/rep_0
```

Run directories use the same layout as server runs.

### 7. Configuration via environment

| Variable | Field |
|---|---|
| `PARASTORE_LLM_MODEL` | LiteLLM model id, e.g. `anthropic/claude-sonnet-5-5`, `openai/local` |
| `PARASTORE_LLM_API_BASE` | OpenAI-compatible endpoint (vLLM, llama.cpp server, gateways) |
| `PARASTORE_LLM_TEMPERATURE`, `PARASTORE_LLM_MAX_TOKENS`, `PARASTORE_LLM_TIMEOUT_SEC` | sampling / limits |
| `PARASTORE_LLM_SEED` | enables per-call seeds |
| `PARASTORE_LLM_CACHE_DIR` | enables the response cache |
| `PARASTORE_ENGINE` | default engine (`pattern_intent_impulse` / `rule_based`) |
| `PARASTORE_SEED` | default run seed |
| `PARASTORE_CURRENCY` | ISO 4217 currency of prices |
| `PARASTORE_EXPOSURE_MODEL`, `PARASTORE_ROUTE_ORDERING` | `visibility`/`adjacency`, `planned`/`nearest` |
| `PARASTORE_BUDGET_TOLERANCE` | float, or `none` to disable |

### 8. UI

- Run launcher: engine (instant rule-based preview or LLM shoppers), customer
  sample, seed, replicate, preview vs final, LLM call estimate.
- Live progress (customers done, elapsed, remaining, failures); failed runs
  return to the previous view with the error shown inline.
- Playback toolbar: switch between runs of a layout, run again, compare, CSV
  export, back to editing (draft layouts list their previous runs).
- Compare dialog: paired bootstrap intervals as a forest plot, P(B > A), sample
  size hints, warnings when seeds or engines differ.
- Run KPI tiles, segment breakdown, diagnostics panel, POS validation upload.
- Heatmap layers — footfall, dwell time, predicted traffic — with color ramps
  and legend; 3D rack KPI overlay (revenue-intensity pads and labels).
- Quantity- and impulse-aware live metrics; currency-aware formatting.

### 9. Performance

A* results are memoized per (grid, start, end), rack access-tile geometry is
memoized per geometry key, and the rule engine tokenizes the catalog once per
run: same outputs, ~2.3× faster end to end on the sample store.

### Compatibility

- Old runs still load: new summary fields are optional in the UI; missing dwell
  heatmaps / rack stats disable the corresponding toggles.
- Behavior changes, each reversible: `exposure_model="adjacency"`,
  `route_ordering="nearest"`, `budget_tolerance=None`.
- `TimelineEvent.price` stays the unit price, so v0.1 consumers keep working;
  multiply by `quantity` for line totals.

## 0.1.0

Initial public release.
