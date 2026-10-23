# Coherent shelf photographs for photo-chart runs

Photo-chart runs still read the project's mutable photo cache after admission. A
later upload changed queued/running customers' photos and product boxes, including
adding a previously absent photo. Concurrent uploads could leave one upload's JPEG
with another's boxes. Uploads also raced with project deletion.

Shelf uploads now hold the project tree and setup guards through validation and
saving both files. Vision admission copies complete matching JPEG/JSON pairs into
`input/shelf_views` under the same tree guard, records a manifest and points its
worker at that private directory. Absent or incomplete pairs remain absent. A lost
snapshot manifest fails before simulation instead of reading current project photos.
Failed copies clean their partial run before status/layout transitions.

Another boundary appeared between layout URL hydration and image copying: a SKU
overwrite could leave an old photo key paired with new product pixels. The existing
SKU image mutex is now reentrant, letting vision admission hold it across layout
reading and both snapshots while the nested product-image snapshot reuses it. Rule
admission retains its previous independent locking and does not copy photographs.

Validation used fake vision entry points, rule simulation and temporary local files:

- Before: ten photo mutation/upload/deletion cases failed in 12.41 seconds; a
  separate SKU overwrite/input capture case failed in 6.83 seconds.
- After: 18 focused photo/API/engine cases passed in 20.22 seconds.
- Seven additional cases passed in 10.79 seconds: startup during an upload, copy
  failure, lost snapshot, either half of an incomplete photo pair, and both existing
  SKU writer/snapshot orderings.
- Three selected concurrent run-ID cases passed in 8.75 seconds, covering same ID,
  another ID and another project with vision admission.
- Strict Pyright for all four changed modules: zero errors or warnings.

Only photos matching the accepted layout are copied. A later scenario/layout change
whose face key has no matching photo continues to use the existing chart fallback.
