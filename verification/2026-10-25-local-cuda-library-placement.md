# Put CUDA companion libraries where the executable can load them

The pinned [llama.cpp b11870 release workflow](https://github.com/ggml-org/llama.cpp/blob/b11870/.github/workflows/release.yml)
builds Linux binaries with RPATH=$ORIGIN and packages the server under
llama-b11870/, while its CUDA companion libraries have a separate
cudart-llama-b11870-bin-ubuntu-cuda-13.4-x64/ wrapper. TwinStore extracted
both archives into the same parent directory but did not bring their
contents together. The loader could not find the bundled libraries beside
the executable. The earlier platform-selection tests used flat archives
and did not exercise this upstream wrapper structure.

CUDA installation now moves bundled cudart/cublas libraries beside the found
server, preserving existing destination files. The same repair runs when
reusing a managed installation, including legacy installations without a
completion marker. No redownload is needed for this directory repair.
Non-CUDA runtimes and an explicitly supplied custom server retain their paths.

Twenty-six new checks failed before the change and twelve flat-layout controls
passed. A compiled Linux fixture with a shared library named libcudart.so.13
and an executable using RPATH=$ORIGIN reproduced an actual loader failure:
exit 127, cannot open shared object file. Fresh and cached installations now
run that executable successfully with LD_LIBRARY_PATH removed.

The focused run passed 133 checks and exposed one old test that required CUDA
libraries to remain in their unusable parent directory. Its expectation now
requires the same bytes beside the server; its three backend cases pass.
There are 134 distinct passing focused checks, and full-source Pyright reports
zero errors and warnings. Cases cover Windows/Linux names, x64/ARM64 assets,
flat/separate/nested layouts, fresh/marked/legacy caches and offline reuse.

The native fixture contains only tiny test C functions. No actual CUDA
libraries, GPU process, model weights or paid inference were used. Native
Windows/ARM64 execution and real-model GPU startup were not tested.
