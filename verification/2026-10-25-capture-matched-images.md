# Connect applied photo crops to the placed product SKU

Applying a capture could match its product to an existing store SKU while
saving the photo crop under the original temporary capture SKU. The saved
layout then referenced a product with no uploaded picture, while an unused
SKU held the crop. The batch-preview path already resolved identities for
images; direct single/multiple-capture application did not.

Before saving crops, direct application now resolves each captured item
against the resulting layout with the same exact-name policy. New products
keep their captured SKU, and existing SKU images are still preserved by the
image-storage path.

All eight new API cases failed before the fix. The focused application,
batch, crop-boundary and currency suites now pass 84 checks in 7.99 seconds.
Full-source Pyright reports zero errors and warnings. Cases cover replacement
and new racks, complete names and separate brand/size fields, absent and
already-saved images, and repeated application. They verify saved SKU keys,
decoded crop colors through the actual model-image loader, image HTTP reads,
stable image metadata, and unchanged source layout/capture bytes. Both a
matched existing product and an unrelated new product are present.

Images are generated test fixtures. No model inference, downloaded weights,
external photo service or paid calls were used.
