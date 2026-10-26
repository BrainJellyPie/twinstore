# Full automatic stocking with a fresh native-schema CPU run

The complete 32×26 hypermarket setup passed with the actual Qwen3.5-2B
Q4_K_M model on CPU, without copying any application response cache. The
run used llama.cpp b11878, five CPU threads, no GPU and an 8,192-token
context. The template used KRW, one product per category and an explicit
alcohol exclusion. This is text-based automatic stocking with a vision-capable
model, not an image or shopper-decision benchmark.

Results from
`/workspace/scratch/cpu-vlm-probe-2b/native-hypermarket-fresh-082/hypermarket-json_schema-1793011573135363937`:

- **198 rack assignments**, all unique and valid.
- **44 categories and 44 selected SKUs**, with all 44 SKUs actually placed.
- **1,772 placement entries** checked against their exact catalog item,
  price and currency; no category exclusions or per-category limits violated.
- No source-store mutation and no layout validation issues.
- **Nine real HTTP requests, zero application cache hits**. Captured requests
  confirm `json_schema` on the wire, not just in the case name or config.
- The category request succeeded. Two oversized whole-catalog product
  requests returned HTTP 400 context errors; six bounded product requests
  then succeeded and completed the same setup without exposing a partial store.
- Elapsed time was **203.60 s**. Reported usage was 23,338 prompt and 1,317
  completion tokens. Server prompt-prefix reuse is possible; elapsed time
  is not a controlled speed comparison.

The probe ran from post-release checkpoint `176c81b0`. Its starter selection
and template-assortment implementation are identical to release candidate
`2a0959fa`; the separate capture/package follow-ups do not change this path.
This supplies a complete fresh native-schema run, supplementing the earlier
plain-JSON product-batch run that reused a previously obtained category reply.
These checks establish structural/catalog correctness for this case, not
universal semantic quality for all generated assortments.
