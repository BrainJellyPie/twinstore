# Reduce peak memory when exporting long visits as GIFs

GIF export retained every decoded full-size RGB screenshot and every resized
RGB copy, in addition to the indexed GIF frames. A visit can have many tall
pages, so this multiplied memory use before encoding even began.

The renderer now reads image dimensions without decoding all pages, then
decodes, scales, captions and quantizes one page at a time, explicitly releasing
its RGB working images. The indexed output frames still remain until GIF
encoding completes; this is not constant-memory streaming of the final file.

In isolated processes, eight 1024×6000 screenshots peaked at 479.5 MiB before
the change and 246.9 MiB afterward (startup/preparation peaks 93.4/93.5 MiB).
Export took 2.14/2.13 seconds and both outputs were 36,411 bytes. These numbers
describe that controlled workload, not a universal memory limit.

Two new multi-frame retention checks failed before repair; both single-frame
controls passed. Tests track live full-size RGB images and verify desktop/mobile
dimensions, padding, frame count, colors, loop mode and the longer final frame.
Six focused renderer/GIF/playback API tests passed in 11.56 seconds. Full-source
Pyright reported zero errors and warnings; backend boot passed. No frontend
runtime, inference or model downloads changed.
