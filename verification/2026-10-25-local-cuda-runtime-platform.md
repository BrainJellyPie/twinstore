# Pair local CUDA servers with libraries for the same platform

The public llama.cpp b11870 release lists Ubuntu CUDA 13.4 runtime archives
before Windows archives. TwinStore selected a Windows server and then the
first companion matching only CUDA version and architecture: an Ubuntu
tarball. Existing tests covered Windows CUDA 12.4, whose version differed
from Ubuntu, so they did not catch the shared-version case.

Companions now match the server's full OS/architecture/archive pattern and
CUDA version. The selector tries compatible versions from newest to oldest
and requires both server and companion before selecting CUDA. Without a
complete pair it uses the existing CPU fallback, or reports no available
build. Known archive names in cached CUDA installation markers are checked
too, so a prior mixed-platform install is not reused indefinitely. Existing
download authorization rules still apply to repairs.

Source evidence: [llama.cpp b11870 release assets](https://github.com/ggml-org/llama.cpp/releases/tag/b11870),
queried on 2026-10-25. The exact 13.4 Windows/Ubuntu x64/ARM64 names are in
the regression fixture. Twenty-six pre-fix checks failed across published,
reversed/shuffled ordering, supported drivers, missing companions and archive
installation. Additional cases cover cached wrong-platform installs.

The focused suites passed 74 checks in 5.10 seconds; full-source Pyright
reported zero errors and warnings. Installation checks use generated ZIP/TAR
fixtures and the real manager/extractor, verify the correct library files and
completion marker, and confirm a healthy install is reused. They include
repair of prior mixed-platform directories. No actual CUDA binaries, model
weights or paid calls were downloaded, and native Windows/GPU startup was
not tested. This verifies asset selection and installation behavior.
