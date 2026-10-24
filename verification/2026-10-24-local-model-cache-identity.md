# Keep managed local model caches separate

The managed llama.cpp server exposes a stable `local-model` alias. Changing the
selected model and starting a new capture or marketing job therefore reused an
older model's response at the same address: existing cache keys distinguished the
alias, prompts and settings, but not the loaded model artifacts.

Resolve a runtime-only cache namespace from the ready, managed server's actual
plan (repository, weights filename and vision projector). Include it in response
cache keys so capture and marketing can still choose their own cache directories.
The server manager records its downgraded plan before CPU fallback starts, so the
identity follows the loaded fallback rather than the initial GPU recommendation.

External or stopped servers do not infer an identity from a recommended model.
Resolving an unrelated endpoint clears a previous managed namespace. The field
is excluded from saved configuration and is never sent to model providers. Empty
namespaces preserve existing cloud and unmanaged cache keys.

Before: five failing cases and two controls passed. After: 69 focused cache,
provider fallback, readiness and local-context checks passed in 3.29 seconds;
strict Pyright reported zero errors in the three changed production modules.
An additional endpoint-switch regression passed with the seven new cache cases
(8 passed in 1.98 seconds). The tests exercise real resolution, capture wiring,
client generation and disk caching, with mocked model responses. No live model
inference or paid requests were made.

Scope: new resolved clients/jobs after a model change. Existing clients do not
monitor a server restarted during their work. Artifact identity uses repository
and filenames, not a checksum of replacement bytes under the same filenames.
