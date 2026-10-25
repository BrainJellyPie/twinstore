# Keep a usable GPU build when a newer release is incomplete

The release selector returned the first CPU fallback immediately. Given a
newer release containing only CPU assets and an older complete compatible
GPU build, startup therefore downgraded the backend and selected a smaller
CPU model. A synthetic release-list reproduction confirmed the same problem
for CUDA and Vulkan through the real manager pipeline.

Selection now retains the newest CPU fallback while checking the remaining
recent releases for the requested GPU. Drafts, unsupported architectures,
unsupported CUDA versions and incomplete CUDA pairs remain excluded. If no
compatible GPU is available, the existing newest-CPU fallback still applies.
An explicit CPU plan continues to select the newest CPU build directly.

Fourteen new checks failed before the change; eight controls passed. The
focused runtime suites now pass 96 checks in 5.30 seconds. Full-source
Pyright reports zero errors and warnings. Cases include Windows/Linux,
CUDA/Vulkan, foreign architectures, missing companions, older drivers,
drafts, releases without binaries and multiple viable older releases.
Pipeline checks unpack generated archives and confirm that the chosen GPU,
model and model download paths remain intact. No native GPU process, model
weights or paid inference ran. Partial release lists are test fixtures, not
a claim that the current upstream release is incomplete.
