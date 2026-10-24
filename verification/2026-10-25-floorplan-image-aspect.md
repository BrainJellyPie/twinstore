# Preserve the physical proportions of unscaled VLM plans

Image coordinates normalize both axes to 0–1000. Inferring metres from those
fractions alone lost the image's aspect ratio: both 800×400 and 400×800 plans
with the same normalized outline became 12×12 m, 10×10-tile stores.

Use the dimensions returned by image encoding to recover the outline's pixel
proportions before assigning the existing 12 m long-side estimate. These are
the dimensions the model saw, including EXIF orientation and resizing. Keep
positive very thin extents when rounding to centimetres would produce zero.
Written width and depth still override estimation; fixture normalization,
partial-scale fallback and the grid's existing size bounds are unchanged.

Twenty-six scripted HTTP cases exercise both JSON modes, wide/tall/square
images, cropped outlines, EXIF rotations, resizing, explicit and partial scales,
thin images, valid stocked layouts and response-cache reuse. Twenty failures
were reproduced before the change; six controls passed in 2.82 seconds.

After the fix, 100 focused image, geometry, classic/PDF reader, API and
persistence tests passed in 8.43 seconds. Pyright reported zero errors and
warnings. The 26 pytest warnings are existing LiteLLM async logging cleanup
warnings. No real model inference or model download was used.
