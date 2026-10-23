# Stable visual inputs for marketing studies

Shelf panels and vision A/B studies previously kept layout objects but read product
images from mutable source paths later. Deleting an uploaded package could silently
replace the treatment with a generic image; replacing or adding a SKU photo could
change either arm after the study had been accepted. Shelf evidence and respondents
also constructed separate loaders, so they could show different images.

The startup transaction now captures resolved images, including absent images, in
the job's `images` folder. All arms, shelf evidence and respondents use that snapshot.
Copies are decoded through a bounded cache; eviction reads the saved copy instead of
the source. SKU writes share their existing project image lock with capture, while
the existing project tree guard coordinates package deletion. A failed image snapshot
removes its pending job before any background work is submitted. Rule experiments
do not copy images; interactive previews still show current art.

Validation used temporary projects and fake model/evaluator responses, with no live
provider calls:

- Six shelf regressions failed before the change: queued or rendering-time mutation,
  each with package deletion, SKU overwrite or a newly added photo.
- Three vision A/B regressions failed before the change. Their first test draft used
  an invalid panel size of 10; after correcting it to the API minimum of 20, all three
  reached completion and exposed changed image pixels.
- The focused image, shelf-integrity, experiment-start and SKU-storage tests passed:
  **58 passed in 9.71 seconds**. This includes 131 distinct images for one SKU,
  cache eviction, absent-image freezing, duplicate references and disk-write failure.
- Two additional concurrent SKU overwrite/snapshot orderings passed in **3.31 seconds**.
- Strict Pyright for the three changed application modules: **0 errors**.

Logs: `/workspace/scratch/marketing-images-{before,experiment-before,after,types,overlap}.log`.
The saved images add disk usage to each visual study and are removed with that study.
This change does not retrofit images for previously accepted jobs or alter ordinary
simulation image loading.
