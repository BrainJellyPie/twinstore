# Online promo integration — 2026-10-25

Merged 71db84dfcb77e6c6e4bafa8368e2333903744da2, including the online-store
scene in the promo film and README teaser. Relative to main, only media, its
rendering source and README changed; the setup-draft fix is preserved.

Validation: both renderer and embedded JavaScript pass Node syntax checks;
all local image references in the promo HTML exist; ffprobe reads the supplied
1920 × 1080 film at 61.4 seconds. No app runtime tests were rerun. Published
media blobs are reused from the source branch, with an exact merge-tree check.
